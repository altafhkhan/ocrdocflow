"""
All app settings live here, and they are loaded from the .env file.
This means secrets (passwords, keys) never get hardcoded into the code
or committed to Git - this follows Section 22 (Secret Management) of the
OCR SaaS Platform Security Policy.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_UPLOAD_SIZE_MB: int = 10
    # MVP limit - synchronous OCR processing (one request = one document,
    # start to finish) isn't safe for very large multi-page files yet.
    # True bulk support needs a background job queue - see roadmap.
    MAX_PDF_PAGES: int = 10
    UPLOAD_DIR: str = "./uploaded_files"

    # Where Stripe redirects the browser back to after checkout - and any
    # other place the backend needs to build a link back to the frontend.
    FRONTEND_URL: str = "http://localhost:5173"

    # Stripe (test mode keys while developing - Section 22, never
    # hardcoded, always loaded from .env)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # --- OCR engine (see app/services/ocr_providers/) ---
    # "gemini" = Google Gemini API (default; needs GEMINI_API_KEY, else we
    #            quietly fall back to paddle).
    # "paddle" = local PaddleOCR (offline, weaker on handwriting).
    # "azure"  = Azure AI Document Intelligence read model
    #            (needs AZURE_DI_ENDPOINT + AZURE_DI_KEY).
    OCR_PROVIDER: str = "gemini"
    # If a cloud engine errors out, retry the document with local PaddleOCR
    # instead of failing the upload.
    OCR_FALLBACK_TO_PADDLE: bool = True
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Tried in order when the main model answers 429 (quota) or 503 (busy);
    # each free-tier model has its own daily quota.
    GEMINI_FALLBACK_MODELS: str = "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()