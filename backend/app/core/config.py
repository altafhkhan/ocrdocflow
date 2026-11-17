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
    # Two ways to send. SMTP through your own mailbox is used when
    # SMTP_HOST is set; otherwise Resend when RESEND_API_KEY is set. With
    # neither, reset links are written to the server log, not emailed.
    # MAIL_FROM: for SMTP, the mailbox itself; for Resend, an address on a
    # domain verified there.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # "auto" = SSL on port 465, STARTTLS on any other port. Or force
    # "ssl" / "starttls" / "none" (none = unencrypted, local testing only).
    SMTP_SECURITY: str = "auto"
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
    # How many documents may be in OCR at the same moment. Further uploads
    # wait their turn (other requests are not held up). Each document in
    # progress keeps its page images in memory (up to ~120 MB for a
    # 10-page PDF), so raise this only with memory to spare.
    OCR_MAX_CONCURRENT: int = 6
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Tried in order when the main model answers 429 (quota) or 503 (busy);
    # each free-tier model has its own daily quota.
    GEMINI_FALLBACK_MODELS: str = "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""

    # --- AI cost monitoring, limits and caps (see services/ai_cost.py,
    #     services/usage_service.py and the Admin Panel's Usage tab) ---
    # Published price per 1 million tokens, "model:input:output" in USD.
    # Update when Google changes its price list; an unknown model is
    # charged at the dearest price listed here.
    AI_PRICES_USD_PER_MTOK: str = (
        "gemini-3.6-flash:0.75:3.75,gemini-3.5-flash:0.75:3.75,"
        "gemini-3.5-flash-lite:0.30:2.50,gemini-3.1-flash-lite:0.25:1.50"
    )
    # A long invoice counts as one plan invoice per this many line items.
    LINE_ITEMS_PER_INVOICE_UNIT: int = 25
    # Default monthly AI spending cap per customer, by plan (USD, calendar
    # month, 0 = no cap). One customer can be given its own cap in the
    # Admin Panel. Reaching the cap blocks further uploads that month.
    PLAN_COST_CAPS_USD: str = "free:0.50,starter:6,professional:20,business:50"
    # Monthly AI spending cap for the WHOLE platform, visitors included
    # (USD, 0 = no cap). Reaching it pauses all uploads until next month
    # or until this value is raised.
    PLATFORM_MONTHLY_COST_CAP_USD: float = 0
    # Alert emails go here when a customer or the platform passes
    # COST_ALERT_THRESHOLDS of its cap. Empty = alerts only in the API log.
    ALERT_EMAIL: str = ""
    COST_ALERT_THRESHOLDS: str = "0.8,1.0"

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

    # --- Loyalty coupon (see api/v1/billing.py) ---
    # Every paying customer gets one coupon code: LOYALTY_PERCENT_OFF off
    # the plan they are on, for the first LOYALTY_DURATION_MONTHS payments.
    # They may use it themselves or give it to someone who is not a customer
    # yet. It expires LOYALTY_VALID_MONTHS_AFTER_PLAN_END months after the
    # end of the customer's current plan period and works
    # LOYALTY_MAX_REDEMPTIONS time(s). Only ONE discount ever applies: while
    # the launch promotion is running, the bigger of the two is used.
    LOYALTY_COUPON_ENABLED: bool = True
    LOYALTY_PERCENT_OFF: int = 25
    LOYALTY_DURATION_MONTHS: int = 3
    LOYALTY_VALID_MONTHS_AFTER_PLAN_END: int = 2
    LOYALTY_MAX_REDEMPTIONS: int = 1

    class Config:
        env_file = ".env"


settings = Settings()