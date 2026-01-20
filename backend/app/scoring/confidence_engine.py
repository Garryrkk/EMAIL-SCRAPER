import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """
    Calculate confidence score based on:
    1. Source (discovered vs inferred)
    2. Verification status
    3. Pattern confidence
    4. Occurrences
    
    CRITICAL SAFETY RULE:
    These scores are ranking aids, UI ordering, and heuristics.
    They are NEVER:
    - existence confidence (handled separately in confidence_layered.py)
    - factual truth claims
    - to be persisted as ground truth
    
    Existence is binary and managed outside this engine.
    """

    @staticmethod
    def score_discovered_email(
        email: str,
        occurrences: int,
        source: str,
        verification_status: str = "unverified",
        verification_confidence: float = 0.0,
    ) -> Dict:
        """
        Score a DISCOVERED email (found on website).
        
        Base: 60% (found on public website = real)
        + 10% per occurrence (up to 30%)
        + Verification boost
        """
        base_score = 0.60  # Found on website

        # Occurrence boost
        occurrence_boost = min(occurrences - 1, 3) * 0.10  # Up to +30%
        
        # Source boost
        source_boost = {
            "mailto_link": 0.10,      # Explicit link = high trust
            "footer_text": 0.08,      # Footer = important
            "contact_page": 0.07,     # Contact pages matter
            "schema_org": 0.05,       # Structured data
        }.get(source, 0.05)

        # Verification boost
        verification_boost = 0.0
        if verification_status == "valid":
            verification_boost = 0.15  # SMTP confirmed
        elif verification_status == "catch_all":
            verification_boost = -0.20  # Catch-all risky
        elif verification_status == "invalid":
            verification_boost = -0.30  # Hard invalid

        score = min(
            1.0,
            base_score + occurrence_boost + source_boost + verification_boost
        )

        return {
            "email": email,
            "source": "discovered",
            "confidence": score,
            "breakdown": {
                "base": base_score,
                "occurrences": occurrence_boost,
                "source_signal": source_boost,
                "verification": verification_boost,
            },
            "label": "Found on company website",
            "trust_level": _get_trust_level(score),
        }

    @staticmethod
    def score_inferred_email(
        email: str,
        pattern_confidence: float,
        verification_status: str = "unverified",
        verification_confidence: float = 0.0,
    ) -> Dict:
        """
        Score an INFERRED email (guessed from pattern).
        
        Base: 0% (unverified guess)
        + Pattern confidence (20-30%)
        + Verification boost (if verified)
        
        Max without verification: 35%
        Can reach 85%+ only if SMTP verified
        """
        # Inferred emails start at 0
        base_score = 0.0

        # Pattern boost (only if pattern was strong)
        pattern_boost = pattern_confidence * 0.30  # Up to 30%

        # Verification boost
        verification_boost = 0.0
        if verification_status == "valid":
            verification_boost = 0.55  # Can reach 85% total if pattern was good
        elif verification_status == "catch_all":
            verification_boost = 0.10  # Catch-all inferred = risky
        elif verification_status == "invalid":
            verification_boost = -0.15  # Bad pattern + failed verification

        score = max(
            0.0,
            min(1.0, base_score + pattern_boost + verification_boost)
        )

        return {
            "email": email,
            "source": "inferred",
            "confidence": score,
            "breakdown": {
                "base": base_score,
                "pattern": pattern_boost,
                "verification": verification_boost,
            },
            "label": "Guessed using company pattern" if verification_status == "unverified" 
                     else f"Guessed + {verification_status}",
            "trust_level": _get_trust_level(score),
            "show_by_default": score >= 0.75,  # Only show unverified if high confidence
        }

    @staticmethod
    def should_display(
        email_dict: Dict,
        include_unverified: bool = False,
    ) -> bool:
        """
        Determine if email should be shown to user.
        
        RULES:
        - Discovered emails: Always show if confidence >= 50%
        - Inferred unverified: Only show if include_unverified=True
        - Inferred verified: Show if confidence >= 75%
        """
        confidence = email_dict["confidence"]
        source = email_dict["source"]
        label = email_dict.get("label", "")

        # Always show discovered with decent confidence
        if source == "discovered" and confidence >= 0.50:
            return True

        # Inferred unverified
        if "unverified" in label or "Guessed using" in label:
            return include_unverified or confidence >= 0.85

        # Inferred verified
        if confidence >= 0.75:
            return True

        return False


def _get_trust_level(score: float) -> str:
    """Map score to trust level."""
    if score >= 0.90:
        return "very_high"
    elif score >= 0.75:
        return "high"
    elif score >= 0.50:
        return "medium"
    elif score >= 0.25:
        return "low"
    else:
        return "very_low"