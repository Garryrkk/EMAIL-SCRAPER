from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, JSON
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base
from app.core.constants import CompanyStatus


class Company(Base):
    """Company model."""
    __tablename__ = "companies"

    # Identity
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)

    # Company Info
    industry = Column(String)
    size = Column(String)  # e.g., "1-10", "11-50", "51-200"
    founded_year = Column(Integer)
    website = Column(String)
    linkedin_url = Column(String)

    # Email Patterns
    detected_pattern = Column(String)  # e.g., "firstname.lastname@domain"
    pattern_confidence = Column(Float, default=0.0, nullable=False)

    # Public Emails Found
    public_emails_count = Column(Integer, default=0, nullable=False)
    emails_from_crawl = Column(Integer, default=0, nullable=False)
    emails_from_enrichment = Column(Integer, default=0, nullable=False)

    # Confidence & Signals
    confidence_score = Column(Float, default=0.0, nullable=False)
    bounce_rate = Column(Float, default=0.0, nullable=False)
    accept_all_probability = Column(Float, default=0.0, nullable=False)

    # Status
    status = Column(String, default=CompanyStatus.ACTIVE, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Metadata
    company_metadata = Column(String)
    last_crawled_at = Column(DateTime)
    last_verified_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Company {self.domain}>"