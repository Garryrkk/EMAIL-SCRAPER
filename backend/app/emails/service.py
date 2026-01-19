import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.emails.model import Email
from app.core.constants import EmailStatus

logger = logging.getLogger(__name__)


class EmailService:
    """Email management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_email(
        self,
        address: str,
        domain: str,
        company_id: str = None,
        person_id: str = None,
        source: str = "inferred",
        pattern_used: str = None,
    ) -> Email:
        """Create or get email."""
        # Check if exists
        existing = await self.get_email_by_address(address)
        if existing:
            return existing

        # Create new
        email = Email(
            id=str(uuid.uuid4()),
            address=address,
            domain=domain,
            company_id=company_id,
            person_id=person_id,
            source=source,
            pattern_used=pattern_used,
        )
        self.db.add(email)
        await self.db.flush()
        return email

    async def get_email_by_address(self, address: str) -> Email:
        """Get email by address."""
        result = await self.db.execute(
            select(Email).where(Email.address == address)
        )
        return result.scalars().first()

    async def get_email_by_id(self, email_id: str) -> Email:
        """Get email by ID."""
        result = await self.db.execute(
            select(Email).where(Email.id == email_id)
        )
        return result.scalars().first()

    async def get_emails_by_company(self, company_id: str, limit: int = 100):
        """Get emails by company."""
        result = await self.db.execute(
            select(Email)
            .where(Email.company_id == company_id)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_verification_status(
        self,
        email_id: str,
        status: str,
        confidence: float = 0.0,
        **details,
    ) -> bool:
        """Update email verification status."""
        email = await self.get_email_by_id(email_id)
        if not email:
            return False

        email.status = status
        email.confidence = confidence
        email.last_verified_at = datetime.utcnow()

        # Update details
        for key, value in details.items():
            if hasattr(email, key):
                setattr(email, key, value)

        await self.db.flush()
        return True

    async def record_bounce(
        self,
        email_id: str,
        bounce_type: str = "permanent",
    ) -> bool:
        """Record email bounce."""
        email = await self.get_email_by_id(email_id)
        if not email:
            return False

        email.bounce_count += 1
        email.bounce_type = bounce_type
        email.last_bounce_at = datetime.utcnow()

        # Mark as invalid after certain bounces
        if email.bounce_count > 2:
            email.status = EmailStatus.INVALID

        await self.db.flush()
        return True

    async def record_view(self, email_id: str) -> bool:
        """Record email view."""
        email = await self.get_email_by_id(email_id)
        if not email:
            return False

        email.view_count += 1
        await self.db.flush()
        return True

    async def record_export(self, email_id: str) -> bool:
        """Record email export."""
        email = await self.get_email_by_id(email_id)
        if not email:
            return False

        email.export_count += 1
        await self.db.flush()
        return True

    async def update_risk_score(self, email_id: str, risk_score: float) -> bool:
        """Update email risk score."""
        email = await self.get_email_by_id(email_id)
        if not email:
            return False

        email.risk_score = risk_score
        await self.db.flush()
        return True

    async def bulk_update_status(
        self,
        email_ids: list,
        status: str,
    ) -> bool:
        """Bulk update email status."""
        result = await self.db.execute(
            select(Email).where(Email.id.in_(email_ids))
        )
        emails = result.scalars().all()

        for email in emails:
            email.status = status
            email.last_verified_at = datetime.utcnow()

        await self.db.flush()
        return True