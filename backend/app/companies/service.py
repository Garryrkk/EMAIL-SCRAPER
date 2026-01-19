import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.companies.model import Company
from app.core.constants import CompanyStatus

logger = logging.getLogger(__name__)


class CompanyService:
    """Company management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_company(
        self,
        domain: str,
        name: str = None,
    ) -> Company:
        """Create or get company."""
        # Check if exists
        existing = await self.get_company_by_domain(domain)
        if existing:
            return existing

        # Create new
        company = Company(
            id=str(uuid.uuid4()),
            domain=domain,
            name=name or domain,
        )
        self.db.add(company)
        await self.db.flush()
        logger.info(f"Company created: {domain}")
        return company

    async def get_company_by_domain(self, domain: str) -> Company:
        """Get company by domain."""
        result = await self.db.execute(
            select(Company).where(Company.domain == domain)
        )
        return result.scalars().first()

    async def get_company_by_id(self, company_id: str) -> Company:
        """Get company by ID."""
        result = await self.db.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalars().first()

    async def update_company_info(
        self,
        company_id: str,
        **kwargs,
    ) -> bool:
        """Update company information."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        allowed_fields = {
            "name", "industry", "size", "founded_year",
            "website", "linkedin_url",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(company, key, value)

        await self.db.flush()
        return True

    async def set_detected_pattern(
        self,
        company_id: str,
        pattern: str,
        confidence: float,
    ) -> bool:
        """Set detected email pattern."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        company.detected_pattern = pattern
        company.pattern_confidence = confidence
        await self.db.flush()
        logger.info(f"Pattern detected for {company.domain}: {pattern} ({confidence:.2f})")
        return True

    async def update_email_counts(
        self,
        company_id: str,
        crawl_count: int = 0,
        enrichment_count: int = 0,
    ) -> bool:
        """Update email counts."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        company.emails_from_crawl += crawl_count
        company.emails_from_enrichment += enrichment_count
        company.public_emails_count = (
            company.emails_from_crawl + company.emails_from_enrichment
        )
        await self.db.flush()
        return True

    async def update_confidence_score(
        self,
        company_id: str,
        score: float,
    ) -> bool:
        """Update confidence score."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        company.confidence_score = score
        await self.db.flush()
        return True

    async def update_bounce_rate(
        self,
        company_id: str,
        bounce_rate: float,
    ) -> bool:
        """Update bounce rate."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        company.bounce_rate = bounce_rate
        company.last_verified_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def mark_crawled(self, company_id: str) -> bool:
        """Mark company as crawled."""
        company = await self.get_company_by_id(company_id)
        if not company:
            return False

        company.last_crawled_at = datetime.utcnow()
        company.is_verified = True
        await self.db.flush()
        return True