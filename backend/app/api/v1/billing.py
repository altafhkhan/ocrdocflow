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
import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.models.organization import Organization
from app.models.user import User

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


class CheckoutRequest(BaseModel):
    plan: str


@router.get("/plans")
def list_plans():
    return {
        "starter": {"name": "Starter", "price_usd": 19, "invoices_per_month": 500},
        "professional": {"name": "Professional", "price_usd": 59, "invoices_per_month": 3000},
        "business": {"name": "Business", "price_usd": 199, "invoices_per_month": 15000},
    }


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

    try:
        session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": PLAN_PRICE_IDS[payload.plan], "quantity": 1}],
            success_url=f"{FRONTEND_URL}/dashboard?checkout=success",
            cancel_url=f"{FRONTEND_URL}/dashboard?checkout=cancelled",
            # Lets the webhook identify which ORGANIZATION this checkout
            # belongs to.
            client_reference_id=str(org.id),
            metadata={"organization_id": str(org.id), "plan": payload.plan},
        )
    except stripe.error.StripeError:
        logger.exception("Stripe checkout session creation failed")
        raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")

    return {"checkout_url": session.url}


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
        org_id = data.get("client_reference_id") or (data.get("metadata") or {}).get("organization_id")
        plan = (data.get("metadata") or {}).get("plan")
        subscription_id = data.get("subscription")

        if org_id:
            org = db.query(Organization).filter(Organization.id == int(org_id)).first()
            if org and plan in PLAN_PRICE_IDS:
                org.plan = plan
                org.plan_started_at = datetime.now(timezone.utc)
                org.stripe_subscription_id = subscription_id
                org.subscription_status = "active"
                db.commit()
                logger.info(
                    "Organization '%s' upgraded to plan '%s' via Stripe checkout.",
                    org.name, plan,
                )
            else:
                logger.warning(
                    "Webhook checkout.session.completed: could not resolve organization_id=%s plan=%s",
                    org_id, plan,
                )

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