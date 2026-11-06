"""
Visitor (anonymous, no-login) free-tier upload flow.

Product decision: visitors can try the OCR/extraction pipeline without
creating an account, subject to layered limits:
  - Max 1 MB per file (stricter than the authenticated 10 MB limit)
  - Max 3 files per browser session per calendar day
  - Lifetime cap per IP address: 5 free uploads, then an email address
    is required to continue, then 20 more uploads (25 total), after
    which the visitor must create a real account
  - Abandoned visitor data (documents with no matching user) older than
    24 hours is cleaned up automatically on each new visitor upload

MAC address tracking was originally requested but isn't technically
possible for a web server to see - browsers never expose it, and it
doesn't survive being routed over the internet. IP address is used
instead as the practical (if imperfect - shared networks/VPNs) substitute.

Visitors do NOT get the full review-and-save-to-permanent-table
workflow that logged-in users get - they see their OCR/extraction
results and can download a CSV of what was found, but nothing is
"confirmed" into a permanent business record. That's the incentive to
create a real account.
"""
import logging
import os
import uuid
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.document import Document
from app.models.visitor import VisitorUsage
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem
from app.services import ocr_service, field_extractor
from app.api.v1.documents import detect_real_file_type

logger = logging.getLogger("ocrdocflow.visitor")

router = APIRouter(prefix="/api/v1/visitor", tags=["visitor"])

