from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.sql import func
from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    # Nullable - a visitor (anonymous, no-login) upload has no user.
    # When NULL, ip_address/session_id identify the anonymous uploader
    # instead (see VisitorUsage in visitor.py for the free-tier limits).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    ip_address = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)

    # We NEVER trust the original filename for anything except display.
    # The actual file on disk is saved under a random generated name
    # (Security Policy Section 9 - File Upload Security).
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False, unique=True)
    # "uploaded" -> "processing" -> "done" or "failed"
    status = Column(String, nullable=False, default="uploaded")
    # Language the USER told us to expect, selected before upload - used
    # to pick which PaddleOCR model runs (Phase 2 MVP choice: manual
    # selection, not auto-detected before OCR).
    language = Column(String, nullable=False, default="en")
    # Language the SYSTEM thinks the document actually is, based on
    # analyzing the OCR output text after the fact (see
    # services/language_detector.py). Used to flag a likely mismatch to
    # the user - e.g. they selected English but the text looks Arabic.
    detected_language = Column(String, nullable=True)
    ocr_text = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)
    # Product decision: billing/usage quotas are counted in INVOICES, not
    # PDF pages - a single page can contain 2 invoices (counts as 2), or
    # one invoice can span several pages (counts as 1). Set after field
    # extraction runs, from len(parse_invoices_from_text(...)). Used by
    # services/usage_service.py for plan quota enforcement.
    detected_invoice_count = Column(Integer, nullable=True)
    # Plan invoices this document USES: a long invoice counts as several
    # (one per 25 line items - services/ai_cost.py). NULL on documents
    # uploaded before this existed; detected_invoice_count applies then.
    billable_invoice_count = Column(Integer, nullable=True)
    # What reading this document cost us: the AI model that answered, the
    # tokens it billed and the cost at the price list in settings. All
    # NULL when the local engine did the work (no AI cost).
    ai_model = Column(String, nullable=True)
    ai_input_tokens = Column(Integer, nullable=True)
    ai_output_tokens = Column(Integer, nullable=True)
    ai_cost_usd = Column(Numeric(12, 6), nullable=True)
    error_message = Column(String, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())