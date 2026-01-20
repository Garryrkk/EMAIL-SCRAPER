import logging
from typing import List, Dict, Optional
from app.verification.aggregator import VerificationAggregator

logger = logging.getLogger(__name__)


class FallbackInferenceEngine:
    """
    When NO emails are discovered on website, fall back to verification-led inference.
    
    Strategy:
    - Generate common patterns WITHOUT pattern confidence requirement
    - Test each via SMTP
    - Only keep verified results
    - Cap confidence at lower level (70% max)
    
    This is what Apollo does: "If we can't find public proof, 
    we generate candidates and verify them."
    """

    # Common patterns to try when discovery fails
    FALLBACK_PATTERNS = [
        "first.last",
        "first_last",
        "f.last",
        "flast",
        "first-last",
        "firstlast",
    ]

    def __init__(self, domain: str):
        self.domain = domain
        self.verifier = VerificationAggregator()

    async def fallback_infer(
        self,
        first_name: str,
        last_name: str,
    ) -> List[Dict]:
        """
        Fallback inference when no public emails found.
        
        Rules:
        - Generate common patterns
        - Verify each BEFORE returning
        - Only return VERIFIED emails
        - Cap confidence at 70%
        - Label as "Verification-inferred"
        
        Returns:
            [
                {
                    "email": "john.doe@domain.com",
                    "source": "verification_inferred",
                    "confidence": 0.65,
                    "verification_status": "valid",
                    "label": "Generated and verified (no public email found)",
                    "note": "Found via pattern testing, not public discovery"
                }
            ]
        """
        logger.info(
            f"Fallback: No public emails found for {self.domain}. "
            f"Attempting verification-led inference for {first_name} {last_name}"
        )

        candidates = []

        # Try each fallback pattern
        for pattern in self.FALLBACK_PATTERNS:
            email = self._generate_from_pattern(first_name, last_name, pattern)

            if not email:
                continue

            # CRITICAL: Only include if SMTP verification succeeds
            logger.debug(f"Testing fallback candidate: {email}")
            result = await self.verifier.verify(email)

            # Only accept if verification succeeded
            if result.verification_status == "valid":
                candidates.append({
                    "email": email,
                    "source": "verification_inferred",  # Key difference
                    "pattern_used": pattern,
                    "confidence": 0.65,  # Capped at 65% (lower than discovered)
                    "verification_status": "valid",
                    "label": "Generated and verified (no public emails found)",
                    "note": "Pattern inferred and SMTP verified",
                    "show_by_default": True,  # Show because verified
                })
                logger.info(f"Fallback match: {email} verified")
            else:
                logger.debug(f"Fallback failed verification: {email} ({result.verification_status})")

        if not candidates:
            logger.warning(f"Fallback inference found no verified emails for {self.domain}")

        return candidates

    def _generate_from_pattern(
        self,
        first_name: str,
        last_name: str,
        pattern: str,
    ) -> Optional[str]:
        """Generate email from pattern."""
        first = first_name.strip().lower().replace(" ", "")
        last = last_name.strip().lower().replace(" ", "")

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
        else:
            return None

        if not local:
            return None

        return f"{local}@{self.domain}"