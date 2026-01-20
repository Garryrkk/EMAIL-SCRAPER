import logging
import re
from typing import Optional, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Learn email patterns ONLY from discovered (real) emails.
    Never guess without proof.
    """

    # Known patterns to check for
    PATTERNS = [
        ("first.last", r"^(?P<first>.*?)\.(?P<last>.+)$"),
        ("first_last", r"^(?P<first>.*?)_(?P<last>.+)$"),
        ("flast", r"^(?P<first>[a-z])(?P<last>.+)$"),
        ("f.last", r"^(?P<first>[a-z])\.(?P<last>.+)$"),
        ("firstlast", r"^(?P<first>[a-z]+)(?P<last>[A-Z][a-z]+)$"),
        ("first-last", r"^(?P<first>.*?)-(?P<last>.+)$"),
        ("lastfirst", r"^(?P<last>[a-z]+)(?P<first>[A-Z][a-z]+)$"),
        ("last.first", r"^(?P<last>.*?)\.(?P<first>.+)$"),
    ]

    def __init__(self):
        self.discovered_emails: List[str] = []
        self.pattern_candidates = []

    def learn_from_discovered(self, emails: List[str]) -> Tuple[Optional[str], float]:
        """
        Learn dominant pattern from DISCOVERED emails only.
        
        Returns:
            (pattern_string, confidence_score)
            
        Example:
            emails = ["john.doe@company.com", "jane.smith@company.com"]
            → ("first.last", 0.95)
        """
        if not emails:
            return None, 0.0

        # Filter to company domain emails only
        self.discovered_emails = [e.split("@")[0].lower() for e in emails]

        if not self.discovered_emails:
            logger.warning("No valid emails to learn pattern from")
            return None, 0.0

        # Try to match each known pattern
        pattern_matches = {}

        for pattern_name, pattern_regex in self.PATTERNS:
            matches = 0
            
            for email_local in self.discovered_emails:
                try:
                    if re.match(pattern_regex, email_local):
                        matches += 1
                except Exception:
                    pass

            if matches > 0:
                pattern_matches[pattern_name] = matches

        if not pattern_matches:
            logger.warning(f"No pattern matched for emails: {self.discovered_emails}")
            return None, 0.0

        # Find dominant pattern
        dominant_pattern = max(pattern_matches, key=pattern_matches.get)
        match_count = pattern_matches[dominant_pattern]
        confidence = min(match_count / len(self.discovered_emails), 1.0)

        # Only accept if confidence >= 60%
        if confidence < 0.6:
            logger.warning(f"Pattern confidence too low: {confidence:.2%}")
            return None, 0.0

        logger.info(
            f"Pattern learned: {dominant_pattern} "
            f"({match_count}/{len(self.discovered_emails)} emails) "
            f"confidence: {confidence:.2%}"
        )

        return dominant_pattern, confidence

    @staticmethod
    def extract_names_from_email(email_local: str, pattern: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first/last name from email using pattern.
        
        Example:
            email_local = "john.doe"
            pattern = "first.last"
            → ("john", "doe")
        """
        for pattern_name, pattern_regex in PatternDetector.PATTERNS:
            if pattern_name == pattern:
                try:
                    match = re.match(pattern_regex, email_local)
                    if match:
                        groups = match.groupdict()
                        first = groups.get("first", "").strip()
                        last = groups.get("last", "").strip()
                        return first if first else None, last if last else None
                except Exception:
                    pass

        return None, None

    @staticmethod
    def validate_pattern_for_person(
        first_name: str,
        last_name: str,
        pattern: str,
    ) -> bool:
        """
        Validate if pattern can be applied to person.
        
        Don't generate if pattern can't apply.
        Example:
            pattern "first.last" requires both first AND last name
        """
        if not pattern:
            return False

        if pattern in ["first.last", "first_last", "first-last"]:
            return bool(first_name and last_name)
        elif pattern in ["f.last", "flast", "f_last"]:
            return bool(first_name and last_name)
        elif pattern in ["firstlast", "first-last"]:
            return bool(first_name and last_name)
        else:
            return bool(first_name and last_name)