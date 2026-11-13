"""
A paid Stripe checkout puts the organization on the plan - through the
buyer's return to the dashboard (/confirm-checkout) and through the webhook.

Run from backend/ (packages of test_password_reset.py plus stripe):

    python tests/test_checkout_confirm.py

Stripe is not contacted: Session.retrieve and the webhook signature check
are replaced with stand-ins that return what Stripe would.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["PROMO_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stripe  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.organization  # noqa: E402,F401
import app.models.document  # noqa: E402,F401
from app.api.v1 import auth, billing  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.user import User  # noqa: E402

Base.metadata.create_all(bind=engine)
limiter.enabled = False
api = FastAPI()
api.state.limiter = limiter
api.include_router(auth.router)
api.include_router(billing.router)
client = TestClient(api)


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        sys.exit(1)


def signup(email: str) -> tuple[dict, int]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password-1"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "password-1"}).json()["access_token"]
    db = SessionLocal()
    org_id = db.query(User).filter(User.email == email).first().organization_id
    db.close()
    return {"Authorization": f"Bearer {token}"}, org_id


def org_state(org_id: int) -> tuple:
    db = SessionLocal()
    o = db.query(Organization).filter(Organization.id == org_id).first()
    state = (o.plan, o.subscription_status, o.stripe_subscription_id, o.plan_started_at)
    db.close()
    return state


buyer, buyer_org = signup("buyer@example.com")
other, other_org = signup("other@example.com")

# What Stripe would answer for each session id.
SESSIONS = {
    "cs_test_paid": {"id": "cs_test_paid", "status": "complete", "payment_status": "paid",
                     "client_reference_id": str(buyer_org), "subscription": "sub_123",
                     "metadata": {"organization_id": str(buyer_org), "plan": "starter"}},
    "cs_test_open": {"id": "cs_test_open", "status": "open", "payment_status": "unpaid",
                     "client_reference_id": str(buyer_org), "subscription": None,
                     "metadata": {"organization_id": str(buyer_org), "plan": "professional"}},
    "cs_test_upgrade": {"id": "cs_test_upgrade", "status": "complete", "payment_status": "paid",
                        "client_reference_id": str(buyer_org), "subscription": "sub_456",
                        "metadata": {"organization_id": str(buyer_org), "plan": "business"}},
}


class _Obj:
    def __init__(self, d): self._d = d
    def to_dict(self): return dict(self._d)


def fake_retrieve(session_id, **_):
    if session_id not in SESSIONS:
        raise stripe.error.InvalidRequestError("No such checkout.session", param="id")
    return _Obj(SESSIONS[session_id])


stripe.checkout.Session.retrieve = fake_retrieve
URL = "/api/v1/billing/confirm-checkout"

check("starts on the free plan", org_state(buyer_org)[0] == "free")
check("needs a login", client.post(URL, json={"session_id": "cs_test_paid"}).status_code == 401)
check("something that is not a session id is refused",
      client.post(URL, headers=buyer, json={"session_id": "sub_123"}).status_code == 400)
check("unknown session -> 404", client.post(URL, headers=buyer, json={"session_id": "cs_test_nope"}).status_code == 404)

r = client.post(URL, headers=buyer, json={"session_id": "cs_test_open"})
check("unpaid session -> pending, plan unchanged",
      r.status_code == 200 and r.json()["status"] == "pending" and org_state(buyer_org)[0] == "free")

r = client.post(URL, headers=other, json={"session_id": "cs_test_paid"})
check("another organization's paid session -> 404, nobody upgraded",
      r.status_code == 404 and org_state(other_org)[0] == "free" and org_state(buyer_org)[0] == "free")

r = client.post(URL, headers=buyer, json={"session_id": "cs_test_paid"})
state = org_state(buyer_org)
check("paid session -> organization is on Starter, active, with the subscription id",
      r.status_code == 200 and r.json()["status"] == "active" and r.json()["plan"] == "starter"
      and state[:3] == ("starter", "active", "sub_123") and state[3] is not None)
r = client.post(URL, headers=buyer, json={"session_id": "cs_test_paid"})
check("confirming the same session again changes nothing (billing period not restarted)",
      r.status_code == 200 and org_state(buyer_org) == state)

# --- webhook path (signature check replaced; the body is what Stripe posts)
stripe.Webhook.construct_event = lambda payload, sig, secret: None


def webhook(event_type: str, obj: dict) -> int:
    return client.post("/api/v1/billing/webhook", content=json.dumps({"type": event_type, "data": {"object": obj}}),
                       headers={"stripe-signature": "t=1,v1=x"}).status_code


check("webhook for the same paid session after the return is a no-op",
      webhook("checkout.session.completed", SESSIONS["cs_test_paid"]) == 200 and org_state(buyer_org) == state)
check("webhook for an unpaid session is ignored",
      webhook("checkout.session.completed", SESSIONS["cs_test_open"]) == 200 and org_state(buyer_org)[0] == "starter")
check("webhook alone (buyer closed the tab) upgrades the plan",
      webhook("checkout.session.completed", SESSIONS["cs_test_upgrade"]) == 200
      and org_state(buyer_org)[:3] == ("business", "active", "sub_456"))
check("cancelling the subscription returns the organization to free",
      webhook("customer.subscription.deleted", {"id": "sub_456"}) == 200
      and org_state(buyer_org)[:2] == ("free", "canceled"))

print("\nAll checkout checks passed.")
