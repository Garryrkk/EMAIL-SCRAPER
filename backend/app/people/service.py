from sqlalchemy.orm import Session
from app.people.model import Person
from app.people.normalizer import NameNormalizer
import logging

logger = logging.getLogger("email_intel")

class PersonService:
    @staticmethod
    def create_person(db: Session, first_name: str, last_name: str, company_domain: str, title: str = "") -> Person:
        person = Person(
            first_name=NameNormalizer.normalize_name(first_name),
            last_name=NameNormalizer.normalize_name(last_name),
            full_name=f"{first_name} {last_name}".strip(),
            title=title,
            company_domain=company_domain
        )
        db.add(person)
        db.commit()
        db.refresh(person)
        return person
    
    @staticmethod
    def search_by_domain(db: Session, domain: str):
        return db.query(Person).filter(Person.company_domain == domain).all()

