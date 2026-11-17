"""
Loyalty coupon: 25% off the customer's plan for 3 months, usable once by the
customer or by anyone they give it to, valid until 2 months after the plan
period ends - and never stacked with another discount.

Run from backend/ (packages of test_password_reset.py plus stripe):

    python tests/test_loyalty_coupon.py

Stripe is not contacted: the few Stripe calls billing.py makes are replaced
with an in-memory stand-in that behaves like Stripe for these cases.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-a-real-key"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["PROMO_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stripe  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.organization  # noqa: E402,F401
import app.models.document  # noqa: E402,F401
from app.api.v1 import auth, billing  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import usage_service  # noqa: E402


def check(name: str, ok: bool) -> None:
    print(("PASS  " if ok else "FAIL  ") + name, flush=True)
    if not ok:
        sys.exit(1)


# --- an in-memory Stripe -------------------------------------------------------
class Obj(dict):
    """Looks enough like a Stripe object: attribute access + str() -> JSON."""
    __getattr__ = dict.get

    def __str__(self):
        return json.dumps(self)

    def auto_paging_iter(self):
        return iter(self["data"])


customers: dict[str, Obj] = {}
coupons: dict[str, Obj] = {}
codes: dict[str, Obj] = {}
subscriptions: dict[str, Obj] = {}
checkout_calls: list[dict] = []


def customer_create(**kw):
    c = Obj(id=f"cus_{len(customers) + 1}", metadata=dict(kw.get("metadata") or {}))
    customers[c["id"]] = c
    return c


def customer_modify(cid, **kw):
    customers[cid]["metadata"].update(kw.get("metadata") or {})
    return customers[cid]


def coupon_create(**kw):
    c = Obj(id=f"co_{len(coupons) + 1}", valid=True, times_redeemed=0, **kw)
    coupons[c["id"]] = c
    return c


def code_create(**kw):
    promotion = kw.pop("promotion")
    c = Obj(id=f"promo_{len(codes) + 1}", active=True, times_redeemed=0, promotion=promotion, **kw)
    codes[c["id"]] = c
    return c


def code_list(code=None, limit=1):
    return Obj(data=[c for c in codes.values() if c["code"] == code][:limit])


def code_modify(cid, **kw):
    codes[cid].update(kw)
    return codes[cid]


def session_create(**kw):
    checkout_calls.append(kw)
    return Obj(id="cs_test_1", url="https://checkout.stripe.test/pay/cs_test_1")


def subscription_modify(sid, **kw):
    subscriptions[sid]["discounts"] = kw["discounts"]
    for d in kw["discounts"]:
        codes[d["promotion_code"]]["times_redeemed"] += 1
    return subscriptions[sid]


stripe.Customer.create = customer_create
stripe.Customer.retrieve = lambda cid: customers[cid]
stripe.Customer.modify = customer_modify
stripe.Coupon.create = coupon_create
stripe.Coupon.list = lambda limit=100: Obj(data=list(coupons.values()))
stripe.Price.retrieve = lambda pid: Obj(id=pid, product=f"prod_{pid[-4:]}")
stripe.PromotionCode.create = code_create
stripe.PromotionCode.list = code_list
stripe.PromotionCode.retrieve = lambda cid: codes[cid]
stripe.PromotionCode.modify = code_modify
stripe.checkout.Session.create = session_create
stripe.Subscription.retrieve = lambda sid: subscriptions[sid]
stripe.Subscription.modify = subscription_modify

# SQLite returns timezone-less dates; pin the plan period for a known answer.
PERIOD_START = datetime(2026, 11, 17, tzinfo=timezone.utc)
usage_service.get_period_start = lambda org: PERIOD_START

Base.metadata.create_all(bind=engine)
limiter.enabled = False
api = FastAPI()
api.state.limiter = limiter
api.include_router(auth.router)
api.include_router(billing.router)
client = TestClient(api)


def signup(email: str, plan: str = "free") -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password-1"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "password-1"}).json()["access_token"]
    if plan != "free":
        db = SessionLocal()
        db.query(User).filter(User.email == email).first().organization.plan = plan
        db.commit()
        db.close()
    return {"Authorization": f"Bearer {token}"}


# --- date rule -----------------------------------------------------------------
check("2 months after 31 December is the last day of February",
      billing._add_months(datetime(2026, 12, 31, tzinfo=timezone.utc), 2).date().isoformat() == "2027-02-28")

# --- who gets a coupon ---------------------------------------------------------
customer = signup("customer@example.com", plan="starter")
friend = signup("friend@example.com")

r = client.get("/api/v1/billing/loyalty-coupon", headers=friend).json()
check("a free account has no coupon, and is told why", r["coupon"] is None and "paid plan" in r["reason"])

mine = client.get("/api/v1/billing/loyalty-coupon", headers=customer).json()["coupon"]
check("a paying customer gets a 25% coupon for their own plan, for 3 months",
      (mine["percent_off"], mine["plan"], mine["duration_months"], mine["usable"]) == (25.0, "starter", 3, True))
check("it expires 2 months after the plan period ends (17 Nov + 30 days + 2 months)", mine["expires_at"] == "2027-02-17")
check("the code is the same every time it is asked for",
      client.get("/api/v1/billing/loyalty-coupon", headers=customer).json()["coupon"]["code"] == mine["code"])
check("the Stripe coupon is limited to that plan's product and to 3 months",
      len(coupons) == 1 and list(coupons.values())[0]["applies_to"] == {"products": ["prod_TCbK"]}
      and list(coupons.values())[0]["duration_in_months"] == 3)
check("the code can be redeemed once", list(codes.values())[0]["max_redemptions"] == 1)
check("the offer is described on /plans",
      client.get("/api/v1/billing/plans").json()["loyalty"] == {"percent_off": 25, "duration_months": 3,
                                                               "valid_months_after_plan_end": 2, "max_redemptions": 1})

# --- someone else redeems it ---------------------------------------------------
code = mine["code"]
check("a non-customer can check the code (any letter case)",
      client.post("/api/v1/billing/check-coupon", headers=friend, json={"code": code.lower(), "plan": "starter"}).status_code == 200)
r = client.post("/api/v1/billing/check-coupon", headers=friend, json={"code": code, "plan": "business"})
check("it is refused for another plan", r.status_code == 400 and "Starter plan only" in r.json()["detail"])
r = client.post("/api/v1/billing/check-coupon", headers=friend, json={"code": "LOYAL-NOTREAL1"})
check("an unknown code is refused", r.status_code == 400 and "not valid" in r.json()["detail"])

r = client.post("/api/v1/billing/create-checkout-session", headers=friend, json={"plan": "starter", "coupon_code": code})
check("checkout with the code applies the coupon",
      r.status_code == 200 and r.json()["discount_note"] is None
      and checkout_calls[-1]["discounts"] == [{"promotion_code": list(codes)[0]}])
r = client.post("/api/v1/billing/create-checkout-session", headers=friend, json={"plan": "business", "coupon_code": code})
check("checkout on the wrong plan is refused, not charged at full price", r.status_code == 400 and len(checkout_calls) == 1)
r = client.post("/api/v1/billing/create-checkout-session", headers=friend, json={"plan": "starter"})
check("checkout without a code has no discount", r.status_code == 200 and "discounts" not in checkout_calls[-1])

# --- one discount only ---------------------------------------------------------
launch = {"id": "co_launch", "valid": True, "percent_off": 50.0, "max_redemptions": 50, "times_redeemed": 2, "duration": "forever"}
billing._get_or_create_promo_coupon = lambda: launch
r = client.post("/api/v1/billing/create-checkout-session", headers=friend, json={"plan": "starter", "coupon_code": code})
check("with the bigger launch offer running, the launch offer is used alone",
      r.status_code == 200 and checkout_calls[-1]["discounts"] == [{"coupon": "co_launch"}])
check("the buyer is told the coupon was kept", "has not been used" in r.json()["discount_note"] and "2027-02-17" in r.json()["discount_note"])
launch["percent_off"] = 10.0
r = client.post("/api/v1/billing/create-checkout-session", headers=friend, json={"plan": "starter", "coupon_code": code})
check("with a smaller general offer, the coupon is used alone",
      checkout_calls[-1]["discounts"] == [{"promotion_code": list(codes)[0]}] and r.json()["discount_note"] is None)
billing._get_or_create_promo_coupon = lambda: None

# --- the customer uses it on their own subscription ----------------------------
r = client.post("/api/v1/billing/apply-coupon", headers=customer, json={"code": code})
check("without an active subscription it cannot be applied", r.status_code == 400 and "no active subscription" in r.json()["detail"])

db = SessionLocal()
org = db.query(User).filter(User.email == "customer@example.com").first().organization
org.stripe_subscription_id, org.subscription_status = "sub_1", "active"
db.commit()
db.close()
subscriptions["sub_1"] = Obj(id="sub_1", discounts=[], items={"data": [{"current_period_end": int(datetime(2026, 12, 17, tzinfo=timezone.utc).timestamp())}]})

check("the owner is offered 'use it on my subscription'",
      client.get("/api/v1/billing/loyalty-coupon", headers=customer).json()["can_apply_to_own_subscription"] is True)
r = client.post("/api/v1/billing/apply-coupon", headers=customer, json={"code": code})
check("applying it discounts the existing subscription",
      r.status_code == 200 and "25% off your next 3 payments" in r.json()["message"] and len(subscriptions["sub_1"]["discounts"]) == 1)
r = client.post("/api/v1/billing/apply-coupon", headers=customer, json={"code": code})
check("a used coupon is refused", r.status_code == 400 and "already been used" in r.json()["detail"])
r = client.post("/api/v1/billing/check-coupon", headers=friend, json={"code": code})
check("...for everyone", r.status_code == 400 and "already been used" in r.json()["detail"])
after = client.get("/api/v1/billing/loyalty-coupon", headers=customer).json()
check("the customer sees it as used, and no second coupon is issued",
      after["coupon"]["used"] is True and after["coupon"]["code"] == code and len(codes) == 1)

# --- a subscription that already has a discount --------------------------------
other = signup("other@example.com", plan="starter")
other_code = client.get("/api/v1/billing/loyalty-coupon", headers=other).json()["coupon"]["code"]
db = SessionLocal()
org = db.query(User).filter(User.email == "other@example.com").first().organization
org.stripe_subscription_id, org.subscription_status = "sub_2", "active"
db.commit()
db.close()
subscriptions["sub_2"] = Obj(id="sub_2", discounts=["di_launch"], items={"data": []})
r = client.post("/api/v1/billing/apply-coupon", headers=other, json={"code": other_code})
check("a subscription that already has a discount cannot take a second one",
      r.status_code == 400 and "only one discount" in r.json()["detail"] and codes[list(codes)[1]]["times_redeemed"] == 0)

# --- expiry and switching off --------------------------------------------------
codes[list(codes)[1]]["expires_at"] = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
r = client.post("/api/v1/billing/check-coupon", headers=friend, json={"code": other_code})
check("an expired coupon is refused with its date", r.status_code == 400 and "expired on 2026-01-01" in r.json()["detail"])
renewed = client.get("/api/v1/billing/loyalty-coupon", headers=other).json()["coupon"]
check("a coupon that expired unused is replaced by a new one", renewed["code"] != other_code and renewed["usable"] is True)

settings.LOYALTY_COUPON_ENABLED = False
check("switched off: no offer on /plans, no coupon",
      client.get("/api/v1/billing/plans").json()["loyalty"] is None
      and client.get("/api/v1/billing/loyalty-coupon", headers=other).json()["coupon"] is None)
print("All loyalty-coupon checks passed.")
