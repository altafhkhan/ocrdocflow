"""
Admin action audit trail (Security Policy Section 17 - Logging and
Audit Trail: "Administrators should not be able to silently alter...
without a record"). Every admin action that changes something (role,
plan, deletions) writes one row here. This table is append-only from
the API's perspective - there's no admin endpoint to edit or delete
audit entries.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.db.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # e.g. "role_changed", "plan_changed", "document_deleted"
    action = Column(String, nullable=False)
    # e.g. "user" or "document" - what kind of thing was affected
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)
    # Human-readable summary, e.g. "role: user -> admin" or
    # "deleted document 'invoice.pdf' (id=42) belonging to user@example.com"
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())