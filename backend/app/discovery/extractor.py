import logging
import re
from bs4 import BeautifulSoup
from typing import Set, Dict, List

logger = logging.getLogger(__name__)

# Email pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Name patterns
NAME_PATTERNS = [
    r'(?:CEO|Founder|President):\s*([A-Z][a-z]+ [A-Z][a-z]+)',
    r'By\s+([A-Z][a-z]+ [A-Z][a-z]+)',
]


class EmailExtractor:
    """Extract emails and names from HTML content."""

    def __init__(self):
        self.emails = set()
        self.names = set()

    def extract_from_html(self, html: str, domain: str) -> Dict:
        """Extract emails and names from HTML."""
        self.emails.clear()
        self.names.clear()

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for script in soup(['script', 'style']):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Extract emails
            self._extract_emails(text, domain)

            # Extract names
            self._extract_names(text)

            # Extract from structured data
            self._extract_from_schema(soup, domain)

            return {
                "emails": list(self.emails),
                "names": list(self.names),
            }

        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
            return {"emails": [], "names": []}

    def _extract_emails(self, text: str, domain: str):
        """Extract email addresses."""
        matches = EMAIL_PATTERN.findall(text)
        for match in matches:
            # Filter out generic domains and non-work emails
            if not self._is_valid_work_email(match, domain):
                continue
            self.emails.add(match.lower())

    def _is_valid_work_email(self, email: str, domain: str) -> bool:
        """Check if email is valid work email."""
        from core.constants import GENERIC_DOMAINS, ROLE_BASED_PATTERNS

        email_domain = email.split("@")[1]

        # Must be company domain or business domain
        if email_domain != domain and email_domain not in [
            f"mail.{domain}",
            f"info.{domain}",
        ]:
            return False

        # Not a generic domain
        if email_domain in GENERIC_DOMAINS:
            return False

        # Check role patterns (but keep them for later analysis)
        local = email.split("@")[0]
        for pattern in ROLE_BASED_PATTERNS:
            if local.startswith(pattern.replace("@", "")):
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
        return True

    def _extract_from_schema(self, soup: BeautifulSoup, domain: str):
        """Extract from schema.org structured data."""
        import json

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                self._parse_schema(data, domain)
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
                if self._is_valid_work_email(email, domain):
                    self.emails.add(email.lower())

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