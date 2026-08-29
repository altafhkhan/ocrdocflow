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
plan_started_at (or created_at if that's unset). The window LENGTH is
plan-specific (confirmed with a concrete example):
  - Starter: bills monthly, usage period is 1 month
  - Professional: bills monthly, but the USAGE PERIOD is 2 months long -
    e.g. invoices unused in month 1 remain usable through the end of
    month 2, then the period resets
  - Business: same idea, 4-month usage period

Warnings: logged at 90% and 95% of quota - see email_service.py for
actually sending them (SendGrid).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.document import Document
from app.models.user import User
from app.models.organization import Organization

logger = logging.getLogger("ocrdocflow.usage")

PLAN_LIMITS = {
    "free": 10,
    "starter": 500,
    "professional": 3000,
    "business": 15000,
}

PLAN_PERIOD_DAYS = {
    "free": 30,
    "starter": 30,
    "professional": 60,
    "business": 120,
}

WARNING_THRESHOLDS = [0.90, 0.95]


def get_plan_limit(org: Organization) -> int:
    return PLAN_LIMITS.get(org.plan, PLAN_LIMITS["free"])


def get_period_length_days(org: Organization) -> int:
    return PLAN_PERIOD_DAYS.get(org.plan, PLAN_PERIOD_DAYS["free"])


def get_period_start(org: Organization) -> datetime:
    """
    Start of the organization's CURRENT billing/usage period - a rolling
    window from plan_started_at (or created_at if unset), with a length
    that depends on the plan (see PLAN_PERIOD_DAYS above).
    """
    reference = org.plan_started_at or org.created_at
    period_days = get_period_length_days(org)
    now = datetime.now(timezone.utc)
    days_elapsed = (now - reference).days
    period_number = days_elapsed // period_days
    return reference + timedelta(days=period_number * period_days)


def get_usage_this_period(db: Session, org: Organization) -> int:
    """
    Sum of detected_invoice_count across documents uploaded by ANY
    member of this organization within the current billing period.
    """
    period_start = get_period_start(org)
    member_ids = [row[0] for row in db.query(User.id).filter(User.organization_id == org.id).all()]
    if not member_ids:
        return 0
    total = (
        db.query(func.coalesce(func.sum(Document.detected_invoice_count), 0))
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
    Logs a warning (and, once email_service.py is wired in, actually
    sends one) if this upload just pushed the ORGANIZATION's usage past
    a 90% or 95% threshold for the first time this period.
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
                "Would send %.0f%% usage warning email to organization '%s' "
                "(triggered by %s, plan=%s, usage=%d/%d)",
                threshold * 100, org.name, user.email, org.plan, usage_after, limit,
            )