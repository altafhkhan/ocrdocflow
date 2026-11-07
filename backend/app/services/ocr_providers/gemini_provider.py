"""
Google Gemini API as an OCR + invoice-extraction engine.

Why: Gemini's vision models read handwriting and mixed-script documents
(English + Arabic/Urdu on one page) far better than a classic OCR model,
and the API has a free tier that needs no credit card. We call the plain
REST endpoint with `requests` - no SDK to install.

Two ways to use it:
  extract_pages(images)     - plain transcription, one request per page
                              (the generic OCRProvider interface).
  extract_document(images)  - ONE request for the whole document that
                              returns the page texts AND the invoice
                              fields/line items as JSON. This is what the
                              upload routes use: the model sees the real
                              page, so it fills the review form far better
                              than regex rules over OCR text, and it costs
                              a single request against the free quota.

Free-tier caveats (checked 2026-11-07, aistudio.google.com/docs/pricing):
  - requests on the free tier may be used by Google to improve products,
    so do NOT send customer documents from production on the free tier;
  - each model has its own small daily quota. On HTTP 429/503 we retry
    the same request on the next model in `fallback_models` before giving
    up (and then ocr_service falls back to local PaddleOCR).
"""
import base64
import io
import json
import logging
import time

import requests
from PIL import Image

from .base import OCRProvider, OCRProviderError

logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

_LANGUAGE_NAMES = {
    "auto": "unknown (detect it)",
    "en": "English", "ar": "Arabic", "ur": "Urdu",
    "fr": "French", "de": "German", "es": "Spanish", "nl": "Dutch",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
}

_TRANSCRIBE_RULES = (
    "Transcription rules:\n"
    "- Plain text only: no markdown, no code fences, no commentary.\n"
    "- Keep the original reading order, one line of the page per output line. "
    "For tables, put one table row per line with cells separated by two spaces.\n"
    "- Copy numbers, dates, amounts, invoice numbers and codes character for "
    "character. Never round, reformat or correct them.\n"
    "- Keep the original language and script (do not translate). Right-to-left "
    "text must be written in normal logical order.\n"
    "- For Arabic/Urdu/Persian pages read each line right-to-left: write the label "
    "first and its value after it (e.g. 'رقم الفاتورة: INV-2201'), and write table "
    "rows starting from the right-most column.\n"
    "- For Chinese/Japanese/Korean keep full-width characters and vertical text "
    "in reading order; do not insert spaces inside words.\n"
    "- If a word is unreadable write [?] in its place.\n"
)

_PAGE_PROMPT = (
    "You are an OCR engine. Transcribe ALL text visible in this scanned page "
    "exactly as written, including handwriting, stamps and small print.\n"
    + _TRANSCRIBE_RULES +
    "- If the page has no text, output exactly: [no text]\n"
    "The document language is expected to be {language}, but transcribe whatever "
    "language actually appears."
)

_DOCUMENT_PROMPT = (
    "You are an OCR and invoice-data-entry engine. The attached images are the "
    "{n} page(s) of one uploaded document, in order. The language is expected to "
    "be {language}, but read whatever language actually appears.\n\n"
    "Do two things and return ONE JSON object:\n"
    "1. \"pages\": for every page, in order, its full transcription (including "
    "handwriting, stamps and small print) as one string, following these rules:\n"
    + _TRANSCRIBE_RULES +
    "   Use an empty string for a page with no text.\n"
    "2. \"invoices\": the invoices, bills or receipts in the document, in order. "
    "One document may hold several invoices and one invoice may span pages. "
    "For each one fill the fields below from what is PRINTED OR HANDWRITTEN; "
    "never invent a value - use null when it is not on the page.\n"
    "- invoice_number: the invoice / bill / receipt number.\n"
    "- invoice_date and due_date: exactly as written on the page.\n"
    "- currency: ISO code if shown or clearly implied (e.g. PKR, SAR, AED, USD); null if unknown.\n"
    "- client_name: the person the document is billed to / the customer. "
    "client_company: their company. client_email: their email. Keep names in "
    "the original script, do not translate.\n"
    "- items: one entry per line item with description (original script), qty, "
    "unit_price and total_price as plain numbers (no thousands separators, no "
    "currency symbols); null for a missing number.\n"
    "- sub_total, tax, discount, grand_total: plain numbers; grand_total is the "
    "final amount payable (net / total amount).\n"
    "If the document contains no invoice-like content at all, return an empty "
    "\"invoices\" list."
)

_NULLABLE_STR = {"type": "STRING", "nullable": True}
_NULLABLE_NUM = {"type": "NUMBER", "nullable": True}

_DOCUMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pages": {"type": "ARRAY", "items": {"type": "STRING"}},
        "invoices": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "invoice_number": _NULLABLE_STR,
                    "invoice_date": _NULLABLE_STR,
                    "due_date": _NULLABLE_STR,
                    "currency": _NULLABLE_STR,
                    "client_name": _NULLABLE_STR,
                    "client_company": _NULLABLE_STR,
                    "client_email": _NULLABLE_STR,
                    "sub_total": _NULLABLE_NUM,
                    "tax": _NULLABLE_NUM,
                    "discount": _NULLABLE_NUM,
                    "grand_total": _NULLABLE_NUM,
                    "items": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "description": _NULLABLE_STR,
                                "qty": _NULLABLE_NUM,
                                "unit_price": _NULLABLE_NUM,
                                "total_price": _NULLABLE_NUM,
                            },
                            "required": ["description", "qty", "unit_price", "total_price"],
                        },
                    },
                },
                "required": ["invoice_number", "invoice_date", "due_date", "currency",
                             "client_name", "client_company", "client_email",
                             "sub_total", "tax", "discount", "grand_total", "items"],
            },
        },
    },
    "required": ["pages", "invoices"],
}

