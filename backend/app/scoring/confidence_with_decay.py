import logging
from typing import Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConfidenceEngineWithDecay:
    """
    Extends confidence scoring with time-based decay.
    
    Apollo principles:
    - Older discoveries lose confidence over time (companies change)
    - Unverified emails decay faster
    - Recently verified emails stay high confidence
    
    Decay rates:
    - Discovered (verified): -5% per 90 days
    - Discovered (unverified): -10% per 30 days
    - Inferred (verified): -5% per 180 days
    - Inferred (unverified): -20% per 7 days
    
    CRITICAL SAFETY RULES:
    1. Decay applies ONLY to deliverability/association scores
    2. Existence facts (discovered emails) NEVER decay from 1.0
    3. This class operates on heuristic scores, not ground truth
    """

    @staticmethod
    def apply_decay(
        base_confidence: float,
        source: str,  # "discovered" or "inferred"
        last_verified_at: datetime = None,
        created_at: datetime = None,
        verification_status: str = "unverified",
    ) -> Dict:
        """
        Apply time-based decay to confidence score.
        
        HARD GUARD: Factual discoveries (1.0) NEVER decay.
        This protects existence integrity.
        
        Returns:
            {
                "base_confidence": float,
                "decay_factor": float (0.0-1.0),
                "final_confidence": float,
                "reason": str,
                "days_old": int
            }
        """
        # 🔒 MANDATORY GUARD: Protect factual existence from decay
        if source == "discovered" and base_confidence == 1.0:
            return {
                "base_confidence": 1.0,
                "decay_factor": 1.0,
                "final_confidence": 1.0,
                "reason": "Factual discovery does not decay",
                "days_old": 0,
                "source": source,
                "verification_status": verification_status,
            }
        
        now = datetime.utcnow()
        reference_date = last_verified_at or created_at or now

        days_old = (now - reference_date).days

        # Determine decay rate based on source and verification
        decay_rate_per_day = 0.0

        if source == "discovered":
            if verification_status == "valid":
                # Verified discovered emails decay slowly
                decay_rate_per_day = 0.05 / 90  # 5% per 90 days
            else:
                # Unverified discovered emails decay faster
                decay_rate_per_day = 0.10 / 30  # 10% per 30 days

        elif source == "inferred":
            if verification_status == "valid":
                # Verified inferred emails decay slowly
                decay_rate_per_day = 0.05 / 180  # 5% per 180 days
            else:
                # Unverified inferred emails decay quickly
                decay_rate_per_day = 0.20 / 7  # 20% per 7 days

        # Calculate decay factor
        total_decay = min(decay_rate_per_day * days_old, 0.5)  # Cap at 50% decay
        decay_factor = 1.0 - total_decay

        # Apply decay
        final_confidence = base_confidence * decay_factor

        # Reason string
        if days_old == 0:
            reason = "Fresh (no decay)"
        elif days_old < 7:
            reason = f"Recent ({days_old} days old)"
        elif days_old < 30:
            reason = f"Recent ({days_old} days old)"
        elif days_old < 90:
            reason = f"Aging ({days_old} days old)"
        else:
            reason = f"Old data ({days_old} days old, consider re-verification)"

        return {
            "base_confidence": base_confidence,
            "decay_factor": decay_factor,
            "final_confidence": final_confidence,
            "reason": reason,
            "days_old": days_old,
            "source": source,
            "verification_status": verification_status,
        }

    @staticmethod
    def should_reverify(
        email_dict: Dict,
        last_verified_at: datetime = None,
    ) -> bool:
        """
        Determine if an email should be re-verified.
        
        Rules:
        - Discovered emails: Re-verify if > 180 days old
        - Inferred emails: Re-verify if > 30 days old
        - Always re-verify if verification_status is not "valid"
        
        CRITICAL: Only reverify based on DELIVERABILITY decay,
        never existence or association confidence.
        """
        now = datetime.utcnow()
        last_verified = last_verified_at or datetime.utcnow()

        days_since_verification = (now - last_verified).days

        source = email_dict.get("source", "unknown")
        verification_status = email_dict.get("verification_status", "unknown")
        
        # 🔒 SAFE: Only check deliverability confidence for decay
        # Never check existence or association
        deliverability = email_dict.get("deliverability_confidence")

        # Always re-verify if not valid
        if verification_status != "valid":
            return True

        # Discovered emails: Re-verify after 180 days
        if source == "discovered" and days_since_verification > 180:
            return True

        # Inferred emails: Re-verify after 30 days
        if source == "inferred" and days_since_verification > 30:
            return True

        # Re-verify if DELIVERABILITY has decayed below 50%
        # (Never reverify based on existence confidence)
        if deliverability is not None and deliverability < 0.50:
            return True

        return False