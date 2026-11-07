"""
Phase 4/5 - CSV Export.

Lets a user download their SAVED (permanent, confirmed) invoices for a
date range as a CSV file - not the staging/pending-review data, since
only reviewed and confirmed records should leave the system as "real"
business data (Security Policy Section 11).

Format: one row per LINE ITEM, with the invoice's header fields repeated
on every row for that invoice. This "flattened" layout is the standard
shape expected by most accounting/ERP CSV import tools (QuickBooks,
Xero, etc), rather than a nested header+items structure.

Language: the column HEADERS (not the data itself) are shown in English
or Arabic depending on the `language` query parameter, so the file reads
naturally for the person using it. This only affects labels/headers -
we never translate the actual invoice data (matches the product's
"never translate document content" decision).
"""
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.services.csv_headers import CSV_HEADERS

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.document import Document
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])

_HEADERS = CSV_HEADERS


@router.get("/csv")
def export_csv(
    start_date: date = Query(..., description="Include invoices uploaded on/after this date"),
    end_date: date = Query(..., description="Include invoices uploaded on/before this date"),
    language: str = Query("en", description="Column header language (en, ar, ur, fr, de, es, nl, zh, ja, ko)"),
    document_language: str = Query("all", description="Only invoices from documents in this language, or 'all'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")
    if language not in _HEADERS:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use one of: {', '.join(_HEADERS)}.")
    if document_language != "all" and document_language not in _HEADERS:
        raise HTTPException(status_code=400, detail="Unsupported document language filter.")

    # Date range is inclusive of the whole end_date, so add one day and
    # use a strict "less than" comparison against the timestamp column.
    range_end_exclusive = end_date + timedelta(days=1)

    # Only SAVED invoices (permanent table), only THIS user's own data
    # (tenant isolation - Security Policy Section 8), matching the
    # document's language and upload date range.
    query = (
        db.query(Invoice)
        .join(Document, Invoice.document_id == Document.id)
        .filter(
            Invoice.user_id == current_user.id,
            Document.uploaded_at >= start_date,
            Document.uploaded_at < range_end_exclusive,
        )
    )
    if document_language != "all":
        # A document uploaded with "Auto-detect" carries the detected
        # language in detected_language, an explicit choice in language.
        query = query.filter(or_(
            Document.language == document_language,
            and_(Document.language == "auto", Document.detected_language == document_language),
        ))
    invoices = query.order_by(Invoice.confirmed_at).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_HEADERS[language])

    for inv in invoices:
        items = (
            db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == inv.id)
            .order_by(InvoiceItem.line_order)
            .all()
        )
        header_cells = [
            inv.invoice_number, inv.invoice_date, inv.due_date, inv.currency,
            inv.client_name, inv.client_company, inv.client_email,
        ]
        totals_cells = [inv.sub_total, inv.tax, inv.discount, inv.grand_total]

        if items:
            for item in items:
                writer.writerow(header_cells + [
                    item.description, item.qty, item.unit_price, item.total_price,
                ] + totals_cells)
        else:
            # An invoice with no line items still gets one row, so it's
            # not silently dropped from the export.
            writer.writerow(header_cells + [None, None, None, None] + totals_cells)

    # utf-8-sig (adds a BOM) so Excel correctly detects UTF-8 and
    # displays Arabic text properly instead of showing garbled characters
    # - a common, easy-to-miss gotcha with plain UTF-8 CSVs.
    csv_bytes = output.getvalue().encode("utf-8-sig")

    filename = f"invoices_{document_language}_{start_date}_to_{end_date}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