VISITOR_MAX_FILE_MB = 1
VISITOR_MAX_PER_DAY = 3
VISITOR_FREE_BEFORE_EMAIL = 5
VISITOR_MAX_LIFETIME = 25
VISITOR_DATA_MAX_AGE_HOURS = 24


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_owned_visitor_document(document_id: int, session_id: str, ip: str, db: Session) -> Document:
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id.is_(None),
            Document.session_id == session_id,
            Document.ip_address == ip,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _cleanup_abandoned_visitor_data(db: Session) -> None:
    """
    Visitor data (documents with no user_id) older than 24 hours is
    treated as abandoned and deleted - files on disk plus staging
    extraction data. Runs automatically at the start of each new
    visitor upload rather than needing a separate background scheduler.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=VISITOR_DATA_MAX_AGE_HOURS)
    stale_docs = (
        db.query(Document)
        .filter(Document.user_id.is_(None), Document.uploaded_at < cutoff)
        .all()
    )
    for doc in stale_docs:
        file_path = os.path.join(settings.UPLOAD_DIR, doc.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.query(ExtractedInvoiceItem).filter(
            ExtractedInvoiceItem.document_id == doc.id
        ).delete(synchronize_session=False)
        db.query(ExtractedInvoiceHeader).filter(
            ExtractedInvoiceHeader.document_id == doc.id
        ).delete(synchronize_session=False)
        db.delete(doc)
    if stale_docs:
        db.commit()


@router.post("/upload")
async def visitor_upload(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en"),
    session_id: str = Form(...),
    email: str | None = Form(None),
    db: Session = Depends(get_db),
):
    _cleanup_abandoned_visitor_data(db)

    ip = _get_client_ip(request)

    contents = await file.read()
    max_bytes = VISITOR_MAX_FILE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Free trial limit is {VISITOR_MAX_FILE_MB} MB per file.",
        )

    real_type = detect_real_file_type(contents[:16])
    if real_type is None:
        raise HTTPException(status_code=400, detail="Unsupported file. Only PDF, JPG, and PNG are allowed.")

    # Daily per-session limit.
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = (
        db.query(Document)
        .filter(
            Document.session_id == session_id,
            Document.ip_address == ip,
            Document.uploaded_at >= today_start,
        )
        .count()
    )
    if today_count >= VISITOR_MAX_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Free trial limit reached: {VISITOR_MAX_PER_DAY} files per day. "
                f"Please try again tomorrow, or sign up for unlimited access."
            ),
        )

    # Lifetime per-IP limit and email gate.
    usage = db.query(VisitorUsage).filter(VisitorUsage.ip_address == ip).first()
    if usage is None:
        usage = VisitorUsage(ip_address=ip, total_uploads=0)
        db.add(usage)
        db.flush()

    if usage.total_uploads >= VISITOR_MAX_LIFETIME:
        raise HTTPException(
            status_code=403,
            detail="You've used all your free trial uploads. Please create a free account to continue.",
        )

    if usage.total_uploads >= VISITOR_FREE_BEFORE_EMAIL and not usage.email:
        if not email or "@" not in email:
            # Distinct status code (not just 400) so the frontend can
            # specifically show the email-capture prompt.
            raise HTTPException(status_code=402, detail="EMAIL_REQUIRED")
        usage.email = email
        usage.email_captured_at = datetime.now(timezone.utc)

    # No real email-sending infrastructure connected yet - log what
    # WOULD be sent instead, so this is easy to wire up to a real
    # provider later without changing the trigger logic.
    if usage.email and usage.total_uploads >= VISITOR_FREE_BEFORE_EMAIL:
        logger.info(
            "Would send marketing plans email to %s (visitor upload #%d from IP %s)",
            usage.email, usage.total_uploads + 1, ip,
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}.{real_type}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_filename)
    with open(stored_path, "wb") as f:
        f.write(contents)

    if real_type == "pdf":
        page_count = ocr_service.get_pdf_page_count(stored_path)
        if page_count > settings.MAX_PDF_PAGES:
            os.remove(stored_path)
            raise HTTPException(
                status_code=400,
                detail=f"This PDF has {page_count} pages. The free trial limit is {settings.MAX_PDF_PAGES} pages per file.",
            )

    document = Document(
        user_id=None,
        ip_address=ip,
        session_id=session_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        status="processing",
        language=language,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        text, page_count, invoices = ocr_service.extract_document(stored_path, real_type, language)
        document.ocr_text = text
        document.page_count = page_count
        document.status = "done"
        try:
            invoices_found = invoices if invoices is not None else field_extractor.parse_invoices_from_text(text)
            for invoice_index, parsed in enumerate(invoices_found):
                db.add(ExtractedInvoiceHeader(
                    document_id=document.id, invoice_index=invoice_index, **parsed["header"],
                ))
                for i, item in enumerate(parsed["items"]):
                    db.add(ExtractedInvoiceItem(
                        document_id=document.id, invoice_index=invoice_index, line_order=i, **item,
                    ))
        except Exception:
            logger.exception("Visitor field extraction failed for document_id=%s", document.id)
    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)[:500]

    usage.total_uploads += 1
    usage.last_upload_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(document)

    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "status": document.status,
        "uploaded_at": document.uploaded_at,
        "uploads_used": usage.total_uploads,
        "uploads_remaining": max(0, VISITOR_MAX_LIFETIME - usage.total_uploads),
    }


@router.get("/documents")
def list_visitor_documents(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    docs = (
        db.query(Document)
        .filter(Document.user_id.is_(None), Document.session_id == session_id, Document.ip_address == ip)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return docs


@router.get("/documents/{document_id}")
def get_visitor_document(
    document_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    return _get_owned_visitor_document(document_id, session_id, ip, db)


@router.get("/documents/{document_id}/extraction")
def get_visitor_extraction(
    document_id: int,
    session_id: str,
    request: Request,
    invoice_index: int = 0,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    doc = _get_owned_visitor_document(document_id, session_id, ip, db)

    header = (
        db.query(ExtractedInvoiceHeader)
        .filter(
            ExtractedInvoiceHeader.document_id == doc.id,
            ExtractedInvoiceHeader.invoice_index == invoice_index,
        )
        .first()
    )
    if header is None:
        raise HTTPException(status_code=404, detail="No extracted data for this document yet.")

    items = (
        db.query(ExtractedInvoiceItem)
        .filter(
            ExtractedInvoiceItem.document_id == doc.id,
            ExtractedInvoiceItem.invoice_index == invoice_index,
        )
        .order_by(ExtractedInvoiceItem.id)
        .all()
    )

    total_invoices = (
        db.query(ExtractedInvoiceHeader)
        .filter(ExtractedInvoiceHeader.document_id == doc.id)
        .count()
    )

    return {
        "invoice_index": invoice_index,
        "total_invoices": total_invoices,
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
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            }
            for item in items
        ],
    }


@router.get("/csv")
def visitor_csv(
    session_id: str,
    request: Request,
    language: str = "en",
    db: Session = Depends(get_db),
):
    """
    Direct CSV download of everything extracted in THIS visitor session
    - no confirm/save step exists for visitors, so this reads straight
    from the staging tables rather than a permanent invoices table.
    """
    ip = _get_client_ip(request)

    headers_en = [
        "Invoice Number", "Invoice Date", "Due Date", "Currency",
        "Client Name", "Client Company", "Client Email",
        "Item Description", "Qty", "Unit Price", "Total Price",
        "Sub-Total", "Tax", "Discount", "Grand Total",
    ]
    headers_ar = [
        "رقم الفاتورة", "تاريخ الفاتورة", "تاريخ الاستحقاق", "العملة",
        "اسم العميل", "اسم الشركة", "البريد الإلكتروني",
        "الوصف", "الكمية", "سعر الوحدة", "السعر الإجمالي",
        "المجموع الفرعي", "الضريبة", "الخصم", "الإجمالي الكلي",
    ]
    headers = headers_ar if language == "ar" else headers_en

    doc_ids = [
        row[0] for row in (
            db.query(Document.id)
            .filter(Document.user_id.is_(None), Document.session_id == session_id, Document.ip_address == ip)
            .all()
        )
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)

    if doc_ids:
        headers_rows = (
            db.query(ExtractedInvoiceHeader)
            .filter(ExtractedInvoiceHeader.document_id.in_(doc_ids))
            .all()
        )
        for h in headers_rows:
            items = (
                db.query(ExtractedInvoiceItem)
                .filter(
                    ExtractedInvoiceItem.document_id == h.document_id,
                    ExtractedInvoiceItem.invoice_index == h.invoice_index,
                )
                .order_by(ExtractedInvoiceItem.line_order)
                .all()
            )
            header_cells = [
                h.invoice_number, h.invoice_date, h.due_date, h.currency,
                h.client_name, h.client_company, h.client_email,
            ]
            totals_cells = [h.sub_total, h.tax, h.discount, h.grand_total]
            if items:
                for item in items:
                    writer.writerow(header_cells + [
                        item.description, item.qty, item.unit_price, item.total_price,
                    ] + totals_cells)
            else:
                writer.writerow(header_cells + [None, None, None, None] + totals_cells)

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ocrdocflow_free_trial.csv"'},
    )