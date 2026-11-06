"""
Pluggable OCR engines for OCRDocFlow.

ocr_service.py decides WHICH engine to use (via settings.OCR_PROVIDER) and
handles the file -> page images part. Each provider here only has to turn
a list of page images into a list of page texts.

Providers:
  paddle  - the original local PaddleOCR engine (free, offline, weaker on
            handwriting). Always available as a fallback.
  gemini  - Google Gemini API (vision model). Free tier, no card needed.
            Strong on handwriting and mixed-language documents.
  azure   - Azure AI Document Intelligence "prebuilt-read". Free F0 tier
            (500 pages/month, first 2 pages per request). Purpose-built OCR
            with 12 handwriting languages incl. English and Arabic.
"""
from .base import OCRProvider, OCRProviderError

__all__ = ["OCRProvider", "OCRProviderError", "build_provider"]


def build_provider(name: str, **kwargs) -> OCRProvider:
    name = (name or "paddle").strip().lower()
    if name == "paddle":
        from .paddle_provider import PaddleProvider
        return PaddleProvider()
    if name == "gemini":
        from .gemini_provider import GeminiProvider
        fallbacks = kwargs.get("fallback_models")
        if isinstance(fallbacks, str):
            fallbacks = [m.strip() for m in fallbacks.split(",") if m.strip()]
        return GeminiProvider(api_key=kwargs.get("api_key", ""), model=kwargs.get("model") or None,
                              fallback_models=fallbacks)
    if name == "azure":
        from .azure_provider import AzureReadProvider
        return AzureReadProvider(endpoint=kwargs.get("endpoint", ""), api_key=kwargs.get("api_key", ""))
    raise ValueError(f"Unknown OCR provider: {name!r}")
