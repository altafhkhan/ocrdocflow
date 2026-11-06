from PIL import Image


class OCRProviderError(Exception):
    """Raised when an OCR engine fails (network, quota, bad response...)."""


class OCRProvider:
    name: str = "base"

    def extract_pages(self, images: list[Image.Image], language: str) -> list[str]:
        """
        Turn page images into one text block per page (same order).
        `language` is the user's dropdown choice ("en", "ar", ...) - a hint
        only; cloud engines auto-detect and may ignore it.
        """
        raise NotImplementedError
