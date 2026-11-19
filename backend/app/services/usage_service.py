"""
Usage/quota tracking for subscription plans.

Plans belong to ORGANIZATIONS, not individual users (Professional = up
to 5 users sharing one plan/quota, Business = up to 15) - so usage is
POOLED across every member of the same organization, not tracked
per-user in isolation.

Product decision: usage is measured in INVOICES, not PDF pages - a
single page can contain multiple invoices (each counts separately), or
one invoice can span multiple pages (still counts as one). See
Document.detected_invoice_count, set after field extraction runs.

Billing period: a rolling window from the organization's
plan_started_at (or created_at if that's unset). Every plan's period is
one month (30 days): the invoice count starts again each period, and on
paid plans the invoices of a closed period are deleted the next day
(services/retention_service.py).

Warnings: emails at 80% and 90% of the quota are sent by the retention
job (services/retention_service.py), not from here.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.document import Document
from app.models.user import User
from app.models.organization import Organization

logger = logging.getLogger("ocrdocflow.usage")

PLAN_LIMITS = {
    "free": 10,
    "starter": 500,
    "professional": 3000,
    "business": 12000,
}

PLAN_PERIOD_DAYS = {
    "free": 30,
    "starter": 30,
    "professional": 30,
    "business": 30,
}

WARNING_THRESHOLDS = [0.80, 0.90]


def get_plan_limit(org: Organization) -> int:
    # An admin can give one customer its own limit (Admin Panel, Usage tab).
    if org.invoice_limit_override is not None:
        return org.invoice_limit_override
    return PLAN_LIMITS.get(org.plan, PLAN_LIMITS["free"])


def get_period_length_days(org: Organization) -> int:
    return PLAN_PERIOD_DAYS.get(org.plan, PLAN_PERIOD_DAYS["free"])


def _utc(moment: datetime) -> datetime:
    # SQLite (tests) hands datetimes back without a time zone.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def get_period_start(org: Organization, now: datetime | None = None) -> datetime:
    """
    Start of the organization's CURRENT billing/usage period - a rolling
    window from plan_started_at (or created_at if unset), one month long
    (see PLAN_PERIOD_DAYS above).
    """
    reference = _utc(org.plan_started_at or org.created_at)
    period_days = get_period_length_days(org)
    now = now or datetime.now(timezone.utc)
    days_elapsed = max((now - reference).days, 0)
    period_number = days_elapsed // period_days
    return reference + timedelta(days=period_number * period_days)


def get_period_end(org: Organization) -> datetime:
    """When the current period closes (and the invoice count starts again)."""
    return get_period_start(org) + timedelta(days=get_period_length_days(org))


def get_usage_this_period(db: Session, org: Organization, period_start: datetime | None = None) -> int:
    """
    Plan invoices used by documents uploaded by ANY member of this
    organization within the current billing period. A long invoice counts
    as several (billable_invoice_count, see services/ai_cost.py); older
    documents without that figure count their detected invoices.
    """
    period_start = period_start or get_period_start(org)
    member_ids = [row[0] for row in db.query(User.id).filter(User.organization_id == org.id).all()]
    if not member_ids:
        return 0
    total = (
        db.query(func.coalesce(func.sum(
            func.coalesce(Document.billable_invoice_count, Document.detected_invoice_count)), 0))
        .filter(Document.user_id.in_(member_ids), Document.uploaded_at >= period_start)
        .scalar()
    )
    return total or 0


def check_quota_before_upload(db: Session, user: User) -> None:
    """
    Raises HTTPException if the user's ORGANIZATION has already reached
    its plan's quota for the current billing period (usage is pooled
    across all members, not tracked per-user). Admins are exempt. Call
    this BEFORE running OCR, so we don't waste processing time/memory on
    an upload that's already over quota.
    """
    from fastapi import HTTPException  # local import keeps this a plain service module otherwise

    if user.role == "admin":
        return
    if user.organization is None:
        # Shouldn't happen post-migration, but fail OPEN rather than
        # crash the upload if it somehow does - better to allow an
        # upload than to break the whole app for one edge case.
        logger.warning("User %s has no organization - quota check skipped.", user.email)
        return

    org = user.organization
    limit = get_plan_limit(org)
    usage = get_usage_this_period(db, org)
    if usage >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Your organization has reached its {org.plan} plan's limit of "
                f"{limit} invoices for this billing period. Please upgrade to continue."
            ),
        )


def log_usage_warnings(db: Session, user: User, usage_before: int, usage_after: int) -> None:
    """
    Writes a log line when this upload pushed the ORGANIZATION's usage
    past 80% or 90% of its quota. The customer's email about it is sent by
    the retention job (services/retention_service.py) on its next run.
    """
    if user.role == "admin" or user.organization is None:
        return

    org = user.organization
    limit = get_plan_limit(org)
    if limit <= 0:
        return

    for threshold in WARNING_THRESHOLDS:
        threshold_count = limit * threshold
        if usage_before < threshold_count <= usage_after:
            logger.info(
                "Usage passed %.0f%% of the quota for organization '%s' "
                "(triggered by %s, plan=%s, usage=%d/%d)",
                threshold * 100, org.name, user.email, org.plan, usage_after, limit,
            )


# --- AI spending: monitoring, caps and alerts -------------------------------
# Separate from the invoice quota above. The quota is what the customer
# bought; the spending cap protects US from an unexpectedly expensive month
# (very long invoices, a runaway integration). Caps run per CALENDAR month.

def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _plan_cost_caps() -> dict[str, float]:
    caps: dict[str, float] = {}
    for entry in (settings.PLAN_COST_CAPS_USD or "").split(","):
        plan, _, value = entry.partition(":")
        try:
            caps[plan.strip()] = float(value)
        except ValueError:
            continue
    return caps


def get_org_cost_cap(org: Organization) -> float:
    """Monthly AI spending cap for this customer in USD; 0 = no cap."""
    if org.monthly_cost_cap_usd is not None:
        return float(org.monthly_cost_cap_usd)
    return _plan_cost_caps().get(org.plan, 0.0)


def get_org_cost_this_month(db: Session, org: Organization) -> float:
    member_ids = [row[0] for row in db.query(User.id).filter(User.organization_id == org.id).all()]
    if not member_ids:
        return 0.0
    total = (
        db.query(func.coalesce(func.sum(Document.ai_cost_usd), 0))
        .filter(Document.user_id.in_(member_ids), Document.uploaded_at >= month_start())
        .scalar()
    )
    return float(total or 0)


def get_platform_cost_this_month(db: Session) -> float:
    """Every upload on the platform this month, visitors included."""
    total = (
        db.query(func.coalesce(func.sum(Document.ai_cost_usd), 0))
        .filter(Document.uploaded_at >= month_start())
        .scalar()
    )
    return float(total or 0)


def check_spend_caps_before_upload(db: Session, user: User | None) -> None:
    """
    Raises HTTPException when the platform's, or this customer's, monthly AI
    spending cap is already used up. `user` is None for a visitor upload
    (only the platform cap applies). Admins are exempt from their own
    organization's cap but not from the platform cap.
    """
    from fastapi import HTTPException

    platform_cap = settings.PLATFORM_MONTHLY_COST_CAP_USD or 0
    if platform_cap > 0 and get_platform_cost_this_month(db) >= platform_cap:
        logger.warning("Upload refused: platform AI spending cap of $%.2f reached.", platform_cap)
        raise HTTPException(
            status_code=503,
            detail=(
                "Document processing is paused for the rest of this month because the "
                "service has reached its monthly processing budget. Please try again "
                "next month or contact support."
            ),
        )

    if user is None or user.role == "admin" or user.organization is None:
        return
    org = user.organization
    cap = get_org_cost_cap(org)
    if cap > 0 and get_org_cost_this_month(db, org) >= cap:
        logger.warning("Upload refused: organization '%s' reached its AI spending cap of $%.2f.", org.name, cap)
        raise HTTPException(
            status_code=403,
            detail=(
                "Your organization has reached its processing limit for this month, so "
                "uploads are paused until next month. Please contact support if you need "
                "the limit raised."
            ),
        )


def _usd(amount: float) -> str:
    return f"${amount:.2f}" if amount >= 1 else f"${amount:.4f}"


def _alert_thresholds() -> list[float]:
    values = []
    for part in (settings.COST_ALERT_THRESHOLDS or "").split(","):
        try:
            values.append(float(part))
        except ValueError:
            continue
    return sorted(v for v in values if v > 0)


def _send_alert(subject: str, text: str) -> None:
    logger.warning("%s - %s", subject, text.replace("\n", " "))
    if not settings.ALERT_EMAIL:
        return
    try:
        from app.services import email_service
        email_service.send_email(settings.ALERT_EMAIL, subject, text)
    except Exception:  # an alert must never fail the upload that triggered it
        logger.exception("Could not send alert email '%s'", subject)


def send_spend_alerts(db: Session, user: User | None, org_cost_before: float, platform_cost_before: float) -> None:
    """
    Call after an upload is saved. Emails settings.ALERT_EMAIL (and always
    writes to the log) when that upload pushed the customer's or the
    platform's month-to-date AI cost past an alert threshold of its cap.
    """
    month = month_start().strftime("%B %Y")

    platform_cap = settings.PLATFORM_MONTHLY_COST_CAP_USD or 0
    if platform_cap > 0:
        after = get_platform_cost_this_month(db)
        for t in _alert_thresholds():
            if platform_cost_before < platform_cap * t <= after:
                _send_alert(
                    f"OCRDocFlow: platform AI spending at {t:.0%} of the monthly cap",
                    f"Platform AI cost for {month} is {_usd(after)} of the {_usd(platform_cap)} cap.\n"
                    + ("All uploads are now paused until next month or until "
                       "PLATFORM_MONTHLY_COST_CAP_USD is raised.\n" if after >= platform_cap else ""),
                )

    org = user.organization if user is not None else None
    if org is None:
        return
    cap = get_org_cost_cap(org)
    if cap <= 0:
        return
    after = get_org_cost_this_month(db, org)
    for t in _alert_thresholds():
        if org_cost_before < cap * t <= after:
            _send_alert(
                f"OCRDocFlow: {org.name} at {t:.0%} of its monthly AI spending cap",
                f"Customer: {org.name} (plan: {org.plan}, last upload by {user.email})\n"
                f"AI cost for {month}: {_usd(after)} of the {_usd(cap)} cap.\n"
                + ("Their uploads are now paused until next month, or until you raise "
                   "the cap in the Admin Panel (Usage tab).\n" if after >= cap else ""),
            )

