"""
Invoice retention: warning emails and the automatic deletion.

The rule (owner's decision, 2026-11-19):

* A paid plan's period is one month. The day after a period closes, every
  invoice and document uploaded before the close is deleted - also when
  the customer carries on into the next period. Customers are told to
  download their invoices first.
* When a paid plan ends (cancelled, or put back on free), the invoices
  uploaded under it are deleted the day after. The account stays and
  works on the free plan.
* Free-plan documents are not deleted by this job.

Warning emails go to every member of the organization:

* quota:  at 80% and 90% of the period's invoice quota used (all plans)
* period: at 90% and 95% of the plan period passed (paid plans)
* ended:  when a paid plan has ended

Safety rules:

* Nothing is deleted for a period unless a warning email for that period
  was actually sent (so a mail outage delays deletion, never hides it),
  and never sooner than a day after that email.
* Organizations with a platform admin among their members are skipped.
* "Deleting" removes the stored file, the read text, the review data and
  the saved invoices. The document row itself stays (purged_at set) so the
  usage counts and AI cost reports still add up.

RETENTION_MODE in backend/.env decides what the job does:
  "off"      nothing runs
  "dry_run"  works out what it would email and delete, writes that to the
             log, and changes nothing (the default)
  "on"       sends the emails and deletes

Run by a background thread started in app/main.py, or by hand:
    python -m app.scripts.retention_run [--dry-run]
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.document import Document
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.organization import Organization
from app.models.retention_notice import RetentionNotice
from app.models.user import User
from app.services import email_service, usage_service

logger = logging.getLogger("ocrdocflow.retention")

QUOTA_STEPS = [(0.90, "quota_90"), (0.80, "quota_80")]      # highest first
PERIOD_STEPS = [(0.95, "period_95"), (0.90, "period_90")]   # highest first
DELETE_DELAY = timedelta(days=1)


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment.strftime('%B %Y')}"


def _plan_name(org: Organization) -> str:
    return (org.plan or "free").capitalize()


# --- the emails -------------------------------------------------------------

def _quota_email(org: Organization, percent: int, usage: int, limit: int, period_end: datetime) -> tuple[str, str]:
    subject = f"OCRDocFlow: you have used {percent}% of your invoices for this period"
    text = (
        f"Hello,\n\n"
        f"{org.name} has used {usage} of the {limit} invoices included in its "
        f"{_plan_name(org)} plan for the current period, which ends on {_day(period_end)}.\n\n"
        f"When the limit is reached, uploads stop until the next period starts. "
        f"To keep uploading, choose a bigger plan here:\n"
        f"{settings.FRONTEND_URL}/billing\n\n"
        f"OCRDocFlow by Qumaxa IT Services\n"
    )
    return subject, text


def _period_email(org: Organization, period_end: datetime) -> tuple[str, str]:
    delete_day = period_end + DELETE_DELAY
    subject = f"OCRDocFlow: download your invoices before {_day(period_end)}"
    text = (
        f"Hello,\n\n"
        f"The current period of {org.name}'s {_plan_name(org)} plan ends on {_day(period_end)}.\n\n"
        f"On {_day(delete_day)} all invoices and documents uploaded up to the end of this "
        f"period will be deleted from our servers. This also happens when your subscription "
        f"continues into the next period.\n\n"
        f"Please download your invoices (CSV or Excel) before then:\n"
        f"{settings.FRONTEND_URL}/dashboard\n\n"
        f"To keep using OCRDocFlow after {_day(period_end)}, make sure your subscription "
        f"is active, or subscribe again here:\n"
        f"{settings.FRONTEND_URL}/billing\n\n"
        f"OCRDocFlow by Qumaxa IT Services\n"
    )
    return subject, text


def _ended_email(org: Organization, delete_at: datetime) -> tuple[str, str]:
    subject = "OCRDocFlow: your plan has ended - download your invoices now"
    text = (
        f"Hello,\n\n"
        f"The paid plan of {org.name} has ended. Your account still works, on the free plan.\n\n"
        f"On {_day(delete_at)} the invoices and documents uploaded under the paid plan will be "
        f"deleted from our servers. Please download them (CSV or Excel) before then:\n"
        f"{settings.FRONTEND_URL}/dashboard\n\n"
        f"To subscribe again:\n"
        f"{settings.FRONTEND_URL}/billing\n\n"
        f"OCRDocFlow by Qumaxa IT Services\n"
    )
    return subject, text


# --- helpers ----------------------------------------------------------------

def _notices(db: Session, org: Organization, period_start: datetime, kinds: list[str]) -> list[RetentionNotice]:
    rows = (
        db.query(RetentionNotice)
        .filter(RetentionNotice.organization_id == org.id, RetentionNotice.kind.in_(kinds))
        .all()
    )
    # Compared in Python: SQLite (tests) drops the time zone, Postgres keeps it.
    return [r for r in rows if _utc(r.period_start) == _utc(period_start)]


def _notify(db: Session, org: Organization, members: list[User], period_start: datetime,
            kind: str, subject: str, text: str, dry_run: bool, report: dict, now: datetime) -> bool:
    """Sends one warning to every member, once. True when it went out."""
    recipients = [m.email for m in members if m.email]
    if dry_run:
        report["emails"].append(f"would email {kind} to {org.name} ({len(recipients)} recipient(s))")
        return False
    notice = RetentionNotice(organization_id=org.id, period_start=period_start, kind=kind, sent_at=now)
    db.add(notice)
    try:
        db.commit()
    except IntegrityError:  # another run got there first
        db.rollback()
        return False
    sent = [to for to in recipients if email_service.send_email(to, subject, text)]
    if not sent:
        # Not delivered to anyone: forget it, so the next run tries again
        # (and so nothing is deleted on the strength of it).
        db.delete(notice)
        db.commit()
        report["problems"].append(f"could not email {kind} to {org.name}")
        logger.error("Retention: %s email for organization '%s' could not be sent.", kind, org.name)
        return False
    report["emails"].append(f"emailed {kind} to {org.name} ({len(sent)} of {len(recipients)} recipient(s))")
    logger.warning("Retention: %s email sent for organization '%s' to %d recipient(s).", kind, org.name, len(sent))
    return True


def _documents_to_delete(db: Session, member_ids: list[int], before: datetime):
    return (
        db.query(Document)
        .filter(Document.user_id.in_(member_ids), Document.purged_at.is_(None), Document.uploaded_at < before)
    )


def _delete_documents(db: Session, org: Organization, member_ids: list[int], before: datetime,
                      now: datetime, dry_run: bool, report: dict) -> int:
    docs = _documents_to_delete(db, member_ids, before).all()
    if not docs:
        return 0
    if dry_run:
        report["deletions"].append(f"would delete {len(docs)} document(s) of {org.name} uploaded before {_day(before)}")
        return 0
    doc_ids = [d.id for d in docs]
    invoice_ids = [row[0] for row in db.query(Invoice.id).filter(Invoice.document_id.in_(doc_ids)).all()]
    if invoice_ids:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
        db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).delete(synchronize_session=False)
    db.query(ExtractedInvoiceItem).filter(ExtractedInvoiceItem.document_id.in_(doc_ids)).delete(synchronize_session=False)
    db.query(ExtractedInvoiceHeader).filter(ExtractedInvoiceHeader.document_id.in_(doc_ids)).delete(synchronize_session=False)
    files = []
    for doc in docs:
        files.append(os.path.join(settings.UPLOAD_DIR, doc.stored_filename))
        doc.ocr_text = None
        doc.original_filename = "(deleted)"
        doc.error_message = None
        doc.purged_at = now
    db.commit()
    # Files go after the database commit: a file left behind by a crash is
    # only wasted space, a deleted file with its rows still shown is worse.
    for path in files:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            logger.exception("Retention: could not remove file %s", path)
    report["deletions"].append(
        f"deleted {len(docs)} document(s) and {len(invoice_ids)} saved invoice(s) of {org.name} "
        f"uploaded before {_day(before)}"
    )
    logger.warning("Retention: deleted %d document(s), %d saved invoice(s) of organization '%s' (uploaded before %s).",
                   len(docs), len(invoice_ids), org.name, before.isoformat())
    return len(docs)


# --- one organization -------------------------------------------------------

def _process(db: Session, org: Organization, now: datetime, dry_run: bool, report: dict) -> None:
    members = db.query(User).filter(User.organization_id == org.id).all()
    if not members or any(m.role == "admin" for m in members):
        return
    member_ids = [m.id for m in members]
    paid = (org.plan or "free") != "free"
    length = timedelta(days=usage_service.get_period_length_days(org))
    period_start = _utc(usage_service.get_period_start(org, now))
    period_end = period_start + length

    # 1. Quota warnings (every plan). Only the highest step reached is sent.
    limit = usage_service.get_plan_limit(org)
    usage = usage_service.get_usage_this_period(db, org, period_start)
    if limit > 0:
        for index, (share, kind) in enumerate(QUOTA_STEPS):
            if usage >= limit * share:
                same_or_higher = [k for _, k in QUOTA_STEPS[: index + 1]]
                if not _notices(db, org, period_start, same_or_higher):
                    subject, text = _quota_email(org, round(share * 100), usage, limit, period_end)
                    _notify(db, org, members, period_start, kind, subject, text, dry_run, report, now)
                break

    if paid:
        # 2. Period warnings: the period is nearly over, download now.
        passed = (now - period_start) / length
        for index, (share, kind) in enumerate(PERIOD_STEPS):
            if passed >= share:
                same_or_higher = [k for _, k in PERIOD_STEPS[: index + 1]]
                if not _notices(db, org, period_start, same_or_higher):
                    subject, text = _period_email(org, period_end)
                    _notify(db, org, members, period_start, kind, subject, text, dry_run, report, now)
                break

        # 3. Delete what was uploaded before the period that just closed
        #    ended - a day after the close, and only if that period's
        #    warning went out at least a day ago.
        first_period = period_start <= _utc(org.plan_started_at or org.created_at)
        if not first_period and now >= period_start + DELETE_DELAY:
            if _documents_to_delete(db, member_ids, period_start).count():
                warned = _notices(db, org, period_start - length, [k for _, k in PERIOD_STEPS])
                if dry_run:
                    _delete_documents(db, org, member_ids, period_start, now, True, report)
                    if not warned:
                        report["problems"].append(f"{org.name}: no warning email on record for the closed period")
                elif warned and now >= min(_utc(n.sent_at) for n in warned) + DELETE_DELAY:
                    _delete_documents(db, org, member_ids, period_start, now, False, report)
                elif not warned:
                    report["problems"].append(
                        f"{org.name}: documents of a closed period were NOT deleted because no warning "
                        f"email was sent for that period"
                    )
        return

    # 4. Free plan after a paid plan ended: tell them, delete a day later.
    ended_at = org.paid_plan_ended_at
    if ended_at is None:
        return
    ended_at = _utc(ended_at)
    if not _documents_to_delete(db, member_ids, ended_at).count():
        return
    told = _notices(db, org, ended_at, ["ended"])
    if not told:
        subject, text = _ended_email(org, max(now, ended_at) + DELETE_DELAY)
        _notify(db, org, members, ended_at, "ended", subject, text, dry_run, report, now)
        if dry_run and now >= ended_at + DELETE_DELAY:
            _delete_documents(db, org, member_ids, ended_at, now, True, report)
        return
    if now >= max(ended_at, _utc(told[0].sent_at)) + DELETE_DELAY:
        _delete_documents(db, org, member_ids, ended_at, now, dry_run, report)


# --- the job ----------------------------------------------------------------

def run_once(db: Session, now: datetime | None = None, dry_run: bool | None = None) -> dict:
    """One pass over every organization. Returns what was (or would be) done."""
    now = now or datetime.now(timezone.utc)
    if dry_run is None:
        dry_run = settings.RETENTION_MODE.lower() != "on"
    report: dict = {"dry_run": dry_run, "emails": [], "deletions": [], "problems": []}
    for org in db.query(Organization).all():
        try:
            _process(db, org, now, dry_run, report)
        except Exception:  # one customer's problem must not stop the others
            db.rollback()
            logger.exception("Retention: organization %s failed", org.id)
            report["problems"].append(f"organization {org.id} failed - see the log")
    if report["problems"] and not dry_run and settings.ALERT_EMAIL:
        email_service.send_email(
            settings.ALERT_EMAIL, "OCRDocFlow: invoice retention job needs attention",
            "\n".join(report["problems"]) + "\n",
        )
    return report


def _loop() -> None:
    time.sleep(60)  # let the API finish starting
    while True:
        try:
            db = SessionLocal()
            try:
                report = run_once(db)
            finally:
                db.close()
            for line in report["emails"] + report["deletions"] + report["problems"]:
                logger.warning("Retention%s: %s", " (dry run)" if report["dry_run"] else "", line)
        except Exception:
            logger.exception("Retention job run failed")
        time.sleep(max(settings.RETENTION_INTERVAL_MINUTES, 5) * 60)


def start_background_job() -> None:
    mode = settings.RETENTION_MODE.lower()
    if mode not in ("dry_run", "on"):
        logger.warning("Invoice retention job is off (RETENTION_MODE=%s).", settings.RETENTION_MODE)
        return
    logger.warning("Invoice retention job started (mode: %s).", mode)
    threading.Thread(target=_loop, name="retention", daemon=True).start()
