"""
Phase 4/5 - Export (CSV or Excel).

Lets a user download their SAVED (permanent, confirmed) invoices for a
date range - not the staging/pending-review data, since only reviewed and
confirmed records should leave the system as "real" business data
(Security Policy Section 11).

Format: one row per LINE ITEM, with the invoice's header fields repeated
on every row for that invoice. This "flattened" layout is the standard
shape expected by most accounting/ERP import tools (QuickBooks, Xero,
etc), rather than a nested header+items structure. The CSV and the Excel
file hold exactly the same rows and columns.

Language: the column HEADERS (not the data itself) are shown in the
language given by the `language` query parameter, so the file reads
naturally for the person using it. This only affects labels/headers -
we never translate the actual invoice data (matches the product's
"never translate document content" decision).
"""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal

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
_RTL_LANGUAGES = {"ar", "ur"}
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _export_rows(
    db: Session,
    current_user: User,
    start_date: date,
    end_date: date,
    language: str,
    document_language: str,
) -> list[list]:
    """Validates the request and returns the data rows (no header row)."""
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

    rows: list[list] = []
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
                rows.append(header_cells + [
                    item.description, item.qty, item.unit_price, item.total_price,
                ] + totals_cells)
        else:
            # An invoice with no line items still gets one row, so it's
            # not silently dropped from the export.
            rows.append(header_cells + [None, None, None, None] + totals_cells)
    return rows


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    # utf-8-sig (adds a BOM) so Excel correctly detects UTF-8 and
    # displays Arabic text properly instead of showing garbled characters
    # - a common, easy-to-miss gotcha with plain UTF-8 CSVs.
    return output.getvalue().encode("utf-8-sig")


def _xlsx_bytes(headers: list[str], rows: list[list], rtl: bool) -> bytes:
    """A real .xlsx workbook: bold frozen header row, numbers stored as
    numbers (so they can be summed), sensible column widths, and a
    right-to-left sheet for Arabic/Urdu headings."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.sheet_view.rightToLeft = rtl

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2563EB")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(rows) + 1)}"

    for row in rows:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in row])

    for index, header in enumerate(headers, start=1):
        longest = max([len(str(header))] + [len(str(r[index - 1])) for r in rows if r[index - 1] is not None])
        ws.column_dimensions[get_column_letter(index)].width = min(60, max(10, longest + 2))

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _download(content: bytes, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/csv")
def export_csv(
    start_date: date = Query(..., description="Include invoices uploaded on/after this date"),
    end_date: date = Query(..., description="Include invoices uploaded on/before this date"),
    language: str = Query("en", description="Column header language (en, ar, ur, fr, de, es, nl, zh, ja, ko)"),
    document_language: str = Query("all", description="Only invoices from documents in this language, or 'all'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = _export_rows(db, current_user, start_date, end_date, language, document_language)
    filename = f"invoices_{document_language}_{start_date}_to_{end_date}.csv"
    return _download(_csv_bytes(_HEADERS[language], rows), "text/csv", filename)


@router.get("/xlsx")
def export_xlsx(
    start_date: date = Query(..., description="Include invoices uploaded on/after this date"),
    end_date: date = Query(..., description="Include invoices uploaded on/before this date"),
    language: str = Query("en", description="Column header language (en, ar, ur, fr, de, es, nl, zh, ja, ko)"),
    document_language: str = Query("all", description="Only invoices from documents in this language, or 'all'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Same rows and columns as /csv, as an Excel workbook."""
    rows = _export_rows(db, current_user, start_date, end_date, language, document_language)
    filename = f"invoices_{document_language}_{start_date}_to_{end_date}.xlsx"
    content = _xlsx_bytes(_HEADERS[language], rows, rtl=language in _RTL_LANGUAGES)
    return _download(content, _XLSX_MEDIA_TYPE, filename)
