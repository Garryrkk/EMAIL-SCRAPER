import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LayeredConfidenceEngine:
    """
    Three separate confidence layers (Apollo/Hunter model).
    
    This is the critical fix:
    - Layer 1: Email EXISTENCE (factual, not probabilistic)
    - Layer 2: PERSON-EMAIL association (probabilistic)
    - Layer 3: DELIVERABILITY (time-aware, MX-aware)
    
    These MUST be treated separately.
    """

    @staticmethod
    def score_email_existence(
        email: str,
        source: str,  # "discovered", "inferred", "verification_inferred"
        verification_status: str = "unverified",
    ) -> Dict:
        """
        LAYER 1: Does this email EXIST for this company?
        
        This is FACTUAL, not probabilistic.
        
        Rules:
        - Discovered on website: 100% (FACT)
        - Verified via SMTP: 100% (FACT)
        - Inferred/guessed: NOT applicable here
        
        Returns:
            {
                "exists": bool,
                "existence_confidence": 1.0 | 0.0,
                "reason": str
            }
        """
        
        # CRITICAL: Discovered emails are ALWAYS facts
        if source == "discovered":
            return {
                "exists": True,
                "existence_confidence": 1.0,
                "reason": "Found on company website (factual)",
                "is_factual": True,
            }
        
        # Verification-led inference (fallback)
        if source == "verification_inferred":
            if verification_status == "valid":
                return {
                    "exists": True,
                    "existence_confidence": 1.0,
                    "reason": "Generated and SMTP verified (factual)",
                    "is_factual": True,
                }
        
        # Pure inferred (guessed, NOT factual)
        return {
            "exists": False,  # Or uncertain
            "existence_confidence": 0.0,
            "reason": "Inferred pattern (not verified as existing)",
            "is_factual": False,
        }

    @staticmethod
    def score_person_association(
        person_first: str,
        person_last: str,
        email: str,
        pattern_used: Optional[str] = None,
        pattern_confidence: float = 0.0,
        verification_status: str = "unverified",
    ) -> Dict:
        """
        LAYER 2: Does this email belong to THIS PERSON?
        
        This is PROBABILISTIC.
        Used when user asks "Find John Doe's email"
        
        Factors:
        - Pattern reliability
        - Verification success
        - Name matching
        
        Returns:
            {
                "person_match_confidence": 0.0-1.0,
                "reason": str
            }
        """
        
        # Base: Does pattern exist?
        if not pattern_used or pattern_confidence < 0.6:
            return {
                "person_match_confidence": 0.0,
                "reason": "No confirmed pattern for this company",
            }
        
        # Pattern exists: Apply pattern confidence
        base_confidence = pattern_confidence * 0.4  # Max 40% from pattern alone
        
        # Verification boost
        verification_boost = 0.0
        if verification_status == "valid":
            verification_boost = 0.55  # SMTP confirmation adds 55%
        elif verification_status == "catch_all":
            verification_boost = 0.10  # Some boost but risky
        
        total_confidence = base_confidence + verification_boost
        
        return {
            "person_match_confidence": min(total_confidence, 1.0),
            "pattern_confidence_used": pattern_confidence,
            "verification_boost": verification_boost,
            "reason": f"Pattern ({pattern_confidence:.0%}) + Verification ({verification_boost:.0%})",
        }

    @staticmethod
    def score_deliverability(
        email: str,
        verification_status: str,
        last_verified_at: Optional[datetime] = None,
        mx_valid: bool = False,
        catch_all: bool = False,
    ) -> Dict:
        """
        LAYER 3: Will this email reach inbox TODAY?
        
        This is where decay, MX, catch-all apply.
        
        Rules:
        - MX invalid: Cannot deliver
        - Catch-all: Can deliver but risky
        - Old verification: Might be stale
        - SMTP reject: Cannot deliver
        
        Returns:
            {
                "deliverable": bool,
                "deliverability_confidence": 0.0-1.0,
                "reason": str
            }
        """
        
        # No MX = not deliverable
        if not mx_valid:
            return {
                "deliverable": False,
                "deliverability_confidence": 0.0,
                "reason": "No valid MX records for domain",
            }
        
        # SMTP rejected = not deliverable
        if verification_status == "invalid":
            return {
                "deliverable": False,
                "deliverability_confidence": 0.0,
                "reason": "SMTP verification failed",
            }
        
        # SMTP accepted = deliverable
        if verification_status == "valid":
            confidence = 0.95
            reason = "SMTP verified"
            
            # Age decay (slow)
            if last_verified_at:
                days_old = (datetime.utcnow() - last_verified_at).days
                if days_old > 180:
                    confidence = 0.85
                    reason = "SMTP verified (180+ days old, consider re-verify)"
            
            return {
                "deliverable": True,
                "deliverability_confidence": confidence,
                "reason": reason,
            }
        
        # Catch-all = technically deliverable but risky
        if catch_all:
            return {
                "deliverable": True,
                "deliverability_confidence": 0.5,
                "reason": "Domain is catch-all (accepts any address)",
            }
        
        # Unknown
        return {
            "deliverable": None,
            "deliverability_confidence": 0.3,
            "reason": "Verification status unknown",
        }

    @staticmethod
    def combine_layers(
        existence: Dict,
        association: Optional[Dict] = None,
        deliverability: Optional[Dict] = None,
    ) -> Dict:
        """
        Combine three layers into final response.
        
        Key rule: If email doesn't exist, association is irrelevant.
        """
        
        # If email doesn't exist, return only that
        if not existence.get("exists"):
            return {
                "email_exists": False,
                "existence_confidence": 0.0,
                "reason": existence.get("reason"),
                "show_to_user": False,
                "is_factual": False,
            }
        
        # Email exists (factual = 100%)
        response = {
            "email_exists": True,
            "existence_confidence": 1.0,  # ALWAYS 1.0 if exists
            "reason_existence": existence.get("reason"),
            "is_factual": True,
        }
        
        # Add association confidence if person was specified
        if association:
            response.update({
                "person_match_confidence": association.get("person_match_confidence", 0.0),
                "reason_association": association.get("reason", ""),
            })
        
        # Add deliverability
        if deliverability:
            response.update({
                "deliverable": deliverability.get("deliverable"),
                "deliverability_confidence": deliverability.get("deliverability_confidence", 0.0),
                "reason_deliverability": deliverability.get("reason", ""),
            })
        
        # Final UI confidence: existence (factual) vs association (probabilistic)
        if association:
            # User asked about a person: show both
            response["display_confidence"] = {
                "exists": 1.0,
                "matches_person": association.get("person_match_confidence", 0.0),
            }
        else:
            # Just showing discovered email: show existence only
            response["display_confidence"] = 1.0
        
        response["show_to_user"] = True
        
        return response