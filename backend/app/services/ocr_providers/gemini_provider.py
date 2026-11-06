"""
Google Gemini API as an OCR engine.

Why: Gemini's vision models read handwriting and mixed-script documents
(English + Arabic/Urdu on one page) far better than a classic OCR model,
and the API has a free tier that needs no credit card. We call the plain
REST endpoint with `requests` - no SDK to install.

Free-tier caveats (checked 2026-11-07, aistudio.google.com/docs/pricing):
  - requests on the free tier may be used by Google to improve products,
    so do NOT send customer documents from production on the free tier;
  - rate limits are low (a handful of requests per minute).

Each page is sent as one request. The model is told to transcribe only
(no summarising, no translation), keep reading order and keep numbers
exactly as printed - that is what field_extractor.py depends on.
"""
import base64
import io
import time

import requests
from PIL import Image

from .base import OCRProvider, OCRProviderError

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

_LANGUAGE_NAMES = {"en": "English", "ar": "Arabic", "ur": "Urdu", "auto": "unknown (detect it)"}

_PROMPT = (
    "You are an OCR engine. Transcribe ALL text visible in this scanned page "
    "exactly as written, including handwriting, stamps and small print.\n"
    "Rules:\n"
    "- Output plain text only: no markdown, no code fences, no commentary.\n"
    "- Keep the original reading order, one line of the page per output line. "
    "For tables, put one table row per line with cells separated by two spaces.\n"
    "- Copy numbers, dates, amounts, invoice numbers and codes character for "
    "character. Never round, reformat or correct them.\n"
    "- Keep the original language and script (do not translate). Right-to-left "
    "text must be written in normal logical order.\n"
    "- For Arabic/Urdu/Persian pages read each line right-to-left: write the label "
    "first and its value after it (e.g. 'رقم الفاتورة: INV-2201'), and write table "
    "rows starting from the right-most column.\n"
    "- If a word is unreadable write [?] in its place.\n"
    "- If the page has no text, output exactly: [no text]\n"
    "The document language is expected to be {language}, but transcribe whatever "
    "language actually appears."
)


def _image_to_jpeg_b64(image: Image.Image, max_side: int = 2000) -> str:
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class GeminiProvider(OCRProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash", timeout: int = 180):
        if not api_key:
            raise OCRProviderError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _call(self, image: Image.Image, language: str) -> str:
        url = f"{_API_ROOT}/models/{self.model}:generateContent"
        body = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": _image_to_jpeg_b64(image)}},
                    {"text": _PROMPT.format(language=_LANGUAGE_NAMES.get(language, language))},
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 8192,
                # Transcription needs no long "thinking" phase; keeping it low
                # makes responses fast and avoids read timeouts.
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        # Simple retry for free-tier rate limiting (HTTP 429), transient 5xx
        # and network timeouts.
        delay = 5
        resp = None
        for attempt in range(4):
            try:
                resp = requests.post(url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == 3:
                    raise OCRProviderError(f"Gemini request failed: {e}") from e
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            break
        if resp.status_code != 200:
            raise OCRProviderError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise OCRProviderError(f"Gemini: unexpected response {str(data)[:300]}") from e
        text = "".join(p.get("text", "") for p in parts).strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
        if text == "[no text]":
            text = ""
        return text

    def extract_pages(self, images: list[Image.Image], language: str) -> list[str]:
        return [self._call(image, language) for image in images]
