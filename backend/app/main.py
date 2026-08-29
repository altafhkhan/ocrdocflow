from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.api.v1 import auth, documents, extraction, exports, admin, visitor, billing, organizations
from app.core.limiter import limiter

app = FastAPI(title="OCRDocFlow API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: allows the React frontend (running on a different port) to call this API.
# In production, replace "*" with your real frontend domain only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(exports.router)
app.include_router(admin.router)
app.include_router(visitor.router)
app.include_router(billing.router)
app.include_router(organizations.router)


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}