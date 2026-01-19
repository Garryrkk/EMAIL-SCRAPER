from sqlalchemy import Column, String, DateTime, Float, Boolean, ForeignKey, Integer
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base
from app.core.constants import EmailStatus, EmailSource


class Email(Base):
    """Email model."""
    __tablename__ = "emails"

    # Identity
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    address = Column(String, index=True, nullable=False)
    domain = Column(String, index=True, nullable=False)

    # Relations
    company_id = Column(String, ForeignKey("companies.id"), index=True)
    person_id = Column(String, ForeignKey("people.id"))

    # Source & Pattern
    source = Column(String, default=EmailSource.INFERRED, nullable=False)
    pattern_used = Column(String)  # Which pattern generated this

    # Verification Status
    status = Column(String, default=EmailStatus.UNKNOWN, nullable=False, index=True)
    confidence = Column(Float, default=0.0, nullable=False)

    # Verification Details
    syntax_valid = Column(Boolean, default=False)
    dns_valid = Column(Boolean, default=False)
    smtp_check_passed = Column(Boolean, default=False)
    catch_all_domain = Column(Boolean, default=False)

    # Bounce & Deliverability
    bounce_count = Column(Integer, default=0)
    bounce_type = Column(String)  # permanent, temporary, unknown
    last_bounce_at = Column(DateTime)

    # Metadata
    is_role_based = Column(Boolean, default=False)
    is_generic = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)

    # Usage Tracking
    view_count = Column(Integer, default=0)
    export_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_verified_at = Column(DateTime)

    def __repr__(self):
        return f"<Email {self.address}>"