_HEADER_STR_FIELDS = ("invoice_number", "invoice_date", "due_date", "currency",
                      "client_name", "client_company", "client_email")
_HEADER_NUM_FIELDS = ("sub_total", "tax", "discount", "grand_total")


def _image_part(image: Image.Image, max_side: int = 2000) -> dict:
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return {"inline_data": {"mime_type": "image/jpeg",
                            "data": base64.b64encode(buf.getvalue()).decode("ascii")}}


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _str(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _normalise_invoices(raw: list) -> list[dict]:
    """Coerce the model's JSON into the {"header": ..., "items": ...} shape
    that field_extractor.py produces, so the upload routes need no changes."""
    invoices = []
    for inv in raw or []:
        if not isinstance(inv, dict):
            continue
        header = {f: _str(inv.get(f)) for f in _HEADER_STR_FIELDS}
        header.update({f: _num(inv.get(f)) for f in _HEADER_NUM_FIELDS})
        items = []
        for item in inv.get("items") or []:
            if not isinstance(item, dict):
                continue
            items.append({
                "description": _str(item.get("description")),
                "qty": _num(item.get("qty")),
                "unit_price": _num(item.get("unit_price")),
                "total_price": _num(item.get("total_price")),
            })
        invoices.append({"header": header, "items": items})
    return invoices


class GeminiProvider(OCRProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL,
                 fallback_models: list[str] | None = None, timeout: int = 180):
        if not api_key:
            raise OCRProviderError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.fallback_models = [m for m in (fallback_models if fallback_models is not None
                                            else DEFAULT_FALLBACK_MODELS) if m and m != self.model]
        self.timeout = timeout

    # --- low-level call with retries + model fallback ------------------------
    def _generate(self, parts: list[dict], generation_config: dict) -> str:
        """Returns the concatenated text of the first candidate."""
        body = {"contents": [{"parts": parts}], "generationConfig": generation_config}
        last_error = "no models tried"
        for model in [self.model] + self.fallback_models:
            url = f"{_API_ROOT}/models/{model}:generateContent"
            delay = 4
            for attempt in range(3):
                try:
                    resp = requests.post(url, json=body, headers={"x-goog-api-key": self.api_key},
                                         timeout=self.timeout)
                except requests.RequestException as e:
                    last_error = f"{model}: request failed: {e}"
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        cand = data["candidates"][0]
                        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
                    except (KeyError, IndexError) as e:
                        raise OCRProviderError(f"Gemini {model}: unexpected response {str(data)[:300]}") from e
                    if model != self.model:
                        logger.info("Gemini: served by fallback model %s", model)
                    return text
                last_error = f"{model}: HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code in (429, 503):
                    # Quota / overload: one quick retry, then move to the next model.
                    if attempt == 0:
                        time.sleep(delay)
                        continue
                    break
                if resp.status_code in (500, 502, 504):
                    time.sleep(delay)
                    delay *= 2
                    continue
                break  # 400/401/403/404: retrying the same model will not help
            logger.warning("Gemini model %s unavailable (%s)", model, last_error[:160])
        raise OCRProviderError(f"Gemini: all models failed; last error {last_error}")

    # --- public API -----------------------------------------------------------
    def extract_pages(self, images: list[Image.Image], language: str) -> list[str]:
        prompt = _PAGE_PROMPT.format(language=_LANGUAGE_NAMES.get(language, language))
        config = {"temperature": 0.0, "maxOutputTokens": 8192,
                  "thinkingConfig": {"thinkingLevel": "low"}}
        pages = []
        for image in images:
            text = self._generate([_image_part(image), {"text": prompt}], config).strip()
            if text.startswith("```"):
                text = text.strip("`").strip()
            pages.append("" if text == "[no text]" else text)
        return pages

    def extract_document(self, images: list[Image.Image], language: str) -> tuple[list[str], list[dict]]:
        """
        One request for the whole document. Returns (page_texts, invoices)
        where invoices has the same shape as field_extractor output.
        """
        prompt = _DOCUMENT_PROMPT.format(n=len(images), language=_LANGUAGE_NAMES.get(language, language))
        parts = [_image_part(img) for img in images] + [{"text": prompt}]
        config = {"temperature": 0.0, "maxOutputTokens": 16384,
                  "thinkingConfig": {"thinkingLevel": "low"},
                  "responseMimeType": "application/json",
                  "responseSchema": _DOCUMENT_SCHEMA}
        raw = self._generate(parts, config)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise OCRProviderError(f"Gemini: response was not valid JSON ({e}): {raw[:200]}") from e
        pages = [str(p or "") for p in (data.get("pages") or [])]
        # Keep page count honest even if the model merged/dropped pages.
        pages = (pages + [""] * len(images))[:len(images)]
        return pages, _normalise_invoices(data.get("invoices"))
