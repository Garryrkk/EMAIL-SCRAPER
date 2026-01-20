import logging
import re
from typing import Optional, List, Tuple, Dict
from collections import Counter

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Learn email patterns ONLY from discovered (real) emails.
    Never guess without proof.
    """

    # Known patterns to check for - STRICT human-safe versions only
    PATTERNS = [
        ("first.last", r"^(?P<first>[a-z]{2,})\.(?P<last>[a-z]{2,})$"),
        ("first_last", r"^(?P<first>[a-z]{2,})_(?P<last>[a-z]{2,})$"),
        ("first-last", r"^(?P<first>[a-z]{2,})-(?P<last>[a-z]{2,})$"),
        ("flast", r"^(?P<first>[a-z])(?P<last>[a-z]{2,})$"),
        ("f.last", r"^(?P<first>[a-z])\.(?P<last>[a-z]{2,})$"),
    ]

    def __init__(self):
        self.discovered_emails: List[str] = []
        self.pattern_candidates = []

    def _is_personal_email(self, email: str) -> bool:
        """Check if email is from personal domain."""
        try:
            domain = email.split("@")[1].lower()
            return domain in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "live.com", "me.com"}
        except (IndexError, AttributeError):
            return False

    def learn_from_discovered(self, emails: List[Dict]) -> Tuple[Optional[str], float]:
        """
        Learn dominant pattern from DISCOVERED emails only.
        
        Args:
            emails: List of email dicts with format:
                    {"email": "john.doe@company.com", "is_role_based": False}
        
        Returns:
            (pattern_string, confidence_score)
            
        Example:
            emails = [
                {"email": "john.doe@company.com", "is_role_based": False},
                {"email": "jane.smith@company.com", "is_role_based": False}
            ]
            → ("first.last", 0.66)
        """
        if not emails:
            return None, 0.0

        # BLOCKER FIX #1: Filter out role-based and personal emails
        valid_for_pattern = [
            e["email"].split("@")[0].lower()
            for e in emails
            if not e.get("is_role_based", False)
            and not self._is_personal_email(e["email"])
        ]

        if len(valid_for_pattern) < 1:
            logger.warning("No eligible emails for pattern learning (all filtered as role-based or personal)")
            return None, 0.0

        # EDGE CASE FIX #2: Require minimum company maturity
        # Single-person companies don't establish patterns reliably
        if len(valid_for_pattern) < 2:
            logger.warning(
                f"Insufficient sample size for pattern learning: {len(valid_for_pattern)} email(s). "
                f"Minimum 2 required for reliable pattern detection."
            )
            return None, 0.0

        self.discovered_emails = valid_for_pattern

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

        # EDGE CASE FIX #1: Require pattern dominance, not just plurality
        # Apollo requires clear winner, not arbitrary tie-breaking
        total_matches = sum(pattern_matches.values())
        dominant_pattern = max(pattern_matches, key=pattern_matches.get)
        dominant_count = pattern_matches[dominant_pattern]
        dominance_ratio = dominant_count / total_matches

        if dominance_ratio < 0.7:
            logger.warning(
                f"Pattern split too evenly (dominance: {dominance_ratio:.1%}). "
                f"Refusing to learn without clear dominant pattern. "
                f"Matches: {pattern_matches}"
            )
            return None, 0.0

        # SOFT ISSUE FIX #1: Apollo-style confidence damping
        # Never trust single examples fully
        sample_penalty = min(len(self.discovered_emails) / 3.0, 1.0)
        raw_confidence = dominant_count / len(self.discovered_emails)
        confidence = raw_confidence * sample_penalty

        # Only accept if confidence >= 60%
        if confidence < 0.6:
            logger.warning(
                f"Pattern confidence too low: {confidence:.2%} "
                f"(raw: {raw_confidence:.2%}, sample_penalty: {sample_penalty:.2%}, "
                f"dominance: {dominance_ratio:.2%})"
            )
            return None, 0.0

        logger.info(
            f"Pattern learned: {dominant_pattern} "
            f"({dominant_count}/{len(self.discovered_emails)} emails) "
            f"confidence: {confidence:.2%} (raw: {raw_confidence:.2%}) "
            f"dominance: {dominance_ratio:.2%}"
        )

        return dominant_pattern, confidence

    @staticmethod
    def extract_names_from_email(
        email_local: str, 
        pattern: str,
        pattern_confidence: float = 0.0
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first/last name from email using pattern.
        
        SOFT ISSUE FIX #2: Only extract if pattern confidence >= 80%
        
        Example:
            email_local = "john.doe"
            pattern = "first.last"
            pattern_confidence = 0.85
            → ("john", "doe")
        """
        # Guard: Don't infer names unless pattern is highly trusted
        if pattern_confidence < 0.8:
            return None, None
            
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

    @staticmethod
    def get_confidence_label(confidence: float) -> str:
        """
        Get UI-friendly confidence label.
        
        Returns:
            "High" (≥80%), "Medium" (60-79%), "Low" (<60%)
        """
        if confidence >= 0.8:
            return "High"
        elif confidence >= 0.6:
            return "Medium"
        else:
            return "Low"