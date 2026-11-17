"""
What an upload costs us in AI processing, and how many plan "invoices" it
uses up.

Cost: the Gemini API reports the tokens it billed with every answer
(usageMetadata). Tokens x the model's published price = our cost for that
upload. Prices live in settings.AI_PRICES_USD_PER_MTOK so they can be
changed when Google changes them, without touching code.

Billable invoices: plans are sold per invoice, but an invoice with 100
line items costs roughly ten times a normal one to read. So a long
invoice counts as one plan invoice per LINE_ITEMS_PER_INVOICE_UNIT line
items (25 by default: 1-25 lines = 1, 26-50 = 2, ... 76-100 = 4).
"""
import logging
import math

from app.core.config import settings

logger = logging.getLogger("ocrdocflow.ai_cost")


def _price_table() -> dict[str, tuple[float, float]]:
    """'model:input:output,...' -> {model: (usd per 1M input, usd per 1M output)}."""
    table: dict[str, tuple[float, float]] = {}
    for entry in (settings.AI_PRICES_USD_PER_MTOK or "").split(","):
        parts = [p.strip() for p in entry.split(":")]
        if len(parts) != 3:
            continue
        try:
            table[parts[0]] = (float(parts[1]), float(parts[2]))
        except ValueError:
            logger.warning("Ignoring malformed AI price entry %r", entry)
    return table


def price_for(model: str | None) -> tuple[float, float]:
    """Price of `model`; an unknown model is charged at the dearest known
    price so the estimate errs on the high side, never the low one."""
    table = _price_table()
    if not table:
        return (0.0, 0.0)
    if model:
        if model in table:
            return table[model]
        # The API reports e.g. "gemini-3.6-flash-001" for "gemini-3.6-flash".
        for name in sorted(table, key=len, reverse=True):
            if model.startswith(name):
                return table[name]
    return max(table.values(), key=lambda p: p[1])


def cost_usd(model: str | None, input_tokens: int | None, output_tokens: int | None) -> float:
    price_in, price_out = price_for(model)
    return round(((input_tokens or 0) * price_in + (output_tokens or 0) * price_out) / 1_000_000, 6)


def invoice_units(line_item_count: int) -> int:
    """How many plan invoices ONE invoice with this many line items uses."""
    per_unit = max(1, settings.LINE_ITEMS_PER_INVOICE_UNIT)
    return max(1, math.ceil(line_item_count / per_unit))


def billable_invoices(invoices: list[dict]) -> int:
    """Plan invoices used by a whole document ({"header", "items"} dicts)."""
    return sum(invoice_units(len(inv.get("items") or [])) for inv in invoices)


def big_invoice_notice(invoices: list[dict]) -> str | None:
    """Plain-English note for the uploader when long invoices cost extra."""
    billable = billable_invoices(invoices)
    if billable <= len(invoices):
        return None
    per_unit = max(1, settings.LINE_ITEMS_PER_INVOICE_UNIT)
    longest = max(len(inv.get("items") or []) for inv in invoices)
    found = "1 invoice" if len(invoices) == 1 else f"{len(invoices)} invoices"
    return (
        f"This document has {found} but used {billable} invoices of your plan: an invoice "
        f"with more than {per_unit} line items counts as 1 invoice for every {per_unit} line "
        f"items (the longest one here has {longest} line items)."
    )
