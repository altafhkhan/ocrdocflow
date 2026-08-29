from typing import Optional, List
from pydantic import BaseModel


class InvoiceItemIn(BaseModel):
    description: Optional[str] = None
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class InvoiceConfirmIn(BaseModel):
    """
    What the frontend sends when the user clicks "Save" on the review
    screen - the (possibly corrected) field values, ready to be written
    into the permanent invoices / invoice_items tables.
    """
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = None
    client_name: Optional[str] = None
    client_company: Optional[str] = None
    client_email: Optional[str] = None
    sub_total: Optional[float] = None
    tax: Optional[float] = None
    discount: Optional[float] = None
    grand_total: Optional[float] = None
    items: List[InvoiceItemIn] = []
