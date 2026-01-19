import logging
from typing import Set
import itertools

logger = logging.getLogger(__name__)


class EmailGenerator:
    """Generate email permutations based on patterns."""

    def __init__(self):
        self.patterns = [
            "firstname.lastname",
            "firstname",
            "f.lastname",
            "flastname",
            "firstname_lastname",
            "fn",
            "firstnameln",
            "firstname-lastname",
            "last.first",
            "lastnamefirst",
        ]

    def generate_from_person(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        detected_pattern: str = None,
    ) -> Set[str]:
        """Generate email permutations."""
        emails = set()

        # Normalize names
        first = self._normalize_name(first_name)
        last = self._normalize_name(last_name)

        # If pattern detected, prioritize that
        if detected_pattern:
            email = self._generate_from_pattern(
                first,
                last,
                domain,
                detected_pattern,
            )
            if email:
                emails.add(email)

        # Generate alternatives
        for pattern in self.patterns:
            email = self._generate_from_pattern(first, last, domain, pattern)
            if email and email not in emails:
                emails.add(email)

        return emails

    def _normalize_name(self, name: str) -> str:
        """Normalize name."""
        if not name:
            return ""
        return name.strip().lower()

    def _generate_from_pattern(
        self,
        first: str,
        last: str,
        domain: str,
        pattern: str,
    ) -> str:
        """Generate single email from pattern."""
        try:
            replacements = {
                "firstname": first,
                "lastname": last,
                "f": first[0] if first else "",
                "l": last[0] if last else "",
                "fn": (first[0] if first else "") + (last if last else ""),
                "fl": (first[0] if first else "") + (last[0] if last else ""),
                "ln": (last if last else "") + (first[0] if first else ""),
                "ln": (last if last else "") + (first if first else ""),
            }

            local = pattern
            for key, value in replacements.items():
                local = local.replace(key, value)

            # Clean up
            local = local.replace("--", "-").replace("__", "_")
            local = local.strip("-_.")

            if not local or not first or not last:
                return None

            return f"{local}@{domain}"

        except Exception as e:
            logger.error(f"Error generating email: {e}")
            return None

    def generate_from_company_pattern(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        pattern: str,
        confidence: float,
    ) -> str:
        """Generate email using company pattern."""
        if confidence < 0.5:
            return None

        return self._generate_from_pattern(
            self._normalize_name(first_name),
            self._normalize_name(last_name),
            domain,
            pattern,
        )

    def detect_pattern(
        self,
        emails: list,
        domain: str,
    ) -> tuple[str, float]:
        """Detect dominant email pattern."""
        if not emails:
            return None, 0.0

        # Filter to company domain emails only
        company_emails = [
            e for e in emails
            if e.split("@")[1] == domain
        ]

        if not company_emails:
            return None, 0.0

        patterns_found = {}

        # Analyze each email
        for email in company_emails:
            local = email.split("@")[0].lower()
            pattern = self._reverse_engineer_pattern(local)
            patterns_found[pattern] = patterns_found.get(pattern, 0) + 1

        if not patterns_found:
            return None, 0.0

        # Get most common pattern
        dominant_pattern = max(patterns_found, key=patterns_found.get)
        confidence = patterns_found[dominant_pattern] / len(company_emails)

        return dominant_pattern, confidence

    def _reverse_engineer_pattern(self, local: str) -> str:
        """Reverse engineer pattern from email local part."""
        # This is a simplified version
        # In production, you'd use ML/heuristics
        
        if "." in local:
            return "firstname.lastname"
        elif "_" in local:
            return "firstname_lastname"
        elif "-" in local:
            return "firstname-lastname"
        elif len(local) > 10:
            return "firstname.lastname"
        else:
            return "unknown"