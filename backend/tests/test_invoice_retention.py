"""
Invoice retention: warning emails and the day-after deletion.

Run from backend/:

    python tests/test_invoice_retention.py

Uses a throwaway SQLite file and a fake mailer; time is moved by passing
`now` to the job, so nothing waits.
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["UPLOAD_DIR"] = str(Path(_tmp, "uploads"))
os.environ["RETENTION_MODE"] = "on"
os.environ["ALERT_EMAIL"] = "ops@example.com"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem  # noqa: E402
from app.models.invoice import Invoice, InvoiceItem  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.retention_notice import RetentionNotice  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import email_service, retention_service, usage_service  # noqa: E402


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name, flush=True)
    if not ok:
        sys.exit(1)


check("every plan's period is one month", set(usage_service.PLAN_PERIOD_DAYS.values()) == {30})
check("Business plan allows 10,000 invoices", usage_service.PLAN_LIMITS["business"] == 10000)

mail_works = True
outbox: list[tuple[str, str, str]] = []


def fake_send(to, subject, text, html=None):
    if not mail_works:
        return False
    outbox.append((to, subject, text))
    return True


email_service.send_email = fake_send
Base.metadata.create_all(bind=engine)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
db = SessionLocal()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_n = 0


def make_org(name, plan, members=1, role="user", started=T0):
    org = Organization(name=name, plan=plan, plan_started_at=started, created_at=started)
    db.add(org)
    db.commit()
    for i in range(members):
        db.add(User(email=f"{name.lower()}{i}@example.com", hashed_password="x", role=role,
                    organization_id=org.id, org_role="owner" if i == 0 else "member"))
    db.commit()
    return org


def make_doc(org, uploaded_at, invoices=1, saved=True):
    """A stored file with staging rows and (optionally) a saved invoice."""
    global _n
    _n += 1
    user = db.query(User).filter(User.organization_id == org.id).first()
    stored = f"file{_n}.png"
    Path(settings.UPLOAD_DIR, stored).write_bytes(b"scan")
    doc = Document(user_id=user.id, original_filename=f"Invoice {_n}.png", stored_filename=stored, status="done",
                   ocr_text="secret text", detected_invoice_count=invoices, billable_invoice_count=invoices,
                   ai_cost_usd=0.01, uploaded_at=uploaded_at)
    db.add(doc)
    db.commit()
    db.add(ExtractedInvoiceHeader(document_id=doc.id, invoice_number="A-1"))
    db.add(ExtractedInvoiceItem(document_id=doc.id, description="Thing"))
    if saved:
        inv = Invoice(document_id=doc.id, user_id=user.id, invoice_number="A-1")
        db.add(inv)
        db.commit()
        db.add(InvoiceItem(invoice_id=inv.id, description="Thing"))
    db.commit()
    return doc


def run(now, dry_run=None):
    outbox.clear()
    return retention_service.run_once(db, now=now, dry_run=dry_run)


def kinds(org):
    return sorted(n.kind for n in db.query(RetentionNotice).filter(RetentionNotice.organization_id == org.id))


def live_docs(org):
    ids = [u.id for u in db.query(User).filter(User.organization_id == org.id)]
    return db.query(Document).filter(Document.user_id.in_(ids), Document.purged_at.is_(None)).count()


day = timedelta(days=1)

# --- quota warnings -----------------------------------------------------------
free = make_org("Freeco", "free")
for _ in range(7):
    make_doc(free, T0 + day)
run(T0 + 2 * day)
check("no quota email below 80%", outbox == [])
make_doc(free, T0 + day)
run(T0 + 2 * day)
check("80% of the quota sends one email", len(outbox) == 1 and "80%" in outbox[0][1])
run(T0 + 2 * day)
check("the same warning is not sent twice", outbox == [])
make_doc(free, T0 + day)
run(T0 + 2 * day)
check("90% of the quota sends the next email", len(outbox) == 1 and "90%" in outbox[0][1] and "9 of the 10" in outbox[0][2])
check("free plan gets no period warning and no deletion",
      run(T0 + 29 * day)["deletions"] == [] and outbox == [] and live_docs(free) == 9)
run(T0 + 500 * day)
check("free-plan documents are never deleted", live_docs(free) == 9)

# --- period warnings and the deletion -------------------------------------------
team = make_org("Teamco", "professional", members=3)
old = make_doc(team, T0 + 5 * day)
make_doc(team, T0 + 20 * day, saved=False)
old_file = Path(settings.UPLOAD_DIR, old.stored_filename)
run(T0 + 26 * day)
check("no period email before 90% of the period", outbox == [])
report = run(T0 + 27 * day + timedelta(hours=1))
check("90% of the period emails every team member",
      len(outbox) == 3 and all("download your invoices before 31 January 2026" in s for _, s, _ in outbox))
check("the email says when the invoices go and that renewal does not stop it",
      "On 1 February 2026 all invoices" in outbox[0][2] and "continues into the next period" in outbox[0][2])
run(T0 + 28 * day + timedelta(hours=13))
check("95% of the period sends a second reminder", len(outbox) == 3 and kinds(team) == ["period_90", "period_95"])
run(T0 + 30 * day + timedelta(hours=12))
check("nothing is deleted on the day the period closes", live_docs(team) == 2 and old_file.exists())
new = make_doc(team, T0 + 30 * day + timedelta(hours=1))
report = run(T0 + 31 * day + timedelta(minutes=5))
check("the day after, the closed period's documents are deleted", live_docs(team) == 1 and len(report["deletions"]) == 1)
db.expire_all()
gone = db.query(Document).filter(Document.id == old.id).first()
check("the file, the text and the file name are gone", not old_file.exists() and gone.ocr_text is None
      and gone.original_filename == "(deleted)" and gone.purged_at is not None)
check("the saved invoices and review data are gone",
      db.query(Invoice).filter(Invoice.document_id == old.id).count() == 0
      and db.query(InvoiceItem).count() == db.query(Invoice).count()
      and db.query(ExtractedInvoiceHeader).filter(ExtractedInvoiceHeader.document_id == old.id).count() == 0)
check("the usage count and AI cost of deleted documents are kept",
      gone.billable_invoice_count == 1 and float(gone.ai_cost_usd) == 0.01)
check("a document uploaded in the new period is untouched",
      Path(settings.UPLOAD_DIR, new.stored_filename).exists() and live_docs(team) == 1)

# --- no warning sent -> no deletion ----------------------------------------------
quiet = make_org("Quietco", "starter")
make_doc(quiet, T0 + 3 * day)
mail_works = False
report = run(T0 + 28 * day)
check("a failed email is not recorded as sent", kinds(quiet) == [] and any("Quietco" in p for p in report["problems"]))
report = run(T0 + 32 * day)
check("without a warning email nothing is deleted", live_docs(quiet) == 1 and any("NOT deleted" in p for p in report["problems"]))
mail_works = True
run(T0 + 58 * day)
report = run(T0 + 61 * day + timedelta(hours=1))
check("once a period's warning has gone out, the old documents go too", live_docs(quiet) == 0)

# --- first period after subscribing, and admins ------------------------------------
fresh = make_org("Freshco", "starter", started=T0 + 100 * day)
make_doc(fresh, T0 + 40 * day)  # uploaded while still on the free plan
run(T0 + 102 * day)
check("subscribing does not delete earlier documents the next day", live_docs(fresh) == 1)
boss = make_org("Bossco", "business", role="admin")
make_doc(boss, T0 + 2 * day)
run(T0 + 28 * day)
run(T0 + 40 * day)
check("an admin's own organization is left alone", live_docs(boss) == 1 and kinds(boss) == [])

# --- a paid plan that ended -------------------------------------------------------
ex = make_org("Exco", "starter")
make_doc(ex, T0 + 4 * day)
ended = T0 + 10 * day
ex.plan, ex.plan_started_at, ex.paid_plan_ended_at = "free", ended, ended
db.commit()
after = make_doc(ex, ended + timedelta(hours=2))
run(ended + timedelta(hours=3))
check("a plan that ended emails the customer", len(outbox) == 1 and "plan has ended" in outbox[0][1]
      and "On 12 January 2026" in outbox[0][2] and live_docs(ex) == 2)
run(ended + timedelta(hours=20))
check("nothing is deleted the same day", live_docs(ex) == 2 and outbox == [])
run(ended + day + timedelta(hours=4))
check("the next day the paid plan's documents are deleted, free-plan ones stay",
      live_docs(ex) == 1 and Path(settings.UPLOAD_DIR, after.stored_filename).exists())

# --- dry run -----------------------------------------------------------------------
dry = make_org("Dryco", "starter")
make_doc(dry, T0 + 2 * day)
report = run(T0 + 28 * day, dry_run=True)
check("a dry run reports the email but sends and records nothing",
      any("Dryco" in e for e in report["emails"]) and outbox == [] and kinds(dry) == [])
report = run(T0 + 32 * day, dry_run=True)
check("a dry run reports the deletion but deletes nothing",
      any("would delete 1 document(s) of Dryco" in d for d in report["deletions"]) and live_docs(dry) == 1)

print("\nAll invoice retention checks passed.")
