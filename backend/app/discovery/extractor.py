import logging
import re
from bs4 import BeautifulSoup
from typing import Set, Dict, List

logger = logging.getLogger(__name__)

# Email pattern - standard format
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Obfuscated email patterns (e.g., "john [at] company [dot] com")
OBFUSCATED_EMAIL_PATTERN = re.compile(
    r'\b([A-Za-z0-9._%+-]+)\s*[\[\(]?\s*(?:at|@)\s*[\]\)]?\s*([A-Za-z0-9.-]+)\s*[\[\(]?\s*(?:dot|\.)\s*[\]\)]?\s*([A-Z|a-z]{2,})\b',
    re.IGNORECASE
)

# Name patterns
NAME_PATTERNS = [
    r'(?:CEO|Founder|President|CTO|CFO|COO|Director|VP|Vice President):\s*([A-Z][a-z]+ [A-Z][a-z]+)',
    r'By\s+([A-Z][a-z]+ [A-Z][a-z]+)',
    r'Written by\s+([A-Z][a-z]+ [A-Z][a-z]+)',
    r'Author:\s*([A-Z][a-z]+ [A-Z][a-z]+)',
]


class EmailExtractor:
    """Extract emails and names from HTML content."""

    def __init__(self):
        self.emails = set()
        self.role_based_emails = set()
        self.names = set()

    def extract_from_html(self, html: str, domain: str) -> Dict:
        """Extract emails and names from HTML."""
        self.emails.clear()
        self.role_based_emails.clear()
        self.names.clear()

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for script in soup(['script', 'style']):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Extract emails (both standard and obfuscated)
            self._extract_emails(text, domain)
            self._extract_obfuscated_emails(text, domain)

            # Extract names
            self._extract_names(text)

            # Extract from structured data
            self._extract_from_schema(soup, domain)

            # Return structured output for scoring
            return {
                "emails": [
                    {
                        "email": e,
                        "source": "discovered",
                        "role_based": e in self.role_based_emails
                    }
                    for e in self.emails
                ],
                "names": list(self.names),
            }

        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
            return {"emails": [], "names": []}

    def _extract_emails(self, text: str, domain: str):
        """Extract standard email addresses."""
        matches = EMAIL_PATTERN.findall(text)
        for match in matches:
            # Normalize email: remove mailto:, strip whitespace, lowercase
            email = match.lower().strip().replace("mailto:", "")
            
            # Filter out generic domains and non-work emails
            if not self._is_valid_work_email(email, domain):
                continue
            
            self.emails.add(email)

    def _extract_obfuscated_emails(self, text: str, domain: str):
        """Extract obfuscated email addresses (e.g., john [at] company [dot] com)."""
        matches = OBFUSCATED_EMAIL_PATTERN.findall(text)
        for match in matches:
            if len(match) == 3:
                local, domain_part, tld = match
                # Reconstruct email
                email = f"{local.strip()}@{domain_part.strip()}.{tld.strip()}".lower()
                
                if self._is_valid_work_email(email, domain):
                    self.emails.add(email)

    def _is_valid_work_email(self, email: str, domain: str) -> bool:
        """Check if email is valid work email."""
        from core.constants import GENERIC_DOMAINS, ROLE_BASED_PATTERNS

        try:
            local, email_domain = email.split("@")
        except ValueError:
            # Malformed email
            return False

        # Must be company domain or subdomain (e.g., team.domain.com, mail.domain.com)
        if not email_domain.endswith(domain):
            return False

        # Not a generic domain (Gmail, Yahoo, Hotmail, Outlook, ProtonMail, etc.)
        if email_domain in GENERIC_DOMAINS:
            return False

        # Check role patterns and flag them separately
        # Role-based emails should NEVER be used for person-pattern learning
        for pattern in ROLE_BASED_PATTERNS:
            pattern_clean = pattern.replace("@", "").lower()
            if local.lower().startswith(pattern_clean) or local.lower() == pattern_clean:
                self.role_based_emails.add(email)
                return True  # Still valid, just flagged as role-based

        return True

    def _extract_names(self, text: str):
        """Extract person names."""
        for pattern in NAME_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    name = " ".join(match)
                else:
                    name = match
                if self._is_valid_name(name):
                    self.names.add(name)

    def _is_valid_name(self, name: str) -> bool:
        """Validate name."""
        parts = name.split()
        if len(parts) < 2:
            return False
        if any(len(part) < 2 for part in parts):
            return False
        # Avoid common false positives
        if any(part.lower() in ['the', 'and', 'or', 'of', 'in', 'at'] for part in parts):
            return False
        return True

    def _extract_from_schema(self, soup: BeautifulSoup, domain: str):
        """Extract from schema.org structured data."""
        import json

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    self._parse_schema(data, domain)
            except json.JSONDecodeError as e:
                logger.debug(f"Error parsing schema JSON: {e}")
            except Exception as e:
                logger.debug(f"Error parsing schema: {e}")

    def _parse_schema(self, data: dict, domain: str, depth=0):
        """Recursively parse schema data."""
        if depth > 5:
            return

        if isinstance(data, dict):
            # Check for email
            if "email" in data:
                email = data["email"]
                if isinstance(email, str):
                    # Normalize email
                    email = email.lower().strip().replace("mailto:", "")
                    
                    if self._is_valid_work_email(email, domain):
                        self.emails.add(email)

            # Check for name
            if "name" in data:
                name = data["name"]
                if isinstance(name, str) and self._is_valid_name(name):
                    self.names.add(name)

            # Recurse
            for value in data.values():
                self._parse_schema(value, domain, depth + 1)

        elif isinstance(data, list):
            for item in data:
                self._parse_schema(item, domain, depth + 1)