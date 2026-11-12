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

    # --- Email (password reset) - see app/services/email_service.py ---
    # Resend API key (sending-only is enough) and the From address on a
    # domain verified in Resend. Leave RESEND_API_KEY empty and reset
    # links are written to the server log instead of being emailed.
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "OCRDocFlow <no-reply@qumaxa.com>"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

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

    # --- Launch promotion (see api/v1/billing.py) ---
    # A Stripe coupon is created once (found again by metadata) and applied
    # automatically at checkout while seats remain. Stripe itself enforces
    # the seat limit and the end date.
    PROMO_ENABLED: bool = True
    PROMO_NAME: str = "Launch offer"
    PROMO_PERCENT_OFF: int = 50
    PROMO_MAX_REDEMPTIONS: int = 50
    # "forever" (every invoice of the subscription), "once" (first invoice
    # only) or "repeating" (PROMO_DURATION_MONTHS invoices).
    PROMO_DURATION: str = "forever"
    PROMO_DURATION_MONTHS: int = 3
    # Optional ISO date (e.g. 2026-12-31) after which the offer stops.
    PROMO_ENDS_AT: str = ""

    class Config:
        env_file = ".env"


settings = Settings()