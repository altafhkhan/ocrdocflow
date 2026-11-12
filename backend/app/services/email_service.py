"""
Transactional email (password reset today; team invites later).

Sends through Resend's REST API (https://resend.com) - the same provider
the Qumaxa marketing stack already uses, so the qumaxa.com sending domain
is verified there. Configure in backend/.env:

    RESEND_API_KEY=re_...            (a sending-only key is enough)
    MAIL_FROM=OCRDocFlow <no-reply@qumaxa.com>

With no RESEND_API_KEY the email is NOT sent: send_email() returns False
and the caller decides what to do (the password-reset endpoint writes the
link to the server log so an operator can still help a locked-out user).
Nothing here raises - a mail outage must never turn into a 500.
"""
import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def email_configured() -> bool:
    return bool(settings.RESEND_API_KEY and settings.MAIL_FROM)


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    if not email_configured():
        return False
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
