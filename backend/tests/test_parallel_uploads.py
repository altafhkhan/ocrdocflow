"""
Uploads must not freeze the server, and several must be processed at once.

Run from backend/ (same packages as test_password_reset.py):

    python tests/test_parallel_uploads.py

Regression test for: "the server processes one upload at a time; while it
works, other users' requests wait". The upload endpoints were `async def`
but called the blocking OCR directly, which stalled the whole event loop.

A real uvicorn server is started (the in-process TestClient would hide the
problem), with a fake OCR engine that just sleeps for one second.
"""
import io
import os
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["UPLOAD_DIR"] = str(Path(_tmp, "uploads"))
os.environ["OCR_PROVIDER"] = "gemini"
os.environ["OCR_MAX_CONCURRENT"] = "2"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from PIL import Image  # noqa: E402

import app.models.organization  # noqa: E402,F401
from app.api.v1 import auth, documents  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, engine  # noqa: E402
from app.services import ocr_service, usage_service  # noqa: E402

OCR_SECONDS = 1.0
UPLOADS = 4


class SlowFakeEngine:
    """Stands in for Gemini: waits, then returns one invoice."""
    in_flight = 0
    max_in_flight = 0
    lock = threading.Lock()

    def extract_document(self, images, language):
        with self.lock:
            SlowFakeEngine.in_flight += 1
            SlowFakeEngine.max_in_flight = max(SlowFakeEngine.max_in_flight, SlowFakeEngine.in_flight)
        time.sleep(OCR_SECONDS)
        with self.lock:
            SlowFakeEngine.in_flight -= 1
        return ["Invoice No: T-1"], [{"header": {"invoice_number": "T-1"}, "items": []}], "en"


ocr_service.get_provider = lambda name=None: SlowFakeEngine()
# SQLite hands back timezone-less dates, which the billing-period maths
# (written for Postgres) cannot subtract; pin the period start instead.
usage_service.get_period_start = lambda org: datetime(2020, 1, 1, tzinfo=timezone.utc)

Base.metadata.create_all(bind=engine)
limiter.enabled = False
api = FastAPI()
api.state.limiter = limiter
api.include_router(auth.router)
api.include_router(documents.router)


@api.get("/ping")
async def ping():
    return {"ok": True}


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name, flush=True)
    if not ok:
        os._exit(1)


with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
base = f"http://127.0.0.1:{port}"
for _ in range(100):
    try:
        requests.get(base + "/ping", timeout=1)
        break
    except requests.RequestException:
        time.sleep(0.1)

requests.post(base + "/api/v1/auth/register", json={"email": "u@example.com", "password": "password-1"})
token = requests.post(base + "/api/v1/auth/login",
                      data={"username": "u@example.com", "password": "password-1"}).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

buf = io.BytesIO()
Image.new("RGB", (60, 40), "white").save(buf, format="PNG")
png = buf.getvalue()

statuses: list = []


def upload():
    r = requests.post(base + "/api/v1/documents/upload", headers=H,
                      files={"file": ("scan.png", png, "image/png")}, data={"language": "en"}, timeout=60)
    statuses.append((r.status_code, r.json().get("status") if r.status_code == 200 else r.text[:200]))


started = time.time()
threads = [threading.Thread(target=upload) for _ in range(UPLOADS)]
for t in threads:
    t.start()

time.sleep(0.4)  # uploads are now inside the fake OCR
t0 = time.time()
ping_ok = requests.get(base + "/ping", timeout=30).status_code == 200
ping_seconds = time.time() - t0
t0 = time.time()
list_ok = requests.get(base + "/api/v1/documents/", headers=H, timeout=30).status_code == 200
list_seconds = time.time() - t0

for t in threads:
    t.join()
total = time.time() - started
print(f"      {UPLOADS} uploads of {OCR_SECONDS:.0f}s each took {total:.1f}s; "
      f"ping {ping_seconds:.2f}s, document list {list_seconds:.2f}s; "
      f"most in OCR at once: {SlowFakeEngine.max_in_flight}", flush=True)

check("every upload succeeded", statuses == [(200, "done")] * UPLOADS)
check("a simple request is answered while uploads are in OCR", ping_ok and ping_seconds < 0.5)
check("a database request is answered while uploads are in OCR", list_ok and list_seconds < 0.8)
check("uploads ran in parallel (faster than one after another)", total < UPLOADS * OCR_SECONDS - 1.0)
check("OCR_MAX_CONCURRENT is respected (2 at a time)", SlowFakeEngine.max_in_flight == 2)
print("All parallel-upload checks passed.", flush=True)
os._exit(0)
