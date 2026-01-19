from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base
from app.core.constants import UserPlan, UserStatus


class User(Base):
    """User model."""
    __tablename__ = "users"

    # Identity
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    company = Column(String)

    # Subscription
    plan = Column(String, default=UserPlan.FREE, nullable=False)
    status = Column(String, default=UserStatus.ACTIVE, nullable=False)

    # Credits
    credits = Column(Integer, default=100, nullable=False)
    monthly_credits_limit = Column(Integer, default=1000, nullable=False)

    # Risk Management
    risk_score = Column(Float, default=0.0, nullable=False)
    is_risky = Column(Boolean, default=False, nullable=False)
    suspension_reason = Column(String)

    # Features
    email_verified = Column(Boolean, default=False, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime)

    def __repr__(self):
        return f"<User {self.email}>"