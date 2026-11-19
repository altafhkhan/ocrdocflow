"""
One row per warning email the retention job has sent to an organization,
so the same warning is never sent twice for the same plan period and so
nothing is deleted before its warning went out
(services/retention_service.py).
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base


class RetentionNotice(Base):
    __tablename__ = "retention_notices"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_start", "kind", name="uq_retention_notice"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    # Start of the plan period the warning is about (for kind "ended":
    # the moment the paid plan ended).
    period_start = Column(DateTime(timezone=True), nullable=False)
    # "quota_80", "quota_90" - share of the invoice quota used
    # "period_90", "period_95" - share of the plan period passed
    # "ended" - the paid plan ended; its invoices go the next day
    kind = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
