"""
Password-reset flow, end to end against an in-memory app.

Run from backend/ (needs fastapi, sqlalchemy, python-jose, passlib, bcrypt,
slowapi, pydantic[email], pydantic-settings, requests, httpx, python-multipart):

    python tests/test_password_reset.py

Uses a throwaway SQLite file and mounts only the auth router, so it needs
neither Postgres nor the OCR stack. No email is sent: RESEND_API_KEY is
empty, and the test reads the link the endpoint would have emailed by
capturing email_service.send_email.
"""
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["FRONTEND_URL"] = "https://app.example.test"
os.environ["RESEND_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.organization  # noqa: E402,F401  (registers the mapper User relates to)
from app.api.v1 import auth  # noqa: E402
from app.core import security  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, engine  # noqa: E402
from app.services import email_service  # noqa: E402

Base.metadata.create_all(bind=engine)
limiter.enabled = False  # rate limits are checked separately at the end
api = FastAPI()
api.state.limiter = limiter
api.include_router(auth.router)
client = TestClient(api)

sent: list[dict] = []
email_service.send_email = lambda to, subject, text, html=None: sent.append({"to": to, "text": text}) or True

EMAIL, OLD, NEW = "user@example.com", "old-password-1", "new-password-2"


def token_from_last_email() -> str:
    link = [w for w in sent[-1]["text"].split() if "reset-password?token=" in w][0]
    assert link.startswith("https://app.example.test/reset-password?token="), link
    return link.split("token=", 1)[1]


def login(password: str) -> int:
    return client.post("/api/v1/auth/login", data={"username": EMAIL, "password": password}).status_code


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        sys.exit(1)


r = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": OLD, "full_name": "Test User"})
check("register", r.status_code == 201)
check("login with old password", login(OLD) == 200)

# unknown email: same answer, nothing sent
r1 = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
check("unknown email answers 200 and sends nothing", r1.status_code == 200 and len(sent) == 0)

r2 = client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
check("known email answers 200 with the same message", r2.status_code == 200 and r2.json() == r1.json())
check("one email sent to the account", len(sent) == 1 and sent[0]["to"] == EMAIL)
token = token_from_last_email()

check("reset token is not accepted as a login token",
      client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401)
access = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": OLD}).json()["access_token"]
check("login token is not accepted as a reset token",
      client.post("/api/v1/auth/reset-password", json={"token": access, "new_password": NEW}).status_code == 400)

check("short password refused",
      client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 400)
check("garbage token refused",
      client.post("/api/v1/auth/reset-password", json={"token": "abc.def.ghi", "new_password": NEW}).status_code == 400)

r = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW})
check("valid token changes the password", r.status_code == 200)
check("old password no longer works", login(OLD) == 401)
check("new password works", login(NEW) == 200)
check("same link cannot be used twice",
      client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "another-pass-3"}).status_code == 400)
check("password unchanged after the replay", login(NEW) == 200)

# expired link
real_minutes = security.settings.PASSWORD_RESET_EXPIRE_MINUTES
security.settings.PASSWORD_RESET_EXPIRE_MINUTES = -1
client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
security.settings.PASSWORD_RESET_EXPIRE_MINUTES = real_minutes
check("expired link refused",
      client.post("/api/v1/auth/reset-password",
                  json={"token": token_from_last_email(), "new_password": "another-pass-3"}).status_code == 400)

# rate limit on requesting links: 3 per 15 minutes per address
limiter.enabled = True
codes = [client.post("/api/v1/auth/forgot-password", json={"email": EMAIL}).status_code for _ in range(4)]
check(f"4th reset request within 15 minutes is rate-limited {codes}", codes == [200, 200, 200, 429])
other = client.post("/api/v1/auth/forgot-password", json={"email": EMAIL}, headers={"X-Real-IP": "203.0.113.9"})
check("another visitor (different X-Real-IP) is not affected by that limit", other.status_code == 200)

print("\nAll password-reset checks passed.")
