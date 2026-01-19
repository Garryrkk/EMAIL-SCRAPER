import logging
from typing import Optional

from app.core.constants import EmailStatus

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Score email confidence."""

    def score_email(
        self,
        syntax_valid: bool = False,
        smtp_valid: bool = False,
        pattern_confidence: float = 0.0,
        domain_bounce_rate: float = 0.0,
        is_catch_all: bool = False,
        is_role_based: bool = False,
        discovery_source: str = "inferred",
    ) -> tuple[float, str]:
        """Calculate overall confidence score."""
        score = 0.0
        factors = []

        # SMTP verification (strongest signal)
        if smtp_valid:
            score += 0.5
            factors.append("SMTP valid")
        elif syntax_valid:
            score += 0.2
            factors.append("Syntax valid")

        # Pattern confidence
        if pattern_confidence > 0:
            score += min(pattern_confidence * 0.3, 0.3)
            factors.append(f"Pattern confidence: {pattern_confidence:.2f}")

        # Domain bounce rate (lower is better)
        bounce_penalty = domain_bounce_rate * 0.2
        score = max(0, score - bounce_penalty)
        if bounce_penalty > 0:
            factors.append(f"Bounce penalty: {bounce_penalty:.2f}")

        # Catch-all detection (risky)
        if is_catch_all:
            score *= 0.6
            factors.append("Catch-all domain")

        # Role-based emails (lower confidence)
        if is_role_based:
            score *= 0.7
            factors.append("Role-based email")

        # Discovery source
        if discovery_source == "discovered":
            score = min(score + 0.15, 1.0)
            factors.append("Discovered in public data")

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))

        # Determine status
        if score >= 0.8:
            status = EmailStatus.VALID
        elif score >= 0.5:
            status = EmailStatus.ACCEPT_ALL
        elif score >= 0.3:
            status = EmailStatus.UNKNOWN
        else:
            status = EmailStatus.RISKY

        logger.debug(f"Confidence score: {score:.3f} - {', '.join(factors)}")

        return score, status

    def score_company_confidence(
        self,
        public_emails_found: int = 0,
        pattern_detected: bool = False,
        pattern_consistency: float = 0.0,
        last_verified_days_ago: int = 999,
    ) -> float:
        """Score company confidence."""
        score = 0.0

        # Public emails found
        if public_emails_found >= 10:
            score += 0.4
        elif public_emails_found >= 5:
            score += 0.3
        elif public_emails_found >= 2:
            score += 0.2

        # Pattern detected
        if pattern_detected:
            score += 0.3
            score += min(pattern_consistency * 0.3, 0.3)

        # Recency bonus
        if last_verified_days_ago < 7:
            score += 0.1
        elif last_verified_days_ago < 30:
            score += 0.05

        return min(score, 1.0)