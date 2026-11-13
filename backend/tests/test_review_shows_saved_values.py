"""
The review screen must show what the reviewer saved, not the OCR draft.

Run from backend/ (same packages as test_password_reset.py):

    python tests/test_review_shows_saved_values.py

Regression test for: "on Review and Save, the old value stays on the screen
while the database has the corrected one". Saving wrote to the permanent
invoices tables, but GET .../extraction only ever read the staging draft.
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.organization  # noqa: E402,F401
from app.api.v1 import auth, extraction  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.extracted_invoice import ExtractedInvoiceHeader, ExtractedInvoiceItem  # noqa: E402
from app.models.user import User  # noqa: E402

Base.metadata.create_all(bind=engine)
limiter.enabled = False
api = FastAPI()
api.state.limiter = limiter
api.include_router(auth.router)
api.include_router(extraction.router)
client = TestClient(api)


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        sys.exit(1)


client.post("/api/v1/auth/register", json={"email": "u@example.com", "password": "password-1"})
token = client.post("/api/v1/auth/login", data={"username": "u@example.com", "password": "password-1"}).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

# A processed document with a two-invoice OCR draft in the staging tables.
db = SessionLocal()
user = db.query(User).filter(User.email == "u@example.com").first()
doc = Document(user_id=user.id, original_filename="scan.pdf", stored_filename="x.pdf", status="processed")
db.add(doc)
db.flush()
for idx, number in enumerate(["INV-0O1", "INV-002"]):  # "0O1" = an OCR misread of 001
    db.add(ExtractedInvoiceHeader(document_id=doc.id, invoice_index=idx, invoice_number=number,
                                  client_name="Acme Ldt", grand_total=100))
    db.add(ExtractedInvoiceItem(document_id=doc.id, invoice_index=idx, line_order=0,
                                description="Widgte", qty=1, unit_price=100, total_price=100))
db.commit()
doc_id = doc.id
db.close()

URL = f"/api/v1/documents/{doc_id}/extraction"

draft = client.get(URL, headers=H).json()
check("before saving, review shows the OCR draft",
      draft["invoice_number"] == "INV-0O1" and draft["status"] == "pending_review" and draft["total_invoices"] == 2)

corrected = dict(draft, invoice_number="INV-001", client_name="Acme Ltd", grand_total=250,
                 items=[{"description": "Widget", "qty": 2, "unit_price": 100, "total_price": 200},
                        {"description": "Delivery", "qty": 1, "unit_price": 50, "total_price": 50}])
r = client.post(f"{URL}/confirm", headers=H, json=corrected)
check("save succeeds", r.status_code == 200)

again = client.get(URL, headers=H).json()
check("reopened review shows the corrected header values",
      again["invoice_number"] == "INV-001" and again["client_name"] == "Acme Ltd" and float(again["grand_total"]) == 250)
check("reopened review shows the corrected line items, in order",
      [i["description"] for i in again["items"]] == ["Widget", "Delivery"] and float(again["items"][0]["qty"]) == 2)
check("status is saved and the invoice count is unchanged",
      again["status"] == "saved" and again["total_invoices"] == 2)

other = client.get(f"{URL}?invoice_index=1", headers=H).json()
check("the other, unsaved invoice still shows its own draft",
      other["invoice_number"] == "INV-002" and other["status"] == "pending_review")

# Save again with another change: the latest save wins.
client.post(f"{URL}/confirm", headers=H, json=dict(corrected, client_name="Acme Limited"))
check("a second save is shown too", client.get(URL, headers=H).json()["client_name"] == "Acme Limited")

# The staging draft is cleared when a newer document is uploaded; the saved invoice must still open.
db = SessionLocal()
db.query(ExtractedInvoiceItem).filter(ExtractedInvoiceItem.document_id == doc_id).delete()
db.query(ExtractedInvoiceHeader).filter(ExtractedInvoiceHeader.document_id == doc_id).delete()
db.commit()
db.close()
r = client.get(URL, headers=H)
check("saved invoice still opens after its draft was cleared",
      r.status_code == 200 and r.json()["invoice_number"] == "INV-001")
check("an unsaved invoice whose draft was cleared still answers 404",
      client.get(f"{URL}?invoice_index=1", headers=H).status_code == 404)

print("\nAll review checks passed.")
