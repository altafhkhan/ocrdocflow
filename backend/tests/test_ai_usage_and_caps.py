"""
AI cost monitoring, big-invoice charging, spending caps and Excel export.

Run from backend/ (same packages as test_password_reset.py, plus openpyxl):

    python tests/test_ai_usage_and_caps.py

Uses a throwaway SQLite file and a fake OCR engine that reports fixed token
counts, so no AI call is made and nothing is charged.
"""
import io
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["UPLOAD_DIR"] = str(Path(_tmp, "uploads"))
os.environ["OCR_PROVIDER"] = "gemini"
os.environ["AI_PRICES_USD_PER_MTOK"] = "fake-model:1.00:4.00"
os.environ["PLAN_COST_CAPS_USD"] = "free:0.50,starter:6"
os.environ["PLATFORM_MONTHLY_COST_CAP_USD"] = "0"
os.environ["ALERT_EMAIL"] = "ops@example.com"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app.models.organization  # noqa: E402,F401
from app.api.v1 import admin, auth, documents, exports, extraction  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import ai_cost, email_service, ocr_service, usage_service  # noqa: E402


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name, flush=True)
    if not ok:
        sys.exit(1)


# --- pure rules ---------------------------------------------------------------
check("1-25 line items count as 1 invoice", [ai_cost.invoice_units(n) for n in (0, 1, 25)] == [1, 1, 1])
check("26-50 count as 2, 100 as 4, 101 as 5", [ai_cost.invoice_units(n) for n in (26, 50, 100, 101)] == [2, 2, 4, 5])
check("cost = tokens x price per million", ai_cost.cost_usd("fake-model", 1_000_000, 500_000) == 3.0)
check("a dated model name uses its base model's price", ai_cost.cost_usd("fake-model-001", 2_000_000, 0) == 2.0)
check("no notice for normal invoices", ai_cost.big_invoice_notice([{"items": [{}] * 25}]) is None)


# --- app with a fake engine ----------------------------------------------------
class FakeEngine:
    """Returns one invoice with `line_items` lines and bills fixed tokens."""
    line_items = 3
    usage = {"model": "fake-model", "input_tokens": 2000, "output_tokens": 1000}   # = $0.006

    def extract_document(self, images, language):
        items = [{"description": f"Item {i}", "qty": 1, "unit_price": 2, "total_price": 2} for i in range(self.line_items)]
        header = {"invoice_number": "T-1", "invoice_date": "01/11/2026", "due_date": None, "currency": "USD",
                  "client_name": "Buyer", "client_company": "Seller Ltd", "client_email": None,
                  "sub_total": 2 * self.line_items, "tax": 0, "discount": 0, "grand_total": 2 * self.line_items}
        return ["Invoice T-1"], [{"header": header, "items": items}], "en"

    def pop_usage(self):
        return dict(self.usage)


fake = FakeEngine()
ocr_service.get_provider = lambda name=None: fake
# SQLite returns timezone-less dates; the billing-period maths expects Postgres.
usage_service.get_period_start = lambda org: datetime(2020, 1, 1, tzinfo=timezone.utc)
sent_alerts: list[tuple[str, str]] = []
email_service.send_email = lambda to, subject, text, html=None: sent_alerts.append((to, subject)) or True

Base.metadata.create_all(bind=engine)
limiter.enabled = False
api = FastAPI()
api.state.limiter = limiter
for module in (auth, documents, extraction, exports, admin):
    api.include_router(module.router)
client = TestClient(api)


def login(email: str) -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password-1"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "password-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


H = login("customer@example.com")
ADMIN = login("boss@example.com")
db = SessionLocal()
db.query(User).filter(User.email == "boss@example.com").update({"role": "admin"})
db.commit()
org_id = db.query(User).filter(User.email == "customer@example.com").first().organization_id

buf = io.BytesIO()
Image.new("RGB", (60, 40), "white").save(buf, format="PNG")
PNG = buf.getvalue()


def upload(headers=H):
    return client.post("/api/v1/documents/upload", headers=headers,
                       files={"file": ("scan.png", PNG, "image/png")}, data={"language": "en"})


# --- a normal invoice ----------------------------------------------------------
r = upload().json()
check("normal invoice: charged as 1, no notice", r["billable_invoice_count"] == 1 and r["notices"] == [])
doc = db.query(Document).filter(Document.id == r["id"]).first()
check("tokens, model and cost are stored on the document",
      (doc.ai_model, doc.ai_input_tokens, doc.ai_output_tokens, float(doc.ai_cost_usd)) == ("fake-model", 2000, 1000, 0.006))

# --- a 100-line invoice --------------------------------------------------------
fake.line_items = 100
r = upload().json()
check("100-line invoice: found 1, charged as 4", r["invoice_count"] == 1 and r["billable_invoice_count"] == 4)
check("the uploader is told why", len(r["notices"]) == 1 and "100 line items" in r["notices"][0] and "4 invoices" in r["notices"][0])
me = client.get("/api/v1/auth/me", headers=H).json()
check("plan usage counts 1 + 4 = 5 invoices", me["invoices_this_period"] == 5)
fake.line_items = 3

