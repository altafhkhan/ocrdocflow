"""
Stripe payment integration - subscription checkout and webhook handling.

Uses Stripe Checkout (a Stripe-hosted payment page) so raw card details
NEVER touch our server - Security Policy Section 24: "The platform
should receive payment status rather than storing raw card details."

The subscription belongs to the user's ORGANIZATION (not the individual
user) - Professional/Business plans are shared across up to 5/15 team
members. Only the organization's "owner" can start/change a
subscription.

Flow:
  1) User clicks "Upgrade to X" -> POST /create-checkout-session ->
     we create a Stripe Checkout Session and return its URL.
  2) Frontend redirects the browser to that URL - the user enters card
     details directly on Stripe's own page, never ours.
  3) Stripe redirects back to our app (success/cancel) AND separately
     sends a webhook event to /webhook confirming what actually
     happened - the webhook is the SOURCE OF TRUTH, not the redirect
     (a user could close the tab before the redirect fires, but the
     webhook still arrives independently).
  4) The webhook handler updates the ORGANIZATION's plan/subscription
     status - every member of that org immediately shares the new plan.
"""
import calendar
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.services import usage_service

logger = logging.getLogger("ocrdocflow.billing")

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY

# Maps our plan names to the actual Stripe Price IDs created in the
# Stripe Dashboard (test mode while developing).
PLAN_PRICE_IDS = {
    "starter": "price_1U3DmLRl5jDJ23VEjYKOTCbK",
    "professional": "price_1U3DrkRl5jDJ23VE1szBaeVI",
    "business": "price_1U3DuIRl5jDJ23VEJXVROnc3",
}

# Where Stripe sends the browser back to after checkout completes/cancels.
FRONTEND_URL = settings.FRONTEND_URL


PLANS = {
    "starter": {"name": "Starter", "price_usd": 19, "invoices_per_month": 500},
    "professional": {"name": "Professional", "price_usd": 59, "invoices_per_month": 3000},
    "business": {"name": "Business", "price_usd": 199, "invoices_per_month": 15000},
}


class CheckoutRequest(BaseModel):
    plan: str
    # Optional loyalty coupon code typed on the Billing page.
    coupon_code: str | None = None


class CouponRequest(BaseModel):
    code: str
    plan: str | None = None


class ConfirmCheckoutRequest(BaseModel):
    session_id: str


def _session_is_paid(session: dict) -> bool:
    """A finished Checkout Session whose payment went through (or needed
    none, e.g. a 100% discount)."""
    return session.get("status") == "complete" and session.get("payment_status") in ("paid", "no_payment_required")


def _apply_paid_checkout(db: Session, session: dict) -> Organization | None:
    """
    Puts the organization named in a PAID Checkout Session on the plan it
    bought. The one place a plan is ever upgraded - used by both the Stripe
    webhook and /confirm-checkout, so the two paths cannot disagree.

    Safe to run more than once for the same session (the webhook and the
    browser's return can both arrive, in either order, and Stripe may
    resend an event): the second run changes nothing, and in particular
    does not restart the billing period.
    """
    org_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("organization_id")
    plan = (session.get("metadata") or {}).get("plan")
    subscription_id = session.get("subscription")
    if isinstance(subscription_id, dict):  # expanded object rather than an id
        subscription_id = subscription_id.get("id")

    if not org_id or not str(org_id).isdigit() or plan not in PLAN_PRICE_IDS:
        logger.warning("Paid checkout could not be applied: organization_id=%s plan=%s", org_id, plan)
        return None
    org = db.query(Organization).filter(Organization.id == int(org_id)).first()
    if org is None:
        logger.warning("Paid checkout names an unknown organization_id=%s", org_id)
        return None

    already_applied = (
        org.plan == plan
        and org.subscription_status == "active"
        and org.stripe_subscription_id == subscription_id
    )
    if not already_applied:
        org.plan = plan
        org.plan_started_at = datetime.now(timezone.utc)
        org.stripe_subscription_id = subscription_id
        org.subscription_status = "active"
        db.commit()
        logger.warning("Organization '%s' (id %s) is now on plan '%s' via Stripe checkout.", org.name, org.id, plan)
    return org


# --- Launch promotion ------------------------------------------------------
# "X% off for the first N subscribers" is modelled as ONE Stripe coupon with
# max_redemptions=N (and optionally redeem_by). We look it up by metadata so
# restarting the API never creates a second coupon, and we read it fresh on
# every /plans call so the "seats left" counter is live. Stripe is the
# source of truth: it refuses the coupon once N subscriptions used it.
_PROMO_CAMPAIGN_KEY = "launch-{pct}-{seats}"


