from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.api.v1 import auth, documents, extraction, exports, admin, visitor, billing, organizations
from app.core.limiter import limiter
from app.services import retention_service
import app.models.retention_notice  # noqa: F401  (registers the table)

app = FastAPI(title="OCRDocFlow API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: allows the React frontend (running on a different port/domain) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ocrdocflow.qumaxa.com",
        # The Android and iOS apps (Capacitor) load their pages from these
        # two built-in addresses - see deploy/MOBILE.md.
        "https://localhost",
        "capacitor://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the apps read the export's file name.
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(exports.router)
app.include_router(admin.router)
app.include_router(visitor.router)
app.include_router(billing.router)
app.include_router(organizations.router)


@app.on_event("startup")
def start_retention_job():
    # Warning emails and the day-after deletion of a closed period's
    # invoices; does nothing unless RETENTION_MODE says so.
    retention_service.start_background_job()


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}