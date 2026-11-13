"""
Transactional email (password reset today; team invites later).

Two ways to send, chosen by what is configured in backend/.env:

1. Your own mailbox over SMTP - used when SMTP_HOST is set:

       SMTP_HOST=mail.example.com
       SMTP_PORT=465                 (465 = SSL, 587 = STARTTLS)
       SMTP_USERNAME=no-reply@example.com
       SMTP_PASSWORD=...
       MAIL_FROM=OCRDocFlow <no-reply@example.com>

   MAIL_FROM should be the mailbox itself (or an alias of it), otherwise
   most mail hosts refuse or the message lands in spam.

2. Resend's REST API (https://resend.com) - used when SMTP_HOST is empty
   and RESEND_API_KEY is set (a sending-only key is enough; MAIL_FROM must
   be on a domain verified in Resend).

With neither configured nothing is sent: send_email() returns False and
the caller decides what to do (the password-reset endpoint writes the link
to the server log so an operator can still help a locked-out user).
Nothing here raises - a mail outage must never turn into a 500.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
SMTP_TIMEOUT_SECONDS = 20


def email_provider() -> str | None:
    """'smtp', 'resend', or None when no way to send is configured."""
    if settings.SMTP_HOST and settings.MAIL_FROM:
        return "smtp"
    if settings.RESEND_API_KEY and settings.MAIL_FROM:
        return "resend"
    return None


def email_configured() -> bool:
    return email_provider() is not None


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    provider = email_provider()
    if provider == "smtp":
        return _send_smtp(to, subject, text, html)
    if provider == "resend":
        return _send_resend(to, subject, text, html)
    return False


def _send_smtp(to: str, subject: str, text: str, html: str | None) -> bool:
    msg = EmailMessage()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    sender_domain = parseaddr(settings.MAIL_FROM)[1].rpartition("@")[2] or None
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    host, port = settings.SMTP_HOST, settings.SMTP_PORT
    security = (settings.SMTP_SECURITY or "auto").lower()
    if security == "auto":
        security = "ssl" if port == 465 else "starttls"
    try:
        if security == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        # str(exc) carries the server's own reason (bad login, sender
        # refused, connection blocked) and never the password.
        logger.error("SMTP send to %s via %s:%s failed: %s", to, host, port, exc)
        return False


def _send_resend(to: str, subject: str, text: str, html: str | None) -> bool:
    payload = {"from": settings.MAIL_FROM, "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    try:
        resp = requests.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            timeout=15,
        )
        if resp.status_code >= 300:
            logger.error("Resend rejected email to %s: %s %s", to, resp.status_code, resp.text[:300])
            return False
        return True
    except requests.RequestException:
        logger.exception("Could not reach Resend for email to %s", to)
        return False
