"""
Phase 3 - Structured Field Extraction (simple, rule-based).

Takes the raw OCR text for a document and pulls out invoice header fields
(invoice number, dates, totals, client info) and line items, using
keyword/label matching plus regular expressions - NOT a machine learning
model. This is an intentional MVP scope decision: it's fast, predictable,
and easy to debug/tune by just adjusting the patterns below.

IMPORTANT CONTEXT: OCR text doesn't always come out in perfect reading
order, especially for documents with side-by-side columns (like this
invoice's "BILL TO" / "PAYMENT DETAILS" layout). A label and its value can
end up several lines apart, or even swapped in order (we saw this for real
with "Due Date" - its value printed one line BEFORE the label). To handle
this without a full table-layout engine, `_find_value_near_label()`
searches a small window of lines around each label instead of assuming
the value is always on the very next line.

Nothing extracted here is treated as final/trusted business data - it's
written to the *staging* tables (ExtractedInvoiceHeader / ExtractedInvoiceItem)
for the user to review and correct before saving
(Security Policy Section 11: "AI-generated results shall be validated
before being stored as business data").
"""
import re
from typing import Optional


# --- Generic value patterns -------------------------------------------------
_DATE_RE = r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"
_INVOICE_NO_RE = r"\b[A-Za-z]{2,6}-?\d{2,}\b"
_MONEY_RE = r"\b\d+(?:,\d{3})*(?:\.\d{2})?\b(?!\s*%)"
_EMAIL_RE = r"[\w.+-]+\s*@\s*[\w-]+\.[\w.-]+"
_KNOWN_CURRENCIES = ["PKR", "USD", "EUR", "GBP", "AED", "SAR"]
_CURRENCY_RE = r"\b(" + "|".join(_KNOWN_CURRENCIES) + r")\b"

# Lines that look like any of these are treated as "this is a label, not a
# free-text value" - used so name/address/company matching doesn't
# accidentally grab a neighboring field's label as if it were the value.
_KNOWN_LABEL_PATTERNS = [
    r"client name", r"client company", r"client address", r"email\s*/?\s*phone",
    r"payment terms", r"^bank\b", r"account\s*/?\s*iban", r"swift",
    r"invoice no", r"invoice date", r"due date", r"currency", r"invoice type",
    r"^item\b", r"^description\b", r"^qty", r"unit price", r"total price",
    r"sub[-\s]?total", r"\btax\b", r"discount", r"grand\s*total",
    r"notes\s*/?\s*payment", r"signature", r"^address:",
    r"^bill\s*to$", r"^payment\s*details$",
    # Arabic/Urdu label equivalents (best-effort stems, tolerant of the
    # OCR misreads we saw in real testing - e.g. dropped/altered letters
    # like "المجموع" coming out as "المجموه").
    r"رقم\s*الف", r"تاريخ\s*الفاتورة", r"تاريخ\s*الاستحقاق", r"العملة",
    r"اسم\s*العميل", r"اسم\s*الشركة", r"العنوان", r"لكتروني",
    r"المجمو", r"ضرب", r"الخصم", r"كلي", r"نوع\s*الفاتورة",
]
_LABEL_LINE_RE = re.compile("|".join(_KNOWN_LABEL_PATTERNS), re.IGNORECASE)

# Matches the "--- Page N ---" markers our own ocr_service.py inserts -
# these aren't real document content and should be ignored.
_PAGE_MARKER_RE = re.compile(r"^-{2,}\s*Page\s+\d+\s*-{2,}$", re.IGNORECASE)

# Marks where a NEW invoice likely starts within the document's text.
# We prefer a standalone "INVOICE" title line (the very first line of
# most invoice templates) over the "Invoice No." label further down,
# because splitting at "Invoice No." leaves the preceding title/company
# lines stranded at the END of the PREVIOUS invoice's segment instead of
# the start of their own - confirmed with a real multi-page test file.
_INVOICE_TITLE_RE = re.compile(r"^invoice$", re.IGNORECASE)
_INVOICE_NO_LABEL_RE = re.compile(r"^invoice\s*no", re.IGNORECASE)


