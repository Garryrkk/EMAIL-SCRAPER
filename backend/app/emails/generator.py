import logging
from typing import List, Set, Optional, Tuple
from inference.pattern_detector import PatternDetector

logger = logging.getLogger(__name__)


class EmailGenerator:
    """
    Generate email candidates ONLY if:
    1. Pattern has been confirmed from discovered emails
    2. Pattern confidence >= 60%
    
    All generated emails are marked as INFERRED (unverified guesses).
    """

    def __init__(self):
        self.detector = PatternDetector()

    def generate_candidates(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        pattern: Optional[str] = None,
        pattern_confidence: float = 0.0,
    ) -> List[dict]:
        """
        Generate email candidates for a person.
        
        RULES:
        - Only generate if pattern exists and confidence >= 60%
        - All generated emails marked as "inferred"
        - All start with confidence = 0.0 (unverified)
        
        Returns:
            [
                {
                    "email": "john.doe@company.com",
                    "source": "inferred",
                    "pattern_used": "first.last",
                    "pattern_confidence": 0.80,
                    "verification_status": "unverified",
                    "confidence": 0.0
                },
                ...
            ]
        """
        candidates = []

        # RULE 1: Only generate if we have a confirmed pattern
        if not pattern or pattern_confidence < 0.6:
            logger.warning(
                f"Cannot generate candidates: "
                f"pattern={pattern}, confidence={pattern_confidence:.2%}"
            )
            return []

        # RULE 2: Validate pattern can apply to this person
        if not self.detector.validate_pattern_for_person(first_name, last_name, pattern):
            logger.warning(
                f"Pattern {pattern} cannot apply to {first_name} {last_name}"
            )
            return []

        # Generate ONLY using confirmed pattern
        generated_email = self._generate_from_pattern(
            first_name,
            last_name,
            domain,
            pattern,
        )

        if generated_email:
            candidates.append({
                "email": generated_email,
                "source": "inferred",
                "pattern_used": pattern,
                "pattern_confidence": pattern_confidence,
                "verification_status": "unverified",
                "confidence": 0.0,  # UNVERIFIED START
                "reason": f"Generated using confirmed pattern: {pattern}"
            })

        # Also generate common alternatives (but mark lower confidence)
        alternative_patterns = self._get_alternative_patterns(pattern)
        for alt_pattern in alternative_patterns:
            alt_email = self._generate_from_pattern(
                first_name,
                last_name,
                domain,
                alt_pattern,
            )
            if alt_email and alt_email != generated_email:
                candidates.append({
                    "email": alt_email,
                    "source": "inferred",
                    "pattern_used": alt_pattern,
                    "pattern_confidence": pattern_confidence * 0.7,  # Lower confidence for alternatives
                    "verification_status": "unverified",
                    "confidence": 0.0,
                    "reason": f"Generated using alternative pattern: {alt_pattern}"
                })

        logger.info(
            f"Generated {len(candidates)} candidates for "
            f"{first_name} {last_name} @ {domain}"
        )

        return candidates

    def _generate_from_pattern(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        pattern: str,
    ) -> Optional[str]:
        """
        Apply pattern to names.
        Returns email or None if pattern can't apply.
        """
        first = self._normalize_name(first_name)
        last = self._normalize_name(last_name)

        if not first or not last:
            return None

        local = None

        if pattern == "first.last":
            local = f"{first}.{last}"
        elif pattern == "first_last":
            local = f"{first}_{last}"
        elif pattern == "first-last":
            local = f"{first}-{last}"
        elif pattern == "firstlast":
            local = f"{first}{last}"
        elif pattern == "f.last":
            local = f"{first[0]}.{last}"
        elif pattern == "flast":
            local = f"{first[0]}{last}"
        elif pattern == "f_last":
            local = f"{first[0]}_{last}"
        elif pattern == "last.first":
            local = f"{last}.{first}"
        elif pattern == "lastfirst":
            local = f"{last}{first}"
        else:
            return None

        if not local:
            return None

        # Clean up
        local = local.lower().strip()
        local = local.replace("--", "-").replace("__", "_").replace("..", ".")

        return f"{local}@{domain}"

    def _normalize_name(self, name: str) -> str:
        """Normalize name."""
        if not name:
            return ""
        return name.strip().lower().replace(" ", "")

    def _get_alternative_patterns(self, primary_pattern: str) -> List[str]:
        """Get related patterns to also try."""
        alternatives = {
            "first.last": ["f.last", "flast", "first_last"],
            "first_last": ["first.last", "f.last", "firstlast"],
            "f.last": ["first.last", "flast"],
            "flast": ["f.last", "first.last"],
            "firstlast": ["first.last", "first_last"],
            "first-last": ["first.last", "first_last"],
        }

        return alternatives.get(primary_pattern, [])