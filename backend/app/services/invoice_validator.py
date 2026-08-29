"""
Phase 4 - Business Parser: validation rules.

These checks run right before saving to the permanent `invoices` /
`invoice_items` tables (see api/v1/extraction.py). They don't BLOCK
saving - OCR-extracted data isn't always perfectly clean, and the human
reviewing it is the final authority - but they surface likely problems
so mistakes don't slip through silently.

Each check returns a dict:
    {"level": "warning", "field": "...", "message": "..."}

MVP scope (3 checks, per product decision - more can be added later):
  1) Math totals: do line items add up to Sub-Total? Does
     Sub-Total + Tax - Discount = Grand Total?
  2) Missing required fields
  3) Duplicate invoice number for this user (see check_duplicate_invoice -
     lives separately since it needs a database query, called directly
     from the API layer rather than from here)
"""
from typing import Optional


def _money(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_math_totals(header: dict, items: list[dict]) -> list[dict]:
    warnings = []
    sub_total = _money(header.get("sub_total"))
    tax = _money(header.get("tax")) or 0.0
    discount = _money(header.get("discount")) or 0.0
    grand_total = _money(header.get("grand_total"))

    # Check 1: do the line items add up to the Sub-Total?
    item_totals = [_money(i.get("total_price")) for i in items]
    if items and all(t is not None for t in item_totals):
        items_sum = sum(item_totals)
        if sub_total is not None and abs(items_sum - sub_total) > 0.01:
            warnings.append({
                "level": "warning",
                "field": "sub_total",
                "message": f"Line items add up to {items_sum:.2f}, but Sub-Total is {sub_total:.2f}.",
            })
    elif items:
        warnings.append({
            "level": "warning",
            "field": "sub_total",
            "message": "Could not verify Sub-Total - one or more line items is missing a Total Price.",
        })

    # Check 2: Sub-Total + Tax - Discount = Grand Total?
    if sub_total is not None and grand_total is not None:
        expected = sub_total + tax - discount
        if abs(expected - grand_total) > 0.01:
            warnings.append({
                "level": "warning",
                "field": "grand_total",
                "message": f"Expected Grand Total to be {expected:.2f} "
                           f"(Sub-Total + Tax - Discount), but it's {grand_total:.2f}.",
            })

    return warnings


def check_required_fields(header: dict) -> list[dict]:
    required = {
        "invoice_number": "Invoice Number",
        "invoice_date": "Invoice Date",
        "client_name": "Client Name",
        "grand_total": "Grand Total",
    }
    warnings = []
    for field, label in required.items():
        value = header.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            warnings.append({
                "level": "warning",
                "field": field,
                "message": f"{label} is missing.",
            })
    return warnings


def validate_invoice(header: dict, items: list[dict]) -> list[dict]:
    """
    Runs the offline checks (no database needed). Duplicate-invoice
    checking is separate since it needs a database query - see
    check_duplicate_invoice() called directly from the API layer.
    """
    return check_math_totals(header, items) + check_required_fields(header)


if __name__ == "__main__":
    # Quick manual test using our known-good real invoice data.
    # Run with: docker compose exec backend python -m app.services.invoice_validator
    import json

    good_header = {
        "invoice_number": "INV-0001", "invoice_date": "09/07/2026",
        "client_name": "Muhammad Qasim", "sub_total": 2800.00,
        "tax": 504.00, "discount": 20.00, "grand_total": 3284.00,
    }
    good_items = [{"total_price": 1800.00}, {"total_price": 1000.00}]

    print("Should be empty (all correct):")
    print(json.dumps(validate_invoice(good_header, good_items), indent=2))

    print("\nShould show 1 warning (bad math on grand total):")
    bad_header = dict(good_header, grand_total=9999.00)
    print(json.dumps(validate_invoice(bad_header, good_items), indent=2))

    print("\nShould show 1 warning (missing field):")
    missing_header = dict(good_header, client_name=None)
    print(json.dumps(validate_invoice(missing_header, good_items), indent=2))