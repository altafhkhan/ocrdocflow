"""
Azure AI Document Intelligence (prebuilt-read) as an OCR engine.

Purpose-built OCR: returns lines in reading order with confidence, handles
printed text in 300+ languages and HANDWRITING in English, Arabic, French,
German, Spanish, Italian, Portuguese, Russian, Chinese, Japanese, Korean
and Thai (v4.0 docs). Free F0 tier: 500 pages/month, max 4 MB per request,
only the first 2 pages of a request are analysed, 1 request/second.
Because of the 2-page cap we send ONE page image per request.

REST only (no SDK): POST ...:analyze -> 202 + Operation-Location, then poll.
"""
import base64
import io
import time

import requests
from PIL import Image

from .base import OCRProvider, OCRProviderError

_API_VERSION = "2024-11-30"


def _image_to_jpeg_bytes(image: Image.Image, max_side: int = 2200) -> bytes:
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class AzureReadProvider(OCRProvider):
    name = "azure"

    def __init__(self, endpoint: str, api_key: str, timeout: int = 60):
        if not endpoint or not api_key:
            raise OCRProviderError("AZURE_DI_ENDPOINT / AZURE_DI_KEY are not set")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _analyze(self, image: Image.Image) -> str:
        url = (f"{self.endpoint}/documentintelligence/documentModels/prebuilt-read:analyze"
               f"?api-version={_API_VERSION}")
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        body = {"base64Source": base64.b64encode(_image_to_jpeg_bytes(image)).decode("ascii")}
        for attempt in range(4):
            resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code == 429 and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            break
        if resp.status_code != 202:
            raise OCRProviderError(f"Azure HTTP {resp.status_code}: {resp.text[:300]}")
        op_url = resp.headers.get("Operation-Location")
        if not op_url:
            raise OCRProviderError("Azure: no Operation-Location header")
        for _ in range(60):
            time.sleep(1.5)
            poll = requests.get(op_url, headers=headers, timeout=self.timeout)
            if poll.status_code == 429:
                continue
            if poll.status_code != 200:
                raise OCRProviderError(f"Azure poll HTTP {poll.status_code}: {poll.text[:300]}")
            data = poll.json()
            status = data.get("status")
            if status == "succeeded":
                result = data.get("analyzeResult", {})
                lines = []
                for page in result.get("pages", []):
                    for line in page.get("lines", []):
                        lines.append(line.get("content", ""))
                if lines:
                    return "\n".join(lines)
                return result.get("content", "")
            if status == "failed":
                raise OCRProviderError(f"Azure analysis failed: {str(data.get('error'))[:300]}")
        raise OCRProviderError("Azure: timed out waiting for result")

    def extract_pages(self, images: list[Image.Image], language: str) -> list[str]:
        return [self._analyze(image) for image in images]
