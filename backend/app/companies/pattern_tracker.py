import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from companies.service import CompanyService

logger = logging.getLogger(__name__)


class PatternTracker:
    """
    Tracks pattern performance over time.
    
    Apollo learns from:
    - Successful verifications
    - User actions (opens, clicks, replies)
    - Over time, pattern confidence evolves
    
    We track:
    - Total attempts with pattern
    - Successful verifications
    - Success rate
    - Last updated
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.company_service = CompanyService(db)

    async def record_pattern_test(
        self,
        company_id: str,
        email: str,
        verification_status: str,
        success: bool,
    ):
        """
        Record a pattern test result.
        
        Args:
            company_id: Company being tested
            email: Email that was tested
            verification_status: valid/invalid/catch_all/unknown
            success: Did the email verify successfully?
        """
        company = await self.company_service.get_company_by_id(company_id)
        
        if not company:
            return

        # Update metadata
        if company.metadata is None:
            company.metadata = {}

        # Initialize tracking if needed
        if "pattern_attempts" not in company.metadata:
            company.metadata["pattern_attempts"] = 0
            company.metadata["pattern_successes"] = 0
            company.metadata["pattern_verifications"] = 0

        # Record this test
        company.metadata["pattern_attempts"] += 1
        company.metadata["pattern_last_tested"] = datetime.utcnow().isoformat()

        # Record success
        if success or verification_status == "valid":
            company.metadata["pattern_successes"] += 1
            company.metadata["pattern_verifications"] += 1

        # Calculate success rate
        attempts = company.metadata["pattern_attempts"]
        successes = company.metadata["pattern_successes"]
        success_rate = successes / attempts if attempts > 0 else 0

        # Update pattern confidence based on performance
        old_confidence = company.pattern_confidence
        new_confidence = await self._recalculate_pattern_confidence(
            company.pattern_confidence,
            success_rate,
            company.metadata.get("pattern_verifications", 0),
        )

        company.pattern_confidence = new_confidence

        logger.info(
            f"Pattern tracking for {company.domain}: "
            f"{successes}/{attempts} successful "
            f"(confidence: {old_confidence:.0%} → {new_confidence:.0%})"
        )

        await self.db.flush()

    async def _recalculate_pattern_confidence(
        self,
        initial_confidence: float,
        success_rate: float,
        verification_count: int,
    ) -> float:
        """
        Recalculate pattern confidence based on verification results.
        
        Logic:
        - If success rate >= 80% and verified >= 3 times → increase confidence
        - If success rate < 60% → decrease confidence
        - Otherwise → keep or slightly adjust
        - Cap at 95% (never 100%)
        """
        if verification_count < 2:
            # Not enough data to adjust yet
            return initial_confidence

        # Boost confidence if pattern is working well
        if success_rate >= 0.80 and verification_count >= 3:
            new_confidence = min(initial_confidence + 0.05, 0.95)
            logger.info(f"Pattern confidence boosted by verification results")
            return new_confidence

        # Reduce confidence if pattern is failing
        elif success_rate < 0.60:
            new_confidence = max(initial_confidence - 0.10, 0.5)
            logger.warning(f"Pattern confidence reduced due to low success rate")
            return new_confidence

        # Keep confidence if mixed results
        else:
            return initial_confidence

    async def get_pattern_stats(self, company_id: str) -> dict:
        """Get pattern performance statistics."""
        company = await self.company_service.get_company_by_id(company_id)
        
        if not company or not company.metadata:
            return {
                "pattern": company.detected_pattern,
                "confidence": company.pattern_confidence,
                "attempts": 0,
                "successes": 0,
                "success_rate": 0.0,
            }

        attempts = company.metadata.get("pattern_attempts", 0)
        successes = company.metadata.get("pattern_successes", 0)
        verifications = company.metadata.get("pattern_verifications", 0)
        success_rate = successes / attempts if attempts > 0 else 0

        return {
            "pattern": company.detected_pattern,
            "confidence": company.pattern_confidence,
            "attempts": attempts,
            "successes": successes,
            "verifications": verifications,
            "success_rate": success_rate,
            "last_tested": company.metadata.get("pattern_last_tested"),
        }