def _split_into_invoice_segments(lines: list[str]) -> list[list[str]]:
    """
    Splits the document's lines into one chunk per detected invoice.
    Falls back to treating the WHOLE document as a single invoice if no
    clear boundary is found - preserves existing single-invoice behavior
    for documents where this heuristic doesn't find anything.

    This heuristic is a first pass - it's expected to need tuning once
    tested against more real multi-invoice files.
    """
    title_starts = [i for i, line in enumerate(lines) if _INVOICE_TITLE_RE.match(line.strip())]
    # Only trust title-based splitting if we found at least 2 - a single
    # match just means "this is a normal one-invoice document with a
    # title", not a boundary to split on. In that case (or if there's no
    # standalone title line at all in this template), fall back to the
    # "Invoice No." label instead.
    if len(title_starts) >= 2:
        starts = title_starts
    else:
        starts = [i for i, line in enumerate(lines) if _INVOICE_NO_LABEL_RE.match(line.strip())]

    if not starts:
        return [lines]

    segments = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        segments.append(lines[start:end])
    return segments


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip().strip("_").strip()
    return value or None


def _find_value_near_label(lines: list[str], label_patterns: list[str],
                            value_pattern: str, window: int = 3,
                            prefer_backward: bool = False) -> Optional[str]:
    """
    Find a line matching one of `label_patterns`, then look for a line
    matching `value_pattern` nearby - first checking the SAME line
    (after a colon), then nearby lines, closest distance first.

    Which direction (forward/backward) is checked first at each distance
    depends on `prefer_backward` - different document conventions put
    the value on different sides of the label:
      - English templates: usually "Label:\\nValue" (value AFTER)
      - Arabic templates (confirmed via real testing): usually
        "Value\\nLabel:" (value BEFORE) - so prefer_backward=True there.
    This is set per-document by the caller based on detected language,
    not guessed per-field, since it's a document-wide convention.
    """
    label_re = re.compile("|".join(label_patterns), re.IGNORECASE)
    value_re = re.compile(value_pattern, re.IGNORECASE)

    for i, line in enumerate(lines):
        if not label_re.search(line):
            continue

        if ":" in line:
            after_colon = line.split(":", 1)[1]
            m = value_re.search(after_colon)
            if m:
                return _clean(m.group(0))

        offsets = []
        for d in range(1, window + 1):
            offsets.extend([-d, d] if prefer_backward else [d, -d])
        for offset in offsets:
            j = i + offset
            if 0 <= j < len(lines) and not label_re.search(lines[j]):
                m = value_re.search(lines[j])
                if m:
                    return _clean(m.group(0))
    return None


def _find_freetext_near_label(lines: list[str], label_patterns: list[str],
                               window: int = 3, prefer_backward: bool = False) -> Optional[str]:
    """
    For fields like Client Name/Company/Address where the value isn't a
    fixed pattern - just "the nearest real line that isn't itself a
    known label and isn't blank". See _find_value_near_label for why
    `prefer_backward` matters (document-convention-dependent).
    """
    label_re = re.compile("|".join(label_patterns), re.IGNORECASE)

    for i, line in enumerate(lines):
        if not label_re.search(line):
            continue

        if ":" in line:
            after_colon = _clean(line.split(":", 1)[1])
            if after_colon and not _LABEL_LINE_RE.search(after_colon):
                return after_colon

        offsets = []
        for d in range(1, window + 1):
            offsets.extend([-d, d] if prefer_backward else [d, -d])

        for offset in offsets:
            j = i + offset
            if 0 <= j < len(lines):
                candidate = _clean(lines[j])
                if candidate and not _LABEL_LINE_RE.search(candidate):
                    return candidate
    return None


