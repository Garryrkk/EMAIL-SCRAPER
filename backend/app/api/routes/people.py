from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models import Person, Company, Email
from app.auth.schemas import PersonCreate, PersonRead
from app.api.routes.emails import EmailService
from app.api.deps import get_db
import unicodedata
import re

# Personal email domains to exclude from pattern learning
PERSONAL_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
    'icloud.com', 'aol.com', 'protonmail.com', 'mail.com'
}

class PeopleService:
    """
    PeopleService handles all person-related operations:
    - CRUD
    - Enrichment
    - Normalization
    - Three-layer confidence calculation (existence, association, deliverability)
    - Email candidate generation (gated by pattern confidence)
    """

    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService(db)
        self.enrichment_service = EnrichmentService(db)

    # ------------------------
    # CRUD OPERATIONS
    # ------------------------
    def get_person_by_id(self, person_id: int) -> Optional[PersonRead]:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return None
        # Update confidence before returning
        self._update_layered_confidence(person)
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
        # Update confidence for each person
        for person in people:
            self._update_layered_confidence(person)
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
            existence_confidence=0.0,
            association_confidence=0.0,
            deliverability_confidence=0.0,
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
        self._update_layered_confidence(person)
        return PersonRead.from_orm(person)

    # ------------------------
    # NAME NORMALIZATION
    # ------------------------
    def normalize_name(self, first_name: str, last_name: str) -> Tuple[str, str]:
        """Strip whitespace, remove accents, capitalize"""
        def clean(name: str) -> str:
            name = name.strip()
            # Remove accents
            name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
            return name.capitalize()
        return clean(first_name), clean(last_name)

    # ------------------------
    # THREE-LAYER CONFIDENCE SYSTEM
    # ------------------------
    def _update_layered_confidence(self, person: Person) -> None:
        """
        Updates the three-layer confidence system:
        1. Existence confidence (1.0 if discovered email exists, 0.0 otherwise)
        2. Association confidence (pattern-based probability)
        3. Deliverability confidence (SMTP + time decay)
        """
        # Get all emails for this person
        emails = self.db.query(Email).filter(Email.person_id == person.id).all()
        
        # Layer 1: Existence confidence
        discovered_emails = [e for e in emails if e.source == 'discovered' and e.exists]
        person.existence_confidence = 1.0 if discovered_emails else 0.0
        
        # Layer 2: Association confidence
        person.association_confidence = self._update_association_confidence(person)
        
        # Layer 3: Deliverability confidence
        person.deliverability_confidence = self._update_deliverability_confidence(emails)
        
        # Overall confidence score (weighted average)
        person.confidence_score = (
            person.existence_confidence * 0.5 +
            person.association_confidence * 0.3 +
            person.deliverability_confidence * 0.2
        )
        
        self.db.commit()

    def _update_association_confidence(self, person: Person) -> float:
        """
        Calculate pattern-based association confidence.
        Returns 0.0 if no valid patterns or insufficient discoveries.
        """
        if not person.company_id:
            return 0.0
        
        company = self.db.query(Company).filter(Company.id == person.company_id).first()
        if not company:
            return 0.0
        
        # Must have at least 1 discovered email to generate patterns
        discovered_count = company.discovered_email_count or 0
        if discovered_count < 1:
            return 0.0
        
        # Use company's pattern confidence if available
        pattern_confidence = company.pattern_confidence or 0.0
        return pattern_confidence

    def _update_deliverability_confidence(self, emails: List[Email]) -> float:
        """
        Calculate deliverability confidence based on SMTP verification + time decay.
        Returns 0.0 if no verified emails exist.
        Ensures last_verified_at is set for all SMTP-verified emails.
        """
        verified_emails = [e for e in emails if e.smtp_verified and e.last_verified_at]
        if not verified_emails:
            return 0.0
        
        # Get most recent verification
        most_recent = max(verified_emails, key=lambda e: e.last_verified_at)
        
        # Time decay: reduce confidence over time
        days_since_verification = (datetime.utcnow() - most_recent.last_verified_at).days
        
        if days_since_verification <= 90:
            return 1.0
        elif days_since_verification <= 180:
            return 0.8
        elif days_since_verification <= 365:
            return 0.6
        else:
            # Cap minimum at 0.5 after 2 years (730 days)
            decay = 1.0 - ((days_since_verification - 365) / 365)
            return max(0.5, decay)

    # ------------------------
    # COMPANY MAPPING
    # ------------------------
    def map_to_company(self, person_id: int, company_id: int) -> bool:
        person = self.db.query(Person).filter(Person.id == person_id).first()
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not person or not company:
            return False
        person.company_id = company.id
        self._update_layered_confidence(person)
        self.db.commit()
        return True

    # ------------------------
    # EMAIL CANDIDATE GENERATION (GATED)
    # ------------------------
    def get_candidates_for_email(self, person_id: int) -> List[str]:
        """
        Generate candidate emails ONLY if:
        1. Company has pattern_confidence >= 0.6
        2. Company has discovered_email_count >= 1
        3. Patterns are from business domains (not Gmail/Yahoo/etc.)
        
        Returns empty list if any gate fails to prevent guessing.
        """
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person or not person.company_id:
            return []

        company = self.db.query(Company).filter(Company.id == person.company_id).first()
        if not company:
            return []

        # GATE 1: Must have at least 1 discovered email
        discovered_count = company.discovered_email_count or 0
        if discovered_count < 1:
            return []

        # GATE 2: Pattern confidence must be >= 0.6
        pattern_confidence = company.pattern_confidence or 0.0
        if pattern_confidence < 0.6:
            return []

        # GATE 3: Filter out personal email domains from patterns
        valid_patterns = []
        if company.email_patterns:
            for p in company.email_patterns:
                pattern_domain = self._extract_domain(p.get('pattern', ''))
                if pattern_domain and pattern_domain not in PERSONAL_EMAIL_DOMAINS:
                    valid_patterns.append(p)

        if not valid_patterns:
            return []

        # Generate candidate emails using valid business patterns
        candidates = self.email_service.generate_candidates(
            first_name=person.first_name,
            last_name=person.last_name,
            domain=company.domain,
            patterns=valid_patterns
        )
        return candidates

    def _extract_domain(self, pattern: str) -> str:
        """Extract domain from email pattern like '{first}.{last}@domain.com'"""
        if '@' in pattern:
            return pattern.split('@')[1].strip().lower()
        return ''

    # ------------------------
    # PATTERN LEARNING (FROM DISCOVERED EMAILS ONLY)
    # ------------------------
    def learn_email_pattern_from_discovery(self, email: Email) -> None:
        """
        Learn email patterns from discovered emails.
        Excludes personal email domains (Gmail, Yahoo, etc.)
        Updates company pattern_confidence and discovered_email_count.
        
        IMPORTANT: Should only be called ONCE per newly discovered email
        to prevent double-counting in discovered_email_count.
        """
        if email.source != 'discovered' or not email.exists:
            return
        
        person = self.db.query(Person).filter(Person.id == email.person_id).first()
        if not person or not person.company_id:
            return
        
        company = self.db.query(Company).filter(Company.id == person.company_id).first()
        if not company:
            return
        
        # Extract domain and check if it's a personal email
        email_address = email.email_address.lower()
        domain = email_address.split('@')[1] if '@' in email_address else ''
        
        # CRITICAL: Ignore personal email domains
        if domain in PERSONAL_EMAIL_DOMAINS:
            return
        
        # Extract pattern from email
        pattern = self._extract_pattern(email_address, person.first_name, person.last_name)
        
        # Update company patterns
        if not company.email_patterns:
            company.email_patterns = []
        
        # Find existing pattern or create new one
        pattern_found = False
        for p in company.email_patterns:
            if p.get('pattern') == pattern:
                p['count'] = p.get('count', 0) + 1
                pattern_found = True
                break
        
        if not pattern_found:
            company.email_patterns.append({
                'pattern': pattern,
                'count': 1
            })
        
        # Update discovered email count
        company.discovered_email_count = (company.discovered_email_count or 0) + 1
        
        # Update pattern confidence based on consistency
        self._update_company_pattern_confidence(company)
        
        self.db.commit()

    def _extract_pattern(self, email: str, first_name: str, last_name: str) -> str:
        """
        Extract pattern from email address.
        Examples:
        - john.doe@company.com -> {first}.{last}@company.com
        - jdoe@company.com -> {first_initial}{last}@company.com
        - john.d@company.com -> {first}.{last_initial}@company.com
        - johndoe@company.com -> {first}{last}@company.com
        
        Returns {unknown}@domain for unrecognized patterns (low confidence).
        """
        local, domain = email.split('@')
        first = first_name.lower()
        last = last_name.lower()
        first_initial = first[0] if first else ''
        last_initial = last[0] if last else ''
        
        # Common patterns (order matters - check most specific first)
        if local == f"{first}.{last}":
            return f"{{first}}.{{last}}@{domain}"
        elif local == f"{first}.{last_initial}":
            return f"{{first}}.{{last_initial}}@{domain}"
        elif local == f"{first_initial}.{last}":
            return f"{{first_initial}}.{{last}}@{domain}"
        elif local == f"{first}{last}":
            return f"{{first}}{{last}}@{domain}"
        elif local == f"{first_initial}{last}":
            return f"{{first_initial}}{{last}}@{domain}"
        elif local == f"{last}.{first}":
            return f"{{last}}.{{first}}@{domain}"
        elif local == f"{last}{first}":
            return f"{{last}}{{first}}@{domain}"
        else:
            # Unrecognized pattern - won't contribute much to confidence
            return f"{{unknown}}@{domain}"

    def _update_company_pattern_confidence(self, company: Company) -> None:
        """
        Calculate pattern confidence based on consistency of discovered patterns.
        Confidence = (most common pattern count) / (total discovered emails)
        
        Higher confidence means more consistent pattern usage.
        Filters out {unknown} patterns from confidence calculation.
        """
        if not company.email_patterns:
            company.pattern_confidence = 0.0
            return
        
        discovered_count = company.discovered_email_count or 0
        if discovered_count < 1:
            company.pattern_confidence = 0.0
            return
        
        # Filter out unknown patterns and find most common valid pattern
        valid_patterns = [p for p in company.email_patterns if '{unknown}' not in p.get('pattern', '')]
        
        if not valid_patterns:
            company.pattern_confidence = 0.0
            return
        
        max_count = max(p.get('count', 0) for p in valid_patterns)
        
        # Calculate confidence (consistency ratio)
        # If multiple patterns have same max count, this still represents consistency
        company.pattern_confidence = min(1.0, max_count / discovered_count)

    # ------------------------
    # ENRICHMENT
    # ------------------------
    def enrich_person(self, person_id: int):
        self.enrichment_service.run_enrichment(person_id)
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if person:
            # Update confidence after enrichment
            self._update_layered_confidence(person)
            self.db.commit()
        return person