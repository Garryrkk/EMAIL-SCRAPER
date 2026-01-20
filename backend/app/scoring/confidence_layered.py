import logging
from typing import Dict, Optional
from datetime import datetime
from app.verification.interpreter import SMTPResultInterpreter
from app.verification.smtp import SMTPVerificationResult

logger = logging.getLogger(__name__)


class LayeredConfidenceEngine:
    """
    Three separate confidence layers (Apollo/Hunter model).
    
    This layer INTERPRETS SMTP results.
    It does NOT accept confidence from SMTP.
    SMTP only provides technical signals.
    """

    @staticmethod
    def score_email_existence(
        email: str,
        source: str,  # "discovered", "inferred", "verification_inferred"
        smtp_result: Optional[SMTPVerificationResult] = None,
    ) -> Dict:
        """
        LAYER 1: Does this email EXIST for this company?
        
        This is FACTUAL, not probabilistic.
        
        Rules:
        - Discovered on website: 1.0 (FACT, SMTP irrelevant)
        - Generated + SMTP accepts: 1.0 (FACT)
        - Generated + SMTP rejects: 0.0 (NOT proven)
        
        CRITICAL: SMTP does NOT override discovery.
        """
        
        # RULE: Discovered emails are facts
        if source == "discovered":
            return {
                "exists": True,
                "existence_confidence": 1.0,
                "reason": "Found on company website (factual)",
                "is_factual": True,
                "smtp_ignored": True,  # SMTP doesn't matter for discovered
            }
        
        # Verification-led inference (fallback)
        if source == "verification_inferred":
            if smtp_result:
                interpreter = SMTPResultInterpreter()
                interpretation = interpreter.interpret(smtp_result)
                
                # SMTP accepts = email exists
                if interpretation.get("smtp_accepts"):
                    return {
                        "exists": True,
                        "existence_confidence": 1.0,
                        "reason": "Generated and SMTP verified (factual)",
                        "is_factual": True,
                    }
            
            return {
                "exists": False,
                "existence_confidence": 0.0,
                "reason": "Generated but SMTP did not verify",
                "is_factual": False,
            }
        
        # Pure inferred (guessed, NOT factual)
        return {
            "exists": False,
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
        smtp_result: Optional[SMTPVerificationResult] = None,
    ) -> Dict:
        """
        LAYER 2: Does this email belong to THIS PERSON?
        
        This is PROBABILISTIC.
        SMTP provides SIGNAL, not truth.
        """
        
        # Base: Does pattern exist?
        if not pattern_used or pattern_confidence < 0.6:
            return {
                "person_match_confidence": 0.0,
                "reason": "No confirmed pattern for this company",
            }
        
        # Pattern exists: Apply pattern confidence
        base_confidence = pattern_confidence * 0.4  # Max 40% from pattern alone
        
        # SMTP as signal (not truth)
        verification_signal = 0.0
        if smtp_result:
            interpreter = SMTPResultInterpreter()
            interpretation = interpreter.interpret(smtp_result)
            
            # SMTP accepts = adds to association confidence
            if interpretation.get("smtp_accepts") and not interpretation.get("catch_all"):
                verification_signal = 0.55  # Strong signal
            elif interpretation.get("catch_all"):
                verification_signal = 0.10  # Weak signal (catch-all)
            # SMTP rejects = no signal, but doesn't prove association wrong
        
        total_confidence = base_confidence + verification_signal
        
        return {
            "person_match_confidence": min(total_confidence, 0.95),  # Never 100%
            "pattern_confidence_used": pattern_confidence,
            "verification_signal": verification_signal,
            "reason": f"Pattern ({pattern_confidence:.0%}) + SMTP signal ({verification_signal:.0%})",
        }

    @staticmethod
    def score_deliverability(
        email: str,
        smtp_result: Optional[SMTPVerificationResult] = None,
        last_verified_at: Optional[datetime] = None,
    ) -> Dict:
        """
        LAYER 3: Will this email reach inbox TODAY?
        
        This is PRACTICAL, not factual.
        SMTP is the primary signal here.
        Time decay applies.
        """
        
        if not smtp_result:
            return {
                "deliverable": None,
                "deliverability_confidence": 0.0,
                "reason": "No verification performed",
            }
        
        interpreter = SMTPResultInterpreter()
        interpretation = interpreter.interpret(smtp_result)
        
        # No MX = cannot deliver
        if not interpretation.get("mx_valid"):
            return {
                "deliverable": False,
                "deliverability_confidence": 0.0,
                "reason": "No valid MX records",
            }
        
        # Cannot verify syntax = cannot deliver
        if not interpretation.get("syntax_valid"):
            return {
                "deliverable": False,
                "deliverability_confidence": 0.0,
                "reason": "Email syntax invalid",
            }
        
        # SMTP rejects = cannot deliver
        if not interpretation.get("smtp_accepts"):
            return {
                "deliverable": False,
                "deliverability_confidence": 0.0,
                "reason": "SMTP server rejected this email",
            }
        
        # SMTP accepts = deliverable (but apply decay)
        confidence = 0.95
        reason = "SMTP accepted"
        
        # Time decay (slow)
        if last_verified_at:
            days_old = (datetime.utcnow() - last_verified_at).days
            if days_old > 180:
                confidence = 0.85
                reason = f"SMTP accepted {days_old} days ago (consider re-verify)"
            elif days_old > 30:
                confidence = 0.90
                reason = f"SMTP accepted {days_old} days ago"
        
        # Catch-all = deliverable but risky
        if interpretation.get("catch_all"):
            confidence = 0.5
            reason = "Domain is catch-all (accepts any address)"
        
        return {
            "deliverable": True,
            "deliverability_confidence": confidence,
            "reason": reason,
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
        
        # If email doesn't exist, stop here
        if not existence.get("exists"):
            return {
                "email_exists": False,
                "existence_confidence": 0.0,
                "reason": existence.get("reason"),
                "show_to_user": False,
                "is_factual": False,
            }
        
        # Email exists (factual = 1.0)
        response = {
            "email_exists": True,
            "existence_confidence": 1.0,
            "reason_existence": existence.get("reason"),
            "is_factual": True,
        }
        
        # Add association if person was specified
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
        
        # Final confidence for UI
        if association:
            # Person search: show both
            response["display_confidence"] = {
                "exists": 1.0,
                "matches_person": association.get("person_match_confidence", 0.0),
            }
        else:
            # Domain search: existence only
            response["display_confidence"] = 1.0
        
        response["show_to_user"] = True
        
        return response