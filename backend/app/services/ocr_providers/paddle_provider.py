"""
Local PaddleOCR engine - the original OCRDocFlow reader, unchanged in
behaviour. Imported lazily so the API (and the comparison script) can run
on machines without paddlepaddle installed when another provider is used.
"""
import re
import numpy as np
from PIL import Image, ImageOps, ImageFilter

from .base import OCRProvider, OCRProviderError

SUPPORTED_LANGUAGES = {"en": "en", "ar": "ar"}

_MIN_WIDTH_FOR_OCR = 1600
_MAX_UPSCALE_FACTOR = 2.0

# PaddleOCR's Arabic model emits each line's characters in left-to-right
# visual order; reversing lines that contain Arabic recovers readable text.
_ARABIC_CHAR_RE = re.compile(r"[؀-ۿ]")

_engines: dict = {}


def _fix_rtl_line(text: str) -> str:
    if _ARABIC_CHAR_RE.search(text):
        return text[::-1]
    return text


def _preprocess_image(image: Image.Image) -> Image.Image:
    if image.width < _MIN_WIDTH_FOR_OCR:
        factor = min(_MAX_UPSCALE_FACTOR, _MIN_WIDTH_FOR_OCR / image.width)
        image = image.resize((int(image.width * factor), int(image.height * factor)), Image.LANCZOS)
    image = ImageOps.autocontrast(image, cutoff=1)
    return image.filter(ImageFilter.SHARPEN)


def _get_engine(language: str):
    try:
        from paddleocr import PaddleOCR
    except ImportError as e:  # pragma: no cover
        raise OCRProviderError("paddleocr is not installed in this environment") from e
    lang_code = SUPPORTED_LANGUAGES.get(language, "en")
    if lang_code not in _engines:
        _engines[lang_code] = PaddleOCR(use_angle_cls=True, lang=lang_code, show_log=False)
    return _engines[lang_code]


class PaddleProvider(OCRProvider):
    name = "paddle"

    def extract_pages(self, images: list[Image.Image], language: str) -> list[str]:
        engine = _get_engine(language)
        pages = []
        for image in images:
            image = _preprocess_image(image)
            result = engine.ocr(np.array(image), cls=True)
            lines = [_fix_rtl_line(line[1][0]) for line in (result[0] or [])]
            pages.append("\n".join(lines))
        return pages
