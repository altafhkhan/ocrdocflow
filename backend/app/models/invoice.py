"""
PERMANENT tables - confirmed invoice data, written only after the user
reviews the staging (extracted_invoice_*) data and clicks Save.

Like the staging tables, invoice_index distinguishes multiple invoices
that came from the same uploaded document (most documents just have one,
invoice_index = 0).
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("document_id", "invoice_index", name="uq_invoice_doc_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    invoice_index = Column(Integer, nullable=False, default=0)
    # Redundant with documents.user_id, but kept here too so invoice
    # queries/reports don't always need a join back to documents just to
    # enforce tenant/ownership isolation (Security Policy Section 8).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    invoice_number = Column(String, nullable=True)
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

    confirmed_at = Column(DateTime(timezone=True), server_default=func.now())


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)

    line_order = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    qty = Column(Numeric(10, 2), nullable=True)
    unit_price = Column(Numeric(12, 2), nullable=True)
    total_price = Column(Numeric(12, 2), nullable=True)
