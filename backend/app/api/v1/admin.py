"""
Admin-only endpoints. Every endpoint here requires the "admin" role,
enforced via get_current_admin (see api/deps.py) - a real backend check,
not just a hidden frontend page (Security Policy Section 7).

Every action that CHANGES something (role, plan, deletion) writes an
entry to admin_audit_log (Security Policy Section 17 - "Administrators
should not be able to silently alter... without a record").
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.database import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.document import Document
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.services import usage_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_ROLES = {"user", "admin"}
VALID_PLANS = {"free", "starter", "professional", "business"}


def _log_action(db: Session, admin: User, action: str, target_type: str, target_id: int, details: str) -> None:
    db.add(AdminAuditLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    ))


@router.get("/users")
def list_all_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    users = db.query(User).order_by(User.id).all()

    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    total_counts = dict(
        db.query(Document.user_id, func.count(Document.id))
        .group_by(Document.user_id)
        .all()
    )
    month_counts = dict(
        db.query(Document.user_id, func.count(Document.id))
        .filter(Document.uploaded_at >= month_start)
        .group_by(Document.user_id)
        .all()
    )

    # Cache usage/limit per organization, since members of the same org
    # would otherwise trigger the same calculation repeatedly.
    org_usage_cache: dict[int, int] = {}
    org_limit_cache: dict[int, int] = {}

    result = []
    for u in users:
        org = u.organization
        if org is not None:
            if org.id not in org_usage_cache:
                org_usage_cache[org.id] = usage_service.get_usage_this_period(db, org)
                org_limit_cache[org.id] = usage_service.get_plan_limit(org)
            plan = org.plan
            plan_started_at = org.plan_started_at
            subscription_status = org.subscription_status
            org_name = org.name
            usage = org_usage_cache[org.id]
            limit = org_limit_cache[org.id]
        else:
            plan = "free"
            plan_started_at = None
            subscription_status = None
            org_name = None
            usage = 0
            limit = usage_service.PLAN_LIMITS["free"]

        result.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "plan": plan,
            "org_name": org_name,
            "org_role": u.org_role,
            "created_at": u.created_at,
            "plan_started_at": plan_started_at,
            "subscription_status": subscription_status,
            "documents_total": total_counts.get(u.id, 0),
            "documents_this_month": month_counts.get(u.id, 0),
            "invoices_this_billing_period": usage,
            "billing_period_limit": limit,
        })
    return result


class UpdateUserPayload(BaseModel):
    role: str | None = None
    plan: str | None = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    changes = []

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
        if target.id == admin.id and payload.role != "admin":
            # Prevents an admin from locking themselves out by accident.
            raise HTTPException(status_code=400, detail="You cannot remove your own admin access.")
        if target.role != payload.role:
            changes.append(f"role: {target.role} -> {payload.role}")
            target.role = payload.role

    if payload.plan is not None:
        if payload.plan not in VALID_PLANS:
            raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {', '.join(VALID_PLANS)}")
        org = target.organization
        if org is None:
            raise HTTPException(status_code=400, detail="This user has no organization to update.")
        if org.plan != payload.plan:
            changes.append(f"plan: {org.plan} -> {payload.plan} (organization: {org.name})")
            org.plan = payload.plan
            # Our stand-in for "a payment happened" until real
            # self-service billing exists - starts a fresh billing
            # period right now.
            org.plan_started_at = datetime.now(timezone.utc)

    if changes:
        _log_action(
            db, admin, "user_updated", "user", target.id,
            "; ".join(changes) + f" (target: {target.email})",
        )

    db.commit()
    db.refresh(target)
    return {"id": target.id, "email": target.email, "role": target.role}


@router.get("/documents")
def list_all_documents(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    rows = (
        db.query(Document, User.email)
        .join(User, Document.user_id == User.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": doc.id,
            "user_email": email,
            "original_filename": doc.original_filename,
            "status": doc.status,
            "language": doc.language,
            "detected_language": doc.detected_language,
            "page_count": doc.page_count,
            "detected_invoice_count": doc.detected_invoice_count,
            "uploaded_at": doc.uploaded_at,
        }
        for doc, email in rows
    ]


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    owner = db.query(User).filter(User.id == doc.user_id).first()
    details = (
        f"deleted document '{doc.original_filename}' (id={doc.id}) "
        f"belonging to {owner.email if owner else 'unknown user'}"
    )

    file_path = os.path.join(settings.UPLOAD_DIR, doc.stored_filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    invoice_ids = [
        row[0] for row in db.query(Invoice.id).filter(Invoice.document_id == doc.id).all()
    ]
    if invoice_ids:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
        db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).delete(synchronize_session=False)

    db.query(ExtractedInvoiceItem).filter(
        ExtractedInvoiceItem.document_id == doc.id
    ).delete(synchronize_session=False)
    db.query(ExtractedInvoiceHeader).filter(
        ExtractedInvoiceHeader.document_id == doc.id
    ).delete(synchronize_session=False)

    db.delete(doc)

    _log_action(db, admin, "document_deleted", "document", document_id, details)

    db.commit()
    return {"status": "deleted", "id": document_id}


@router.get("/audit-log")
def get_audit_log(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    rows = (
        db.query(AdminAuditLog, User.email)
        .join(User, AdminAuditLog.admin_user_id == User.id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": log.id,
            "admin_email": email,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log, email in rows
    ]