def _parse_money(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _parse_line_items(lines: list[str]) -> list[dict]:
    """
    Walks the lines between the table header ("Item / Description / Qty. /
    Unit Price / Total Price") and the first totals label ("Sub-Total"
    etc), grouping them into items using a simple state machine:

        name -> description -> numbers (qty, unit price, total price)

    If OCR only found 2 numbers for a row instead of 3 (as happened with
    a missed "qty" digit in real testing), we assign them as
    (unit_price, total_price) and leave qty blank rather than guessing
    which number is missing - the user corrects this in the review screen.

    This is a pragmatic heuristic tuned to real OCR output, not a strict
    table parser - expected to need small tweaks as we test more invoices.
    """
    header_labels = {"item", "description", "qty.", "qty", "unit price", "total price"}
    money_re = re.compile(r"^\d+(?:,\d{3})*(?:\.\d{2})?$")
    continued_re = re.compile(r"\(continued\)", re.IGNORECASE)

    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "item":
            start = i + 1
            break
    if start is None:
        return []

    i = start
    while i < len(lines) and lines[i].strip().lower().strip(".") in header_labels:
        i += 1

    end = len(lines)
    for j in range(i, len(lines)):
        if re.search(r"sub[-\s]?total|notes\s*/?\s*payment", lines[j], re.IGNORECASE):
            end = j
            break

    items: list[dict] = []
    current_name = None
    current_desc = None
    numbers: list[str] = []
    state = "name"  # name -> description -> numbers

    def finalize():
        if current_name is None:
            return
        qty = unit_price = total_price = None
        if len(numbers) >= 3:
            qty, unit_price, total_price = numbers[-3], numbers[-2], numbers[-1]
        elif len(numbers) == 2:
            unit_price, total_price = numbers[-2], numbers[-1]
        elif len(numbers) == 1:
            total_price = numbers[-1]
        description = f"{current_name} - {current_desc}" if current_desc else current_name
        items.append({
            "description": description,
            "qty": _parse_money(qty),
            "unit_price": _parse_money(unit_price),
            "total_price": _parse_money(total_price),
        })

    for raw_line in lines[i:end]:
        line = raw_line.strip()
        if not line:
            continue

        # A multi-page invoice repeats the table header on each page, and
        # may include a "(continued)" note in between - neither is a real
        # item, so skip them wherever they appear (not just at the start).
        if line.lower().strip(".") in header_labels or continued_re.search(line):
            continue

        if state == "name":
            current_name = line
            state = "description"
        elif state == "description":
            if money_re.match(line):
                numbers.append(line)
                state = "numbers"
            else:
                current_desc = line
                state = "numbers"
        elif state == "numbers":
            if money_re.match(line):
                numbers.append(line)
            else:
                finalize()
                current_name = line
                current_desc = None
                numbers = []
                state = "description"

    finalize()
    return items


_ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")


def _is_rtl_segment(lines: list[str]) -> bool:
    """
    Quick check: does this chunk of text look predominantly Arabic-script?
    Used to decide search direction (see _find_value_near_label) - Arabic
    templates put values BEFORE their label, English ones AFTER.
    """
    text = "\n".join(lines)
    return len(_ARABIC_CHAR_RE.findall(text)) > len(_LATIN_CHAR_RE.findall(text))


def _parse_single_invoice(lines: list[str]) -> dict:
    """
    Extracts header fields + line items from a chunk of lines assumed to
    represent ONE invoice. Any field that couldn't be found is simply
    None - the review screen will show it blank for the user to fill in.
    """
    rtl = _is_rtl_segment(lines)

    header = {
        "invoice_number": _find_value_near_label(lines, [r"invoice no", r"رقم\s*الف"], _INVOICE_NO_RE, prefer_backward=rtl),
        "invoice_date": _find_value_near_label(lines, [r"invoice date", r"تاريخ\s*الفاتورة"], _DATE_RE, prefer_backward=rtl),
        "due_date": _find_value_near_label(lines, [r"due date", r"تاريخ\s*الاستحقاق"], _DATE_RE, prefer_backward=rtl),
        "currency": _find_value_near_label(lines, [r"currency", r"العملة"], _CURRENCY_RE, prefer_backward=rtl),
        "client_name": _find_freetext_near_label(lines, [r"client name", r"اسم\s*العميل"], prefer_backward=rtl),
        "client_company": _find_freetext_near_label(lines, [r"client company", r"اسم\s*الشركة"], prefer_backward=rtl),
        "client_email": _find_value_near_label(lines, [r"email\s*/?\s*phone", r"لكتروني"], _EMAIL_RE, prefer_backward=rtl),
        "sub_total": _parse_money(_find_value_near_label(lines, [r"sub[-\s]?total", r"المجمو"], _MONEY_RE, prefer_backward=rtl)),
        "tax": _parse_money(_find_value_near_label(lines, [r"\btax\b", r"ضرب"], _MONEY_RE, prefer_backward=rtl)),
        "discount": _parse_money(_find_value_near_label(lines, [r"discount", r"الخصم"], _MONEY_RE, prefer_backward=rtl)),
        "grand_total": _parse_money(_find_value_near_label(lines, [r"grand\s*total", r"كلي"], _MONEY_RE, prefer_backward=rtl)),
    }

    # Clean up the OCR spacing artifact around "@" - e.g. "abc @ gmail.com"
    if header["client_email"]:
        header["client_email"] = re.sub(r"\s+", "", header["client_email"])

    items = _parse_line_items(lines)

    return {"header": header, "items": items}


def parse_invoice_fields(ocr_text: str) -> dict:
    """
    Backward-compatible single-invoice entry point - treats the WHOLE
    document as one invoice. Kept for the standalone self-test below and
    any existing caller. New code that needs to handle multiple invoices
    per file should use parse_invoices_from_text() instead.
    """
    lines = [l for l in ocr_text.splitlines() if not _PAGE_MARKER_RE.match(l.strip())]
    return _parse_single_invoice(lines)


def parse_invoices_from_text(ocr_text: str) -> list[dict]:
    """
    Detects and parses MULTIPLE invoices that may appear in a single
    uploaded file (e.g. several invoices scanned/combined into one PDF).
    Returns a list of {"header": ..., "items": ...} dicts, one per
    detected invoice - always at least one, even if no clear boundary
    was found (falls back to treating the whole document as one invoice).
    """
    lines = [l for l in ocr_text.splitlines() if not _PAGE_MARKER_RE.match(l.strip())]
    segments = _split_into_invoice_segments(lines)
    return [_parse_single_invoice(segment) for segment in segments]


if __name__ == "__main__":
    # Quick manual test - run with:
    #   docker compose exec backend python -m app.services.field_extractor
    _sample_text = """--- Page 1 ---
INVOICE
QUMAXA IT SERVICES
(SMC-PRIVATE) LIMITED
qUMAXA
Invoice No.
INV-0001
Invoice Date
09/07/2026
 Invoice Type:
Product
24/07/2026
Due Date
Currency
PKR
BILL TO
PAYMENT DETAILS
Client Name:
Muhammad Qasim
Payment Terms: Due on receipt.
Client Company: _
Minimax Solutions Pvt Ltd
Bank:
Habib Metro Bank.
Client Address:
Shanti Naqar, Karachi
Account / IBAN:
 PK24 0000 -0171 40561976
Email / Phone:
abc @ gmail.com
SWIFT:
Item
Description
Qty.
Unit Price
Total Price
RAM
No 1 quality China 32GB
1800
1800
Mouse
A4 tech with pad
2
500
1000
Notes / Payment Instructions
Sub-Total
2800.00
Thank you for your business..
 Please quote the invoice number when making payment.
Tax treatment: apply the applicable rate according to the service/product classification Tax (18%)
504.00
and applicable law.
Discount
20.00
GRAND TOTAL
3284.00
Signature: (This is computer generated invoice and does not require signature)
Address: Suite No. F-25, Faraz Avenue, Gulistan-e-Johar, Block-20, Karachi, Pakistan | Contact: +92300-2276053 | Website: www.qumaxa.com
"""
    import json
    result = parse_invoice_fields(_sample_text)
    print(json.dumps(result, indent=2))