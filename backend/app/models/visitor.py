"""
Tracks anonymous (no-login) "Visitor" tier usage, keyed by IP address -
the only real identifier available for a web visitor (MAC addresses are
never visible to a web server; IP is the standard practical substitute,
though imperfect - shared office/WiFi networks or VPNs can share or
change IPs).

Gating rules (product decision):
  - Uploads 1-5 for a given IP: free, no email required
  - Upload 6: blocked until an email is provided
  - Uploads 6-25 (after email given): free; each one logs a
    "would send marketing email" event (real email sending isn't wired
    up yet - see upload endpoint)
  - Upload 26+: blocked - must create a real account to continue

This is IN ADDITION TO the daily per-session limit (3 files/session/day)
enforced separately in the visitor upload endpoint.
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class VisitorUsage(Base):
    __tablename__ = "visitor_usage"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, nullable=False, unique=True, index=True)
    total_uploads = Column(Integer, nullable=False, default=0)
    email = Column(String, nullable=True)
    email_captured_at = Column(DateTime(timezone=True), nullable=True)
    last_upload_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())