# --- admin usage report --------------------------------------------------------
check("usage report is admin-only", client.get("/api/v1/admin/usage", headers=H).status_code == 403)
report = client.get("/api/v1/admin/usage", headers=ADMIN).json()
row = next(o for o in report["organizations"] if o["id"] == org_id)
check("report shows the customer's uploads, tokens and cost",
      (row["documents"], row["input_tokens"], row["output_tokens"], row["cost_usd"]) == (2, 4000, 2000, 0.012))
check("report shows the plan's default cap and limit",
      row["cost_cap_usd"] == 0.5 and row["cost_cap_is_custom"] is False and row["invoice_limit"] == 10)
check("platform total covers every upload", report["platform"]["cost_usd"] == 0.012 and report["platform"]["documents"] == 2)

# --- per-customer limits -------------------------------------------------------
r = client.patch(f"/api/v1/admin/organizations/{org_id}", headers=ADMIN,
                 json={"monthly_cost_cap_usd": 0.02, "invoice_limit_override": 100})
check("admin can set a customer's cap and invoice limit",
      r.status_code == 200 and r.json()["cost_cap_usd"] == 0.02 and r.json()["invoice_limit"] == 100)
check("a customer cannot change limits",
      client.patch(f"/api/v1/admin/organizations/{org_id}", headers=H, json={"monthly_cost_cap_usd": 99}).status_code == 403)

sent_alerts.clear()
check("upload below the cap still works ($0.018 of $0.02)", upload().status_code == 200)
check("an alert email went out at 80% of the cap",
      len(sent_alerts) == 1 and sent_alerts[0][0] == "ops@example.com" and "80%" in sent_alerts[0][1])
check("upload that reaches the cap is still processed", upload().status_code == 200)
check("a second alert went out at 100%", len(sent_alerts) == 2 and "100%" in sent_alerts[1][1])
r = upload()
check("after the cap is reached, uploads are refused with a clear message",
      r.status_code == 403 and "processing limit for this month" in r.json()["detail"])
check("no AI cost was added by the refused upload",
      usage_service.get_org_cost_this_month(SessionLocal(), db.get(app.models.organization.Organization, org_id)) == 0.024)

client.patch(f"/api/v1/admin/organizations/{org_id}", headers=ADMIN, json={"monthly_cost_cap_usd": None})
check("clearing the custom cap goes back to the plan default and uploads resume", upload().status_code == 200)

# --- platform-wide cap ---------------------------------------------------------
settings.PLATFORM_MONTHLY_COST_CAP_USD = 0.01
r = upload()
check("platform cap pauses uploads for everyone", r.status_code == 503 and "monthly processing budget" in r.json()["detail"])
check("...including admins", upload(ADMIN).status_code == 503)
settings.PLATFORM_MONTHLY_COST_CAP_USD = 0

# --- download format preference + Excel ---------------------------------------
check("download format defaults to csv", client.get("/api/v1/auth/me", headers=H).json()["export_format"] == "csv")
check("an unknown format is rejected",
      client.patch("/api/v1/auth/me/preferences", headers=H, json={"export_format": "pdf"}).status_code == 400)
client.patch("/api/v1/auth/me/preferences", headers=H, json={"export_format": "xlsx"})
check("the chosen format is remembered on the account", client.get("/api/v1/auth/me", headers=H).json()["export_format"] == "xlsx")

latest = upload().json()["id"]
draft = client.get(f"/api/v1/documents/{latest}/extraction", headers=H).json()
client.post(f"/api/v1/documents/{latest}/extraction/confirm", headers=H, json=draft)
today = datetime.now(timezone.utc).date().isoformat()
query = f"start_date={today}&end_date={today}&language=ar"
csv_rows = client.get(f"/api/v1/exports/csv?{query}", headers=H).content.decode("utf-8-sig").strip().splitlines()
x = client.get(f"/api/v1/exports/xlsx?{query}", headers=H)
check("Excel export downloads as an .xlsx file",
      x.status_code == 200 and ".xlsx" in x.headers["content-disposition"] and x.content[:2] == b"PK")

from openpyxl import load_workbook  # noqa: E402

ws = load_workbook(io.BytesIO(x.content)).active
rows = list(ws.iter_rows(values_only=True))
check("Excel has the same rows and columns as the CSV", len(rows) == len(csv_rows) == 4 and len(rows[0]) == 15)
check("Excel keeps amounts as numbers", rows[1][8:11] == (1, 2, 2) and rows[1][14] == 6)
check("Arabic headings make the sheet right-to-left", ws.sheet_view.rightToLeft is True and ws.freeze_panes == "A2")

print("All AI usage, cap and export checks passed.")
