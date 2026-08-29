"""
An Organization owns the subscription plan and billing - NOT the
individual User (that's the whole point of this feature: Professional
plan = up to 5 users sharing one plan/quota, Business = up to 15).

Every user belongs to exactly one Organization, even solo Starter/Free
users - they just get a 1-person org. This keeps the model consistent
rather than having two different code paths for "solo user" vs
"company account".
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

# Matches the pricing plan's stated user counts per tier.
PLAN_MAX_MEMBERS = {
    "free": 1,
    "starter": 1,
    "professional": 5,
    "business": 15,
}


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    plan = Column(String, nullable=False, default="free")
    # NULL means "use created_at instead" - same convention as the old
    # User.plan_started_at had, kept simple (no backfill needed).
    plan_started_at = Column(DateTime(timezone=True), nullable=True)

    # Stripe integration (Security Policy Section 24 - we never store
    # raw card data, only Stripe's own reference IDs).
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("User", back_populates="organization")