from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    # "user" (default, everyone starts here) or "admin" - PLATFORM-level
    # role (controls access to OCRDocFlow's own Admin Panel). This is a
    # different concept from org_role below (which controls what a
    # person can do WITHIN their own company's account).
    role = Column(String, nullable=False, default="user")

    # --- Organization membership -------------------------------------
    # Nullable FOR NOW during migration - every user will have one once
    # the data migration (Stage 1b, already run) backfills existing
    # users into their own 1-person organizations. A later cleanup
    # migration makes this NOT NULL once we're confident everything
    # works correctly through the organization.
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    organization = relationship("Organization", back_populates="members")
    # "owner" (can manage billing, invite/remove members) or "member"
    # (just uses the product under the org's plan).
    org_role = Column(String, nullable=True, default="owner")

    # --- LEGACY FIELDS - superseded by Organization --------------------
    # Kept temporarily, no longer read by app logic (usage_service.py,
    # admin.py, billing.py, auth.py all read from user.organization
    # now) - will be dropped in a final cleanup migration once we're
    # confident nothing still depends on them.
    plan = Column(String, nullable=False, default="free")
    plan_started_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    #  ---- change password from chatgpt------------------------
	
#	from pydantic import BaseModel

#	class ChangePassword(BaseModel):
#	    current_password: str
#	    new_password: str