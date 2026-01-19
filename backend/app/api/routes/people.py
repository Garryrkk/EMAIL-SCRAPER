# people.py

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Person, Company, Email
from app.auth.schemas import PersonCreate, PersonRead
from app.api.routes.emails import Email
from app.core.database import get_db
import unicodedata

class PeopleService:
    """
    PeopleService handles all person-related operations:
    - CRUD
    - Enrichment
    - Normalization
    - Confidence calculation
    - Email candidate generation
    """

    def __init__(self, db: Session):
        self.db = db
        self.email_service = Email(db)
        self.enrichment_service = EnrichmentService(db)

    # ------------------------
    # CRUD OPERATIONS
    # ------------------------
    def get_person_by_id(self, person_id: int) -> Optional[PersonRead]:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return None
        return PersonRead.from_orm(person)

    def search_people(
        self,
        company_id: Optional[int] = None,
        job_title: Optional[str] = None,
        name: Optional[str] = None
    ) -> List[PersonRead]:
        query = self.db.query(Person)
        if company_id:
            query = query.filter(Person.company_id == company_id)
        if job_title:
            query = query.filter(Person.job_title.ilike(f"%{job_title}%"))
        if name:
            query = query.filter(
                (Person.first_name.ilike(f"%{name}%")) |
                (Person.last_name.ilike(f"%{name}%"))
            )
        people = query.all()
        # Compute confidence for each person
        for person in people:
            person.confidence_score = compute_person_confidence(person)
        return [PersonRead.from_orm(p) for p in people]

    def create_person(self, data: PersonCreate) -> PersonRead:
        normalized_first, normalized_last = self.normalize_name(
            data.first_name, data.last_name
        )
        person = Person(
            first_name=normalized_first,
            last_name=normalized_last,
            job_title=data.job_title,
            company_id=data.company_id,
            linkedin_url=data.linkedin_url,
            confidence_score=0.0,
            created_at=datetime.utcnow()
        )
        self.db.add(person)
        self.db.commit()
        self.db.refresh(person)

        # Trigger async enrichment if feature enabled
        self.enrichment_service.enqueue_enrichment(person.id)
        return PersonRead.from_orm(person)

    def update_person(self, person_id: int, data: PersonCreate) -> Optional[PersonRead]:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return None
        person.first_name, person.last_name = self.normalize_name(data.first_name, data.last_name)
        person.job_title = data.job_title
        person.linkedin_url = data.linkedin_url
        self.db.commit()
        self.db.refresh(person)
        return PersonRead.from_orm(person)

    # ------------------------
    # NAME NORMALIZATION
    # ------------------------
    def normalize_name(self, first_name: str, last_name: str) -> (str, str):
        # Strip whitespace, remove accents, lowercase
        def clean(name: str) -> str:
            name = name.strip()
            name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
            return name.capitalize()
        return clean(first_name), clean(last_name)

    # ------------------------
    # COMPANY MAPPING
    # ------------------------
    def map_to_company(self, person_id: int, company_id: int) -> bool:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not person or not company:
            return False
        person.company_id = company.id
        self.db.commit()
        return True

    # ------------------------
    # EMAIL CANDIDATE GENERATION
    # ------------------------
    def get_candidates_for_email(self, person_id: int) -> List[str]:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person or not person.company_id:
            return []

        company = self.db.query(Company).filter(Company.id == person.company_id).first()
        if not company:
            return []

        # Generate candidate emails using company patterns
        candidates = self.email_service.generate_candidates(
            first_name=person.first_name,
            last_name=person.last_name,
            domain=company.domain,
            patterns=company.email_patterns
        )
        return candidates

    # ------------------------
    # ENRICHMENT
    # ------------------------
    def enrich_person(self, person_id: int):
        self.enrichment_service.run_enrichment(person_id)
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if person:
            # Update confidence after enrichment
            person.confidence_score = compute_person_confidence(person)
            self.db.commit()
        return person