def _promo_campaign_key() -> str:
    return _PROMO_CAMPAIGN_KEY.format(pct=settings.PROMO_PERCENT_OFF, seats=settings.PROMO_MAX_REDEMPTIONS)


def _promo_redeem_by() -> int | None:
    if not settings.PROMO_ENDS_AT:
        return None
    ends = datetime.fromisoformat(settings.PROMO_ENDS_AT)
    if ends.tzinfo is None:
        ends = ends.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    return int(ends.timestamp())


def _get_or_create_promo_coupon() -> dict | None:
    """Returns the live Stripe Coupon (as a plain dict) for the current
    campaign, or None when the promotion is off / Stripe is not configured /
    Stripe errors. Plain dicts because this stripe library's objects don't
    support .get() (same reason the webhook re-parses its payload)."""
    if not settings.PROMO_ENABLED or not settings.STRIPE_SECRET_KEY:
        return None
    key = _promo_campaign_key()
    try:
        for coupon in stripe.Coupon.list(limit=100).auto_paging_iter():
            data = json.loads(str(coupon))
            if (data.get("metadata") or {}).get("campaign") == key:
                return data
        params = {
            "name": settings.PROMO_NAME,
            "percent_off": settings.PROMO_PERCENT_OFF,
            "duration": settings.PROMO_DURATION,
            "max_redemptions": settings.PROMO_MAX_REDEMPTIONS,
            "metadata": {"campaign": key, "app": "ocrdocflow"},
        }
        if settings.PROMO_DURATION == "repeating":
            params["duration_in_months"] = settings.PROMO_DURATION_MONTHS
        redeem_by = _promo_redeem_by()
        if redeem_by:
            params["redeem_by"] = redeem_by
        coupon = stripe.Coupon.create(**params)
        logger.info("Created launch promotion coupon %s (%s)", coupon.id, key)
        return json.loads(str(coupon))
    except stripe.error.StripeError:
        logger.exception("Could not load/create the promotion coupon")
        return None


def _promo_info(coupon) -> dict | None:
    """Shape the coupon for the frontend: None means there is no offer to show."""
    if coupon is None or not coupon.get("valid", False):
        return None
    seats_total = coupon.get("max_redemptions") or 0
    seats_left = max(0, seats_total - (coupon.get("times_redeemed") or 0))
    if seats_total and seats_left == 0:
        return None
    redeem_by = coupon.get("redeem_by")
    return {
        "name": coupon.get("name") or settings.PROMO_NAME,
        "percent_off": coupon.get("percent_off"),
        "seats_total": seats_total,
        "seats_left": seats_left,
        "duration": coupon.get("duration"),
        "duration_in_months": coupon.get("duration_in_months"),
        "ends_at": datetime.fromtimestamp(redeem_by, tz=timezone.utc).date().isoformat() if redeem_by else None,
    }


# --- Loyalty coupon ----------------------------------------------------------
# A reward for paying customers that also brings in new ones. Each paying
# organization gets ONE code (a Stripe Promotion Code) for 25% off the plan it
# is on, for the first 3 payments. The owner can use it on their own
# subscription or give it to anyone - the person redeeming it does not have to
# be a customer already. It can be redeemed once, and expires 2 months after
# the end of the owner's current plan period.
#
# Everything lives in Stripe (no table of ours):
#   Coupon          one per plan, found again by metadata["campaign"]
#   Promotion Code  one per organization; its id is kept in the Stripe
#                   Customer's metadata["loyalty_code_id"]
_LOYALTY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O/1/I to misread
_loyalty_coupon_ids: dict[str, str] = {}


def _to_dict(stripe_object) -> dict:
    """Stripe objects of this library version lack .get(); use plain dicts."""
    return json.loads(str(stripe_object))


def loyalty_policy() -> dict | None:
    """The offer in numbers, for the Billing page. None when switched off."""
    if not settings.LOYALTY_COUPON_ENABLED:
        return None
    return {
        "percent_off": settings.LOYALTY_PERCENT_OFF,
        "duration_months": settings.LOYALTY_DURATION_MONTHS,
        "valid_months_after_plan_end": settings.LOYALTY_VALID_MONTHS_AFTER_PLAN_END,
        "max_redemptions": settings.LOYALTY_MAX_REDEMPTIONS,
    }


