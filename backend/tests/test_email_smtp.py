"""
SMTP sending, against a real SMTP server started locally for the test.

Run from backend/ (needs the packages listed in test_password_reset.py
plus aiosmtpd):

    python tests/test_email_smtp.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///unused.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-a-real-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiosmtpd.controller import Controller  # noqa: E402
from aiosmtpd.smtp import AuthResult, LoginPassword  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.services import email_service  # noqa: E402

received: list = []


class Handler:
    async def handle_DATA(self, server, session, envelope):
        received.append(envelope)
        return "250 OK"


def authenticator(server, session, envelope, mechanism, auth_data):
    ok = isinstance(auth_data, LoginPassword) and auth_data.login == b"box@example.test" and auth_data.password == b"right-password"
    return AuthResult(success=ok)


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        controller.stop()
        sys.exit(1)


controller = Controller(Handler(), hostname="127.0.0.1", port=8925,
                        authenticator=authenticator, auth_required=True, auth_require_tls=False)
controller.start()

settings.RESEND_API_KEY = ""
settings.SMTP_HOST = ""
check("nothing configured -> not sent", email_service.email_provider() is None
      and email_service.send_email("a@example.test", "s", "t") is False)

settings.RESEND_API_KEY = "re_dummy"
check("only Resend configured -> provider is resend", email_service.email_provider() == "resend")

settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_SECURITY = "127.0.0.1", 8925, "none"
settings.SMTP_USERNAME, settings.SMTP_PASSWORD = "box@example.test", "right-password"
settings.MAIL_FROM = "OCRDocFlow <box@example.test>"
check("SMTP_HOST set -> provider is smtp (wins over Resend)", email_service.email_provider() == "smtp")

ok = email_service.send_email("user@example.test", "Reset your OCRDocFlow password",
                              "plain body https://app.example.test/reset-password?token=abc", "<p>html body</p>")
check("message accepted by the SMTP server", ok and len(received) == 1)
env = received[0]
content = env.content.decode("utf-8", errors="replace")
check("envelope sender and recipient", env.mail_from == "box@example.test" and env.rcpt_tos == ["user@example.test"])
check("subject, From, Date and Message-ID headers present",
      "Subject: Reset your OCRDocFlow password" in content and "From: OCRDocFlow <box@example.test>" in content
      and "Date: " in content and "Message-ID: <" in content and "@example.test>" in content)
check("both plain-text and HTML parts present",
      "multipart/alternative" in content and "plain body" in content and "<p>html body</p>" in content)

settings.SMTP_PASSWORD = "wrong-password"
check("wrong password -> returns False, does not raise",
      email_service.send_email("user@example.test", "s", "t") is False and len(received) == 1)

settings.SMTP_PASSWORD, settings.SMTP_PORT = "right-password", 8926  # nothing listens here
check("unreachable server -> returns False, does not raise",
      email_service.send_email("user@example.test", "s", "t") is False)

controller.stop()
print("\nAll SMTP email checks passed.")
