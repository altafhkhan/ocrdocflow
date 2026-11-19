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
from app.models.organization import Organization
from app.models.user import User
from app.services import email_service, usage_service

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
            # A paid plan ending starts the one-day countdown to deleting
            # its invoices (services/retention_service.py).
            leaving_paid = org.plan != "free" and payload.plan == "free"
            org.paid_plan_ended_at = datetime.now(timezone.utc) if leaving_paid else None
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
            "billable_invoice_count": doc.billable_invoice_count,
            "ai_model": doc.ai_model,
            "ai_input_tokens": doc.ai_input_tokens,
            "ai_output_tokens": doc.ai_output_tokens,
            "ai_cost_usd": float(doc.ai_cost_usd) if doc.ai_cost_usd is not None else None,
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


# --- AI usage and cost monitoring -------------------------------------------

def _usage_totals(db: Session, since: datetime, user_ids: list[int] | None = None, visitors_only: bool = False) -> dict:
    """Uploads, pages, invoices, tokens and AI cost since `since`."""
    query = db.query(
        func.count(Document.id),
        func.coalesce(func.sum(Document.page_count), 0),
        func.coalesce(func.sum(Document.detected_invoice_count), 0),
        func.coalesce(func.sum(func.coalesce(Document.billable_invoice_count, Document.detected_invoice_count)), 0),
        func.coalesce(func.sum(Document.ai_input_tokens), 0),
        func.coalesce(func.sum(Document.ai_output_tokens), 0),
        func.coalesce(func.sum(Document.ai_cost_usd), 0),
    ).filter(Document.uploaded_at >= since)
    if visitors_only:
        query = query.filter(Document.user_id.is_(None))
    elif user_ids is not None:
        if not user_ids:
            return {"documents": 0, "pages": 0, "invoices": 0, "billable_invoices": 0,
                    "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        query = query.filter(Document.user_id.in_(user_ids))
    docs, pages, invoices, billable, tokens_in, tokens_out, cost = query.one()
    return {
        "documents": int(docs or 0), "pages": int(pages or 0), "invoices": int(invoices or 0),
        "billable_invoices": int(billable or 0),
        "input_tokens": int(tokens_in or 0), "output_tokens": int(tokens_out or 0),
        "cost_usd": round(float(cost or 0), 4),
    }


@router.get("/usage")
def get_usage_report(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """
    Month-to-date AI usage and cost per customer (organization) and for the
    whole platform, with each customer's limits. Costs are our estimate:
    tokens reported by the AI provider x the price list in settings.
    """
    since = usage_service.month_start()
    organizations = []
    for org in db.query(Organization).order_by(Organization.name).all():
        members = db.query(User).filter(User.organization_id == org.id).order_by(User.id).all()
        totals = _usage_totals(db, since, [m.id for m in members])
        cap = usage_service.get_org_cost_cap(org)
        organizations.append({
            "id": org.id,
            "name": org.name,
            "plan": org.plan,
            "members": len(members),
            "owner_email": next((m.email for m in members if m.org_role == "owner"), members[0].email if members else None),
            **totals,
            "cost_cap_usd": cap,
            "cost_cap_is_custom": org.monthly_cost_cap_usd is not None,
            "cost_cap_used_percent": round(100 * totals["cost_usd"] / cap, 1) if cap > 0 else None,
            "invoices_this_billing_period": usage_service.get_usage_this_period(db, org),
            "invoice_limit": usage_service.get_plan_limit(org),
            "invoice_limit_is_custom": org.invoice_limit_override is not None,
        })

    platform = _usage_totals(db, since)
    platform_cap = settings.PLATFORM_MONTHLY_COST_CAP_USD or 0
    return {
        "month_start": since,
        "organizations": organizations,
        "visitors": _usage_totals(db, since, visitors_only=True),
        "platform": {
            **platform,
            "cost_cap_usd": platform_cap,
            "cost_cap_used_percent": round(100 * platform["cost_usd"] / platform_cap, 1) if platform_cap > 0 else None,
        },
        "settings": {
            "line_items_per_invoice": settings.LINE_ITEMS_PER_INVOICE_UNIT,
            "alert_email": settings.ALERT_EMAIL or None,
            "alert_email_can_send": bool(settings.ALERT_EMAIL) and email_service.email_configured(),
            "alert_thresholds": settings.COST_ALERT_THRESHOLDS,
            "ai_prices_usd_per_million_tokens": settings.AI_PRICES_USD_PER_MTOK,
            "ai_model": settings.GEMINI_MODEL if settings.OCR_PROVIDER == "gemini" else settings.OCR_PROVIDER,
        },
    }


class UpdateOrganizationLimits(BaseModel):
    # Send null to go back to the plan's default. A field that is left out
    # is not changed.
    monthly_cost_cap_usd: float | None = None
    invoice_limit_override: int | None = None


@router.patch("/organizations/{org_id}")
def update_organization_limits(
    org_id: int,
    payload: UpdateOrganizationLimits,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    changes = []
    sent = payload.model_fields_set

    if "monthly_cost_cap_usd" in sent:
        new_cap = payload.monthly_cost_cap_usd
        if new_cap is not None and (new_cap < 0 or new_cap > 100000):
            raise HTTPException(status_code=400, detail="Spending cap must be between 0 and 100000 USD (0 = no cap).")
        old_cap = float(org.monthly_cost_cap_usd) if org.monthly_cost_cap_usd is not None else None
        if old_cap != new_cap:
            changes.append(f"monthly AI spending cap: {old_cap if old_cap is not None else 'plan default'} -> "
                           f"{new_cap if new_cap is not None else 'plan default'}")
            org.monthly_cost_cap_usd = new_cap

    if "invoice_limit_override" in sent:
        new_limit = payload.invoice_limit_override
        if new_limit is not None and (new_limit < 0 or new_limit > 10000000):
            raise HTTPException(status_code=400, detail="Invoice limit must be between 0 and 10000000.")
        if org.invoice_limit_override != new_limit:
            changes.append(f"invoice limit: {org.invoice_limit_override if org.invoice_limit_override is not None else 'plan default'} -> "
                           f"{new_limit if new_limit is not None else 'plan default'}")
            org.invoice_limit_override = new_limit

    if changes:
        _log_action(db, admin, "organization_limits_updated", "organization", org.id,
                    "; ".join(changes) + f" (organization: {org.name})")
    db.commit()
    db.refresh(org)
    return {
        "id": org.id,
        "cost_cap_usd": usage_service.get_org_cost_cap(org),
        "cost_cap_is_custom": org.monthly_cost_cap_usd is not None,
        "invoice_limit": usage_service.get_plan_limit(org),
        "invoice_limit_is_custom": org.invoice_limit_override is not None,
    }