def _add_months(moment: datetime, months: int) -> datetime:
    month_index = moment.month - 1 + months
    year, month = moment.year + month_index // 12, month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _plan_period_end(org: Organization) -> datetime:
    """When the organization's current paid period ends: Stripe's own date for
    a Stripe subscription, else our usage period (plan set by an admin)."""
    if org.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
        try:
            subscription = _to_dict(stripe.Subscription.retrieve(org.stripe_subscription_id))
            ends = [subscription.get("current_period_end")] + [
                item.get("current_period_end") for item in ((subscription.get("items") or {}).get("data") or [])
            ]
            ends = [e for e in ends if e]
            if ends:
                return datetime.fromtimestamp(max(ends), tz=timezone.utc)
        except stripe.error.StripeError:
            logger.warning("Could not read subscription %s for the plan end date", org.stripe_subscription_id)
    start = usage_service.get_period_start(org)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start + timedelta(days=usage_service.get_period_length_days(org))


def _loyalty_coupon_id(plan: str) -> str:
    """The Stripe Coupon behind every loyalty code of this plan (created once)."""
    key = f"loyalty-{settings.LOYALTY_PERCENT_OFF}-{settings.LOYALTY_DURATION_MONTHS}m-{plan}"
    if key in _loyalty_coupon_ids:
        return _loyalty_coupon_ids[key]
    for coupon in stripe.Coupon.list(limit=100).auto_paging_iter():
        data = _to_dict(coupon)
        if (data.get("metadata") or {}).get("campaign") == key:
            _loyalty_coupon_ids[key] = data["id"]
            return data["id"]
    product = _to_dict(stripe.Price.retrieve(PLAN_PRICE_IDS[plan])).get("product")
    coupon = stripe.Coupon.create(
        name=f"Loyalty {settings.LOYALTY_PERCENT_OFF}% off - {PLANS[plan]['name']}",
        percent_off=settings.LOYALTY_PERCENT_OFF,
        duration="repeating",
        duration_in_months=settings.LOYALTY_DURATION_MONTHS,
        # Stripe itself refuses the code on any other plan.
        applies_to={"products": [product]},
        metadata={"campaign": key, "app": "ocrdocflow", "plan": plan},
    )
    logger.info("Created loyalty coupon %s (%s)", coupon.id, key)
    _loyalty_coupon_ids[key] = coupon.id
    return coupon.id


def _create_promotion_code(**params):
    """Stripe moved the coupon reference into `promotion` in newer API
    versions; fall back to the older `coupon=` shape if this one is refused."""
    coupon_id = params.pop("coupon")
    try:
        return stripe.PromotionCode.create(promotion={"type": "coupon", "coupon": coupon_id}, **params)
    except stripe.error.InvalidRequestError:
        return stripe.PromotionCode.create(coupon=coupon_id, **params)


def _loyalty_percent(code: dict) -> float:
    return float((code.get("metadata") or {}).get("percent_off") or settings.LOYALTY_PERCENT_OFF)


def _loyalty_info(code: dict) -> dict:
    """Shape a loyalty Promotion Code for the frontend."""
    meta = code.get("metadata") or {}
    expires_at = code.get("expires_at")
    max_redemptions = code.get("max_redemptions") or 0
    used = bool(max_redemptions) and (code.get("times_redeemed") or 0) >= max_redemptions
    expired = bool(expires_at) and expires_at <= datetime.now(timezone.utc).timestamp()
    plan = meta.get("plan")
    return {
        "code": code.get("code"),
        "plan": plan,
        "plan_name": PLANS.get(plan, {}).get("name", plan),
        "percent_off": _loyalty_percent(code),
        "duration_months": int(meta.get("duration_months") or settings.LOYALTY_DURATION_MONTHS),
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).date().isoformat() if expires_at else None,
        "used": used,
        "expired": expired,
        "usable": bool(code.get("active")) and not used and not expired,
    }


