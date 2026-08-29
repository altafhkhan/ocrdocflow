import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.document import Document
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem
from app.models.user import User
from app.services import ocr_service, field_extractor, usage_service

logger = logging.getLogger("ocrdocflow.documents")

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# We check the first bytes of the file ourselves instead of trusting the
# filename or the browser-supplied content-type header.
# (Security Policy Section 9: "The system shall not trust invoice.pdf
#  simply because the filename ends in .pdf.")
# Product decision: only PDF and image uploads are accepted - no Excel,
# Word, CSV, etc.
FILE_SIGNATURES = {
    b"%PDF": "pdf",
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}


def detect_real_file_type(header_bytes: bytes) -> str | None:
    for signature, filetype in FILE_SIGNATURES.items():
        if header_bytes.startswith(signature):
            return filetype
    return None


def _clear_abandoned_staging(db: Session, current_user: User, keep_document_id: int) -> None:
    """
    Product decision: if the user uploads a NEW document without ever
    reviewing/saving an EARLIER one, that earlier staging data (the
    auto-extracted first-guess) is treated as abandoned and cleared out
    - so "Review & Save" doesn't accumulate old, never-reviewed guesses
    indefinitely. The document record itself (and its raw OCR text) is
    NOT deleted, only the extracted-field staging tables - the user can
    still see what was uploaded, just without a pre-filled review form.
    """
    stale_doc_ids = [
        row[0] for row in (
            db.query(ExtractedInvoiceHeader.document_id)
            .join(Document, ExtractedInvoiceHeader.document_id == Document.id)
            .filter(
                Document.user_id == current_user.id,
                Document.id != keep_document_id,
                ExtractedInvoiceHeader.status == "pending_review",
            )
            .distinct()
            .all()
        )
    ]
    if stale_doc_ids:
        db.query(ExtractedInvoiceItem).filter(
            ExtractedInvoiceItem.document_id.in_(stale_doc_ids)
        ).delete(synchronize_session=False)
        db.query(ExtractedInvoiceHeader).filter(
            ExtractedInvoiceHeader.document_id.in_(stale_doc_ids)
        ).delete(synchronize_session=False)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Plan quota check - BEFORE spending time/memory on OCR. Checks the
    # user's ORGANIZATION quota (usage is pooled across all members of
    # the org). Admins are exempt (see usage_service.check_quota_before_upload).
    usage_service.check_quota_before_upload(db, current_user)

    contents = await file.read()

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    real_type = detect_real_file_type(contents[:16])
    if real_type is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file. Only PDF, JPG, and PNG are allowed.",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Random internal filename - never store or trust the user's original name
    # as a real filesystem path.
    stored_filename = f"{uuid.uuid4().hex}.{real_type}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    with open(stored_path, "wb") as f:
        f.write(contents)

    # Reject oversized PDFs BEFORE running OCR or creating a database
    # record - our current OCR processing is synchronous (one request,
    # start to finish), so very large multi-page files risk exhausting
    # memory or timing out. True bulk support needs a background job
    # queue (planned for a later phase).
    if real_type == "pdf":
        page_count = ocr_service.get_pdf_page_count(stored_path)
        if page_count > settings.MAX_PDF_PAGES:
            os.remove(stored_path)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This PDF has {page_count} pages. The current limit is "
                    f"{settings.MAX_PDF_PAGES} pages per file. Please split "
                    f"it into smaller files and upload separately."
                ),
            )

    document = Document(
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        status="processing",
        language=language,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Clean up any earlier uploads this user never reviewed/saved - see
    # docstring on _clear_abandoned_staging for the reasoning.
    _clear_abandoned_staging(db, current_user, keep_document_id=document.id)
    db.commit()

    # Captured BEFORE this document's invoice count is set, so it
    # correctly represents "usage before this upload" - at the
    # ORGANIZATION level, since usage is pooled across all members.
    org = current_user.organization
    usage_before = usage_service.get_usage_this_period(db, org) if org else 0

    # Phase 2 MVP: run OCR right here, synchronously. For a beginner-friendly
    # first version this is fine (uploads are one-at-a-time, small files).
    # A real production system would hand this off to a background job queue
    # so the upload request returns instantly - that's a later improvement.
    try:
        text, page_count = ocr_service.extract_text(stored_path, real_type, language)
        document.ocr_text = text
        document.page_count = page_count
        document.status = "done"

        # Phase 3: automatically attempt structured field extraction right
        # after OCR succeeds, and save a first-guess into the STAGING
        # tables for the user to review (nothing here is final business
        # data yet - see extraction.py). If extraction itself has a
        # problem, that shouldn't fail the whole upload - the raw OCR
        # text is still useful on its own. We DO log it though, so we can
        # actually see and fix real bugs instead of silently losing them.
        try:
            invoices_found = field_extractor.parse_invoices_from_text(text)
            # Billing/usage counts INVOICES, not pages (product decision -
            # a page can hold multiple invoices, or one invoice can span
            # several pages).
            document.detected_invoice_count = len(invoices_found)
            for invoice_index, parsed in enumerate(invoices_found):
                db.add(ExtractedInvoiceHeader(
                    document_id=document.id,
                    invoice_index=invoice_index,
                    **parsed["header"],
                ))
                for i, item in enumerate(parsed["items"]):
                    db.add(ExtractedInvoiceItem(
                        document_id=document.id,
                        invoice_index=invoice_index,
                        line_order=i,
                        **item,
                    ))
        except Exception:
            logger.exception(
                "Field extraction failed for document_id=%s (%s)",
                document.id, document.original_filename,
            )

    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)[:500]

    db.commit()
    db.refresh(document)

    usage_after = usage_service.get_usage_this_period(db, org) if org else 0
    usage_service.log_usage_warnings(db, current_user, usage_before, usage_after)

    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "status": document.status,
        "uploaded_at": document.uploaded_at,
    }


@router.get("/")
def list_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Tenant/ownership isolation: a user only ever sees their OWN documents.
    # (Security Policy Section 8 - Tenant Isolation)
    docs = db.query(Document).filter(Document.user_id == current_user.id).all()
    return docs


@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership check happens in the SAME query, not as an afterthought -
    # a user can never fetch another user's document by guessing an ID.
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc