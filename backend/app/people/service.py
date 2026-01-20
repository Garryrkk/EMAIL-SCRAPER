import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.people.model import Person

logger = logging.getLogger(__name__)


class PersonService:
    """Person management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_person(
        self,
        company_id: str,
        first_name: str,
        last_name: str,
        title: str = None,
        linkedin_url: str = None,
    ) -> Person:
        """Create person record."""
        person = Person(
            id=str(uuid.uuid4()),
            company_id=company_id,
            first_name=first_name.strip() if first_name else None,
            last_name=last_name.strip() if last_name else None,
            full_name=f"{first_name} {last_name}".strip() if first_name and last_name else None,
            title=title,
            linkedin_url=linkedin_url,
        )
        self.db.add(person)
        await self.db.flush()
        logger.info(f"Person created: {person.full_name}")
        return person

    async def get_person_by_id(self, person_id: str) -> Person:
        """Get person by ID."""
        result = await self.db.execute(
            select(Person).where(Person.id == person_id)
        )
        return result.scalars().first()

    async def get_persons_by_company(self, company_id: str) -> list:
        """Get all persons at company."""
        result = await self.db.execute(
            select(Person).where(Person.company_id == company_id)
        )
        return result.scalars().all()

    async def update_person(self, person_id: str, **kwargs) -> bool:
        """Update person."""
        person = await self.get_person_by_id(person_id)
        if not person:
            return False

        allowed_fields = {"title", "department", "seniority", "linkedin_url", "twitter_url"}
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(person, key, value)

        await self.db.flush()
        return True