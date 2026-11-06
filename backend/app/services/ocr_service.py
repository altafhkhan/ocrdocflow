"""
This is the "reading" engine for OCRDocFlow.

Flow for one document:
  PDF or image file
      -> (if PDF) render each page as an image
      -> hand the page images to the configured OCR engine
         (settings.OCR_PROVIDER: "paddle" local, "gemini" or "azure" cloud -
          see app/services/ocr_providers/)
      -> combine all recognized text into one block, with "--- Page N ---"
         markers that field_extractor.py knows to skip

If a cloud engine fails (network, quota...) and OCR_FALLBACK_TO_PADDLE is
on, we fall back to the local PaddleOCR engine so an upload still works.
"""
import logging

import fitz  # PyMuPDF - reads PDF files
from PIL import Image

from app.core.config import settings
from app.services.ocr_providers import OCRProvider, OCRProviderError, build_provider

logger = logging.getLogger(__name__)

# Engines are built once and reused (PaddleOCR model loading is slow).
_providers: dict[str, OCRProvider] = {}


def get_pdf_page_count(file_path: str) -> int:
    """
    Quick page-count check, used by the upload endpoint to reject
    oversized PDFs BEFORE spending time/memory on OCR
    (see config.MAX_PDF_PAGES).
    """
    pdf = fitz.open(file_path)
    count = pdf.page_count
    pdf.close()
    return count


def pdf_to_images(file_path: str, dpi: int = 200) -> list[Image.Image]:
    images = []
    pdf = fitz.open(file_path)
    for page in pdf:
        # ~200 DPI - good balance of OCR accuracy vs speed/memory
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)
    pdf.close()
    return images


def load_page_images(file_path: str, real_type: str) -> list[Image.Image]:
    if real_type == "pdf":
        return pdf_to_images(file_path)
    return [Image.open(file_path).convert("RGB")]


def get_provider(name: str | None = None) -> OCRProvider:
    name = (name or settings.OCR_PROVIDER or "paddle").lower()
    if name not in _providers:
        _providers[name] = build_provider(
            name,
            api_key=settings.GEMINI_API_KEY if name == "gemini" else settings.AZURE_DI_KEY,
            model=settings.GEMINI_MODEL,
            endpoint=settings.AZURE_DI_ENDPOINT,
        )
    return _providers[name]


def join_pages(pages: list[str]) -> str:
    parts = []
    for page_number, text in enumerate(pages, start=1):
        text = (text or "").strip()
        if text:
            parts.append(f"--- Page {page_number} ---\n{text}")
    return "\n\n".join(parts)


def extract_text(file_path: str, real_type: str, language: str) -> tuple[str, int]:
    """
    Returns (extracted_text, page_count).
    Raises an exception if OCR fails - the caller is responsible for
    catching it and marking the document as "failed".
    """
    images = load_page_images(file_path, real_type)
    name = (settings.OCR_PROVIDER or "paddle").lower()
    try:
        pages = get_provider(name).extract_pages(images, language)
    except OCRProviderError as e:
        if name == "paddle" or not settings.OCR_FALLBACK_TO_PADDLE:
            raise
        logger.warning("OCR provider %s failed (%s); falling back to paddle", name, e)
        pages = get_provider("paddle").extract_pages(images, language)
    return join_pages(pages), len(images)