def _validate_loyalty_code(raw_code: str | None, plan: str | None) -> dict:
    """Returns the Stripe Promotion Code (dict) for a code typed by a buyer,
    or raises a 400 saying, in plain words, why it cannot be used."""
    code = (raw_code or "").strip().upper()
    if not code or len(code) > 40:
        raise HTTPException(status_code=400, detail="Please enter a coupon code.")
    if not settings.LOYALTY_COUPON_ENABLED or not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Coupons are not available at the moment.")
    try:
        found = _to_dict(stripe.PromotionCode.list(code=code, limit=1)).get("data") or []
    except stripe.error.StripeError:
        logger.exception("Could not look up coupon code")
        raise HTTPException(status_code=502, detail="Could not check the coupon. Please try again.")
    promotion_code = found[0] if found else None
    if promotion_code is None or (promotion_code.get("metadata") or {}).get("campaign") != "loyalty":
        raise HTTPException(status_code=400, detail="This coupon code is not valid.")
    info = _loyalty_info(promotion_code)
    if info["used"]:
        raise HTTPException(status_code=400, detail="This coupon has already been used.")
    if info["expired"] or not info["usable"]:
        raise HTTPException(status_code=400, detail=f"This coupon expired on {info['expires_at']}." if info["expired"] else "This coupon is no longer valid.")
    if plan is not None and info["plan"] != plan:
        raise HTTPException(status_code=400, detail=f"This coupon is for the {info['plan_name']} plan only.")
    return promotion_code


def _ensure_customer(db: Session, org: Organization, email: str) -> str:
    if not org.stripe_customer_id:
        customer = stripe.Customer.create(email=email, metadata={"organization_id": str(org.id)})
        org.stripe_customer_id = customer.id
        db.commit()
    return org.stripe_customer_id


