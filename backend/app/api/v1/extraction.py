"""
Phase 3/4 API endpoints - structured field extraction, review, and
business validation.

A single uploaded file may contain MORE THAN ONE invoice (e.g. several
invoices combined into one PDF) - invoice_index (0, 1, 2, ...) selects
which one within the document. Most documents only have one
(invoice_index = 0). Both endpoints return total_invoices so the
frontend can show "Invoice X of Y" and enable/disable Back/Next.

Flow:
  1) After OCR finishes (see documents.py), field_extractor.py detects
     and parses ALL invoices found, saving a first-guess into the
     STAGING tables (ExtractedInvoiceHeader / ExtractedInvoiceItem),
     one row per detected invoice.
  2) GET /{document_id}/extraction?invoice_index=N - the review screen
     loads ONE invoice's staging data into editable text boxes.
  3) POST /{document_id}/extraction/confirm?invoice_index=N - user
     clicks Save; we write the (possibly corrected) values into the
     PERMANENT tables (Invoice / InvoiceItem), matched by the same
     invoice_index. Nothing is trusted as final business data until this
     step (Security Policy Section 11).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.document import Document
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.schemas.invoice import InvoiceConfirmIn
from app.services import invoice_validator

router = APIRouter(prefix="/api/v1/documents", tags=["extraction"])


def _get_owned_document(document_id: int, db: Session, current_user: User) -> Document:
    # Same ownership pattern as documents.py - a user can never reach
    # another user's document by guessing an ID (Security Policy Section 8).
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def check_duplicate_invoice(db: Session, user_id: int, invoice_number: str | None,
                             exclude_invoice_id: int | None = None) -> list[dict]:
    """
    Phase 4 check that needs a database query, so it lives here rather
    than in invoice_validator.py (which only does offline checks).
    `exclude_invoice_id` lets us re-save the SAME invoice (e.g. fixing a
    typo) without flagging it as a duplicate of itself.
    """
    if not invoice_number or not invoice_number.strip():
        return []
    query = db.query(Invoice).filter(
        Invoice.user_id == user_id, Invoice.invoice_number == invoice_number
    )
    if exclude_invoice_id is not None:
        query = query.filter(Invoice.id != exclude_invoice_id)
    existing = query.first()
    if existing:
        saved_on = existing.confirmed_at.strftime("%Y-%m-%d") if existing.confirmed_at else "an earlier date"
        return [{
            "level": "warning",
            "field": "invoice_number",
            "message": f"You already saved an invoice numbered '{invoice_number}' on {saved_on}. "
                       f"Double check this isn't a duplicate upload.",
        }]
    return []


@router.get("/{document_id}/extraction")
def get_extraction(
    document_id: int,
    invoice_index: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_document(document_id, db, current_user)

    total_invoices = (
        db.query(ExtractedInvoiceHeader)
        .filter(ExtractedInvoiceHeader.document_id == doc.id)
        .count()
    )

    header = (
        db.query(ExtractedInvoiceHeader)
        .filter(
            ExtractedInvoiceHeader.document_id == doc.id,
            ExtractedInvoiceHeader.invoice_index == invoice_index,
        )
        .first()
    )
    if header is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No extracted data for this document/invoice. Either OCR is still "
                "processing, extraction hasn't run yet, or this staging data was "
                "cleared because a newer document was uploaded before this one "
                "was reviewed and saved."
            ),
        )

    items = (
        db.query(ExtractedInvoiceItem)
        .filter(
            ExtractedInvoiceItem.document_id == doc.id,
            ExtractedInvoiceItem.invoice_index == invoice_index,
        )
        .order_by(ExtractedInvoiceItem.id)
        .all()
    )

    return {
        "invoice_index": invoice_index,
        "total_invoices": total_invoices,
        "status": header.status,
        "invoice_number": header.invoice_number,
        "invoice_date": header.invoice_date,
        "due_date": header.due_date,
        "currency": header.currency,
        "client_name": header.client_name,
        "client_company": header.client_company,
        "client_email": header.client_email,
        "sub_total": header.sub_total,
        "tax": header.tax,
        "discount": header.discount,
        "grand_total": header.grand_total,
        "items": [
            {
                "id": item.id,
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            }
            for item in items
        ],
    }


@router.post("/{document_id}/extraction/confirm")
def confirm_extraction(
    document_id: int,
    payload: InvoiceConfirmIn,
    invoice_index: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = _get_owned_document(document_id, db, current_user)

    total_invoices = (
        db.query(ExtractedInvoiceHeader)
        .filter(ExtractedInvoiceHeader.document_id == doc.id)
        .count()
    )

    # One invoice per (document, invoice_index) - if the user re-confirms
    # (e.g. fixes a typo and saves again), update the existing permanent
    # record instead of creating a duplicate.
    invoice = (
        db.query(Invoice)
        .filter(Invoice.document_id == doc.id, Invoice.invoice_index == invoice_index)
        .first()
    )
    is_new = invoice is None
    if invoice is None:
        invoice = Invoice(document_id=doc.id, invoice_index=invoice_index, user_id=current_user.id)
        db.add(invoice)

    invoice.invoice_number = payload.invoice_number
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = payload.due_date
    invoice.currency = payload.currency
    invoice.client_name = payload.client_name
    invoice.client_company = payload.client_company
    invoice.client_email = payload.client_email
    invoice.sub_total = payload.sub_total
    invoice.tax = payload.tax
    invoice.discount = payload.discount
    invoice.grand_total = payload.grand_total

    db.flush()  # makes invoice.id available for the items below

    # Replace any existing permanent line items with the confirmed set -
    # simplest correct behavior for "save again after editing".
    db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).delete()
    for i, item in enumerate(payload.items):
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            line_order=i,
            description=item.description,
            qty=item.qty,
            unit_price=item.unit_price,
            total_price=item.total_price,
        ))

    # Mark the staging record as saved, so the review screen knows not to
    # treat this document/invoice as "still needs review" next time.
    header = (
        db.query(ExtractedInvoiceHeader)
        .filter(
            ExtractedInvoiceHeader.document_id == doc.id,
            ExtractedInvoiceHeader.invoice_index == invoice_index,
        )
        .first()
    )
    if header:
        header.status = "saved"

    db.commit()
    db.refresh(invoice)

    # Phase 4 - Business Parser: run validation checks AFTER saving.
    # These never block the save (the human reviewer is the final
    # authority - Security Policy Section 11), but we return them so the
    # review screen can flag anything worth double-checking.
    header_dict = {
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "client_name": invoice.client_name,
        "sub_total": invoice.sub_total,
        "tax": invoice.tax,
        "discount": invoice.discount,
        "grand_total": invoice.grand_total,
    }
    items_list = [{"total_price": item.total_price} for item in payload.items]

    warnings = invoice_validator.validate_invoice(header_dict, items_list)
    warnings += check_duplicate_invoice(
        db, current_user.id, invoice.invoice_number,
        exclude_invoice_id=None if is_new else invoice.id,
    )

    return {
        "invoice_id": invoice.id,
        "invoice_index": invoice_index,
        "total_invoices": total_invoices,
        "status": "saved",
        "warnings": warnings,
    }