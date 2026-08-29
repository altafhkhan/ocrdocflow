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

    # Stripe (test mode keys while developing - Section 22, never
    # hardcoded, always loaded from .env)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    class Config:
        env_file = ".env"


settings = Settings()