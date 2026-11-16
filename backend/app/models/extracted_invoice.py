"""
STAGING tables - hold what OCR + rule-based extraction guessed for a
document's invoice fields, before the user reviews and confirms them.

A single uploaded file may contain MORE THAN ONE invoice (e.g. several
invoices scanned into one PDF) - invoice_index distinguishes them
(0, 1, 2, ...) within the same document, in the order they were detected.
Most documents will just have one (invoice_index = 0).

Nothing here is trusted as final business data yet (Security Policy
Section 11: "AI-generated results shall be validated before being stored
as business data"). Once the user reviews and clicks Save, the confirmed
values are copied into the permanent `invoices` / `invoice_items` tables
(see app/models/invoice.py).
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base


class ExtractedInvoiceHeader(Base):
    __tablename__ = "extracted_invoice_header"
    __table_args__ = (
        # A document can have several invoices, but not two with the same
        # index - keeps ordering unambiguous.
        UniqueConstraint("document_id", "invoice_index", name="uq_extracted_header_doc_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    # Which invoice this is WITHIN the document (0 = first invoice found).
    invoice_index = Column(Integer, nullable=False, default=0)

    invoice_number = Column(String, nullable=True)
    # Kept as text at this stage - dates from OCR can come in odd formats
    # (DD/MM/YYYY, MM-DD-YY, etc) and the user may need to correct them
    # before we try to parse them into a real date type.
    invoice_date = Column(String, nullable=True)
    due_date = Column(String, nullable=True)
    currency = Column(String, nullable=True)

    client_name = Column(String, nullable=True)
    client_company = Column(String, nullable=True)
    client_email = Column(String, nullable=True)

    sub_total = Column(Numeric(12, 2), nullable=True)
    tax = Column(Numeric(12, 2), nullable=True)
    discount = Column(Numeric(12, 2), nullable=True)
    grand_total = Column(Numeric(12, 2), nullable=True)

    # "pending_review" -> "saved" (once the user confirms it and it's
    # copied into the permanent `invoices` table)
    status = Column(String, nullable=False, default="pending_review")
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())


class ExtractedInvoiceItem(Base):
    __tablename__ = "extracted_invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    # Which invoice within the document this line item belongs to -
    # matches ExtractedInvoiceHeader.invoice_index for the same document.
    invoice_index = Column(Integer, nullable=False, default=0)

    line_order = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    qty = Column(Numeric(10, 2), nullable=True)
    unit_price = Column(Numeric(12, 2), nullable=True)
    total_price = Column(Numeric(12, 2), nullable=True)
