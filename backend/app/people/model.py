from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base


class Person(Base):
    """Person model."""
    __tablename__ = "people"

    # Identity
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), index=True)

    # Name
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    full_name = Column(String, index=True)

    # Title & Role
    title = Column(String)
    department = Column(String)
    seniority = Column(String)  # e.g., "executive", "manager", "individual"

    # Contact
    linkedin_url = Column(String, unique=True)
    twitter_url = Column(String)

    # Source
    source = Column(String)  # Where we found this person
    is_verified = Column(String, default=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Person {self.full_name}>"