@router.get("/loyalty-coupon")
def get_loyalty_coupon(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The caller's organization's loyalty coupon, created the first time a
    paying owner opens the Billing page. A new one is issued only when the
    previous one ran out unused (expired, or the plan changed) - a coupon
    that has been redeemed is finished.
    """
    policy = loyalty_policy()
    org = current_user.organization

    def none(reason: str) -> dict:
        return {"coupon": None, "reason": reason, "policy": policy, "can_apply_to_own_subscription": False}

    if policy is None or not settings.STRIPE_SECRET_KEY:
        return none("Loyalty coupons are not available at the moment.")
    if org is None or org.plan not in PLAN_PRICE_IDS:
        return none("Subscribe to a paid plan to receive your loyalty coupon.")
    if current_user.org_role != "owner":
        return none("Your organization's owner can see and share the loyalty coupon.")

    try:
        customer_id = _ensure_customer(db, org, current_user.email)
        customer = _to_dict(stripe.Customer.retrieve(customer_id))
        code_id = (customer.get("metadata") or {}).get("loyalty_code_id")
        code = _to_dict(stripe.PromotionCode.retrieve(code_id)) if code_id else None

        if code is not None:
            info = _loyalty_info(code)
            if info["used"]:
                pass  # redeemed: this customer's coupon is finished
            elif info["expired"] or info["plan"] != org.plan or not info["usable"]:
                # Ran out unused, or the customer changed plan: replace it.
                if code.get("active"):
                    stripe.PromotionCode.modify(code["id"], active=False)
                code = None

        if code is None:
            expires = _add_months(_plan_period_end(org), settings.LOYALTY_VALID_MONTHS_AFTER_PLAN_END)
            created = _create_promotion_code(
                coupon=_loyalty_coupon_id(org.plan),
                code="LOYAL-" + "".join(secrets.choice(_LOYALTY_ALPHABET) for _ in range(8)),
                max_redemptions=settings.LOYALTY_MAX_REDEMPTIONS,
                expires_at=int(expires.timestamp()),
                metadata={
                    "campaign": "loyalty", "app": "ocrdocflow", "organization_id": str(org.id),
                    "plan": org.plan, "percent_off": str(settings.LOYALTY_PERCENT_OFF),
                    "duration_months": str(settings.LOYALTY_DURATION_MONTHS),
                },
            )
            code = _to_dict(created)
            stripe.Customer.modify(customer_id, metadata={"loyalty_code_id": code["id"]})
            logger.warning("Issued loyalty coupon for organization '%s' (id %s), valid until %s.",
                           org.name, org.id, expires.date().isoformat())
    except stripe.error.StripeError:
        logger.exception("Could not load/create the loyalty coupon")
        return none("Your loyalty coupon could not be loaded just now. Please try again later.")

    info = _loyalty_info(code)
    return {
        "coupon": info,
        "reason": None,
        "policy": policy,
        "can_apply_to_own_subscription": bool(info["usable"] and org.stripe_subscription_id
                                              and org.subscription_status == "active"),
    }


@router.post("/check-coupon")
def check_coupon(payload: CouponRequest, _user: User = Depends(get_current_user)):
    """Tells the Billing page what a typed code is worth, before checkout."""
    return {"coupon": _loyalty_info(_validate_loyalty_code(payload.code, payload.plan))}


@router.post("/apply-coupon")
def apply_coupon_to_subscription(
    payload: CouponRequest,
    current_user: User = Depends(get_current_user),
):
    """An existing subscriber uses a loyalty coupon on the subscription they
    already have: the discount starts with their next payment."""
    org = current_user.organization
    if org is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    if current_user.org_role != "owner":
        raise HTTPException(status_code=403, detail="Only the organization's owner can manage billing.")
    if not org.stripe_subscription_id or org.subscription_status != "active":
        raise HTTPException(status_code=400, detail="You have no active subscription. Enter the coupon when you subscribe instead.")

    code = _validate_loyalty_code(payload.code, org.plan)
    try:
        subscription = _to_dict(stripe.Subscription.retrieve(org.stripe_subscription_id))
        if subscription.get("discounts") or subscription.get("discount"):
            raise HTTPException(
                status_code=400,
                detail="Your subscription already has a discount, and only one discount can be used at a time. "
                       "You can give this coupon to someone else instead.",
            )
        stripe.Subscription.modify(org.stripe_subscription_id, discounts=[{"promotion_code": code["id"]}])
    except stripe.error.StripeError as exc:
        logger.warning("Could not apply loyalty coupon to subscription %s: %s", org.stripe_subscription_id, exc)
        raise HTTPException(status_code=400, detail="This coupon could not be applied to your subscription.")

    info = _loyalty_info(code)
    logger.warning("Organization '%s' (id %s) applied a loyalty coupon to its subscription.", org.name, org.id)
    return {
        "status": "applied",
        "message": f"Coupon applied: {info['percent_off']:g}% off your next {info['duration_months']} payments.",
    }


@router.get("/plans")
def list_plans():
    promo = _promo_info(_get_or_create_promo_coupon())
    plans = {}
    for key, plan in PLANS.items():
        entry = dict(plan)
        if promo:
            entry["promo_price_usd"] = round(plan["price_usd"] * (100 - promo["percent_off"]) / 100, 2)
        plans[key] = entry
    return {"plans": plans, "promo": promo, "payments_live": payments_live(), "loyalty": loyalty_policy()}


def payments_live() -> bool:
    """True only with a live Stripe secret key. With no key or a test key
    (sk_test_...), checkout cannot take real money, and the Billing page
    says so instead of letting a buyer think the product is broken."""
    return settings.STRIPE_SECRET_KEY.startswith("sk_live_")


@router.post("/create-checkout-session")
def create_checkout_session(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.plan not in PLAN_PRICE_IDS:
        raise HTTPException(status_code=400, detail="Unknown plan.")

    org = current_user.organization
    if org is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    if current_user.org_role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Only the organization's owner can manage billing.",
        )

    # Reuse the same Stripe Customer across multiple checkouts/plan
    # changes for this organization, rather than creating a new one
    # every time.
    if not org.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={"organization_id": str(org.id)},
        )
        org.stripe_customer_id = customer.id
        db.commit()

    session_params = dict(
        customer=org.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": PLAN_PRICE_IDS[payload.plan], "quantity": 1}],
        # {CHECKOUT_SESSION_ID} is filled in by Stripe. The dashboard hands
        # it to /confirm-checkout, which asks Stripe whether it was paid.
        success_url=f"{FRONTEND_URL}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/dashboard?checkout=cancelled",
        # Lets the webhook identify which ORGANIZATION this checkout
        # belongs to.
        client_reference_id=str(org.id),
        metadata={"organization_id": str(org.id), "plan": payload.plan},
    )

    # Only ONE discount ever applies to a subscription.
    #  - Launch promotion: applied automatically while seats remain. Stripe
    #    counts a redemption when the subscription is actually created, so
    #    two people racing for the last seat are resolved by Stripe, not us.
    #  - Loyalty coupon: only when the buyer typed a code. If the launch
    #    offer is at least as big, the launch offer is used and the coupon
    #    is left untouched for later.
    coupon = _get_or_create_promo_coupon()
    promo = _promo_info(coupon)
    loyalty_code = _validate_loyalty_code(payload.coupon_code, payload.plan) if (payload.coupon_code or "").strip() else None
    discount_note = None
    used_loyalty = False
    if loyalty_code and promo and (promo["percent_off"] or 0) >= _loyalty_percent(loyalty_code):
        session_params["discounts"] = [{"coupon": coupon["id"]}]
        discount_note = (
            f"Only one discount can be used at a time. The launch offer ({promo['percent_off']:g}% off) is bigger "
            f"than your coupon ({_loyalty_percent(loyalty_code):g}% off), so the launch offer is applied. Your coupon "
            f"has not been used and stays valid until {_loyalty_info(loyalty_code)['expires_at']}."
        )
    elif loyalty_code:
        session_params["discounts"] = [{"promotion_code": loyalty_code["id"]}]
        used_loyalty = True
    elif promo:
        session_params["discounts"] = [{"coupon": coupon["id"]}]

    try:
        session = stripe.checkout.Session.create(**session_params)
    except stripe.error.StripeError as exc:
        if used_loyalty:
            # Never fall back to full price behind the buyer's back.
            logger.warning("Checkout with loyalty coupon failed: %s", exc)
            raise HTTPException(status_code=400, detail="This coupon could not be applied. Please check the code or subscribe without it.")
        if "discounts" in session_params:
            # Most likely the last seat went just now - retry at full price
            # rather than failing the upgrade.
            logger.warning("Checkout with promotion failed (%s); retrying without it", exc)
            session_params.pop("discounts")
            try:
                session = stripe.checkout.Session.create(**session_params)
            except stripe.error.StripeError:
                logger.exception("Stripe checkout session creation failed")
                raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")
        else:
            logger.exception("Stripe checkout session creation failed")
            raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")

    return {"checkout_url": session.url, "discount_note": discount_note}


@router.post("/confirm-checkout")
def confirm_checkout(
    payload: ConfirmCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Called by the dashboard when Stripe sends the buyer back after paying.

    The plan used to change ONLY when Stripe's webhook reached us. If that
    call was late, failed, or the webhook was never registered (as on the
    live server until 2026-11-14), a customer who had paid came back to a
    dashboard still saying "free". Here we ask Stripe directly about this
    one session and apply it at once; the webhook stays as the second path
    for when the buyer closes the tab before returning.

    Nothing in the request is trusted: the session is fetched from Stripe
    with our secret key, it must be finished and paid, and it must belong
    to the caller's own organization.
    """
    org = current_user.organization
    if org is None:
        raise HTTPException(status_code=400, detail="No organization found for this account.")
    if not payload.session_id.startswith("cs_") or len(payload.session_id) > 200:
        raise HTTPException(status_code=400, detail="That is not a checkout session.")

    try:
        session = stripe.checkout.Session.retrieve(payload.session_id).to_dict()
    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Checkout session not found.")
    except stripe.error.StripeError:
        logger.exception("Could not read checkout session from Stripe")
        raise HTTPException(status_code=502, detail="Could not reach the payment provider. Please refresh in a minute.")

    # Someone else's session answers exactly like one that does not exist.
    if str(session.get("client_reference_id")) != str(org.id):
        raise HTTPException(status_code=404, detail="Checkout session not found.")

    if not _session_is_paid(session):
        return {"status": "pending", "plan": org.plan,
                "message": "Your payment has not been confirmed yet. Refresh this page in a minute."}

    applied = _apply_paid_checkout(db, session)
    if applied is None:
        raise HTTPException(status_code=409, detail="The payment went through, but the plan could not be applied. Please contact support.")
    name = PLANS.get(applied.plan, {}).get("name", applied.plan)
    return {"status": "active", "plan": applied.plan, "message": f"Payment received. You are now on the {name} plan."}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Called directly by Stripe's servers (not by our frontend) - no
    login/JWT involved. Authenticity is verified via the signature
    header instead (Stripe signs every event with your webhook secret).
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning("Invalid Stripe webhook signature - rejected.")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    # construct_event() above verified the signature (proves this really
    # came from Stripe) - but we re-parse the RAW payload as a plain
    # Python dict for actually reading the data, rather than using
    # construct_event()'s returned StripeObject, which doesn't support
    # dict-style .get() calls the way a plain dict does in this version
    # of the library.
    event_dict = json.loads(payload)
    event_type = event_dict["type"]
    data = event_dict["data"]["object"]

    if event_type == "checkout.session.completed":
        # Same code path as /confirm-checkout; whichever arrives second is a no-op.
        if _session_is_paid(data):
            _apply_paid_checkout(db, data)
        else:
            logger.warning("Webhook checkout.session.completed for an unpaid session %s - ignored.", data.get("id"))

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        org = db.query(Organization).filter(Organization.stripe_subscription_id == subscription_id).first()
        if org:
            org.plan = "free"
            org.subscription_status = "canceled"
            org.plan_started_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Organization '%s' subscription canceled, reverted to free plan.", org.name)

    return {"status": "received"}