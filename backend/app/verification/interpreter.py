import logging
from app.verification.smtp import SMTPVerificationResult

logger = logging.getLogger(__name__)


class SMTPResultInterpreter:
    """
    Interpret SMTP sensor results for use in confidence layers.
    
    SMTP returns raw technical signals.
    This class translates those into data for confidence_layered.py.
    
    KEY SEPARATION:
    - SMTP = sensor (what happened)
    - Interpreter = translator (what it means)
    - confidence_layered.py = judge (what to do)
    """

    @staticmethod
    def interpret(smtp_result: SMTPVerificationResult) -> dict:
        """
        Convert SMTP technical results into facts for confidence layer.
        
        Returns:
            {
                "syntax_valid": bool,
                "mx_valid": bool,
                "smtp_accepts": bool,
                "catch_all": bool,
                "can_verify": bool,  # Can we trust this result?
                "error": str or None
            }
        """
        
        interpretation = {
            "syntax_valid": smtp_result.syntax_valid,
            "mx_valid": smtp_result.mx_valid,
            "smtp_accepts": smtp_result.smtp_accepts,
            "catch_all": smtp_result.catch_all,
            "error": smtp_result.smtp_error,
        }

        # Determine if this result is trustworthy
        # (for confidence_layered.py to decide what to do)
        if smtp_result.syntax_valid and smtp_result.mx_valid:
            interpretation["can_verify"] = True
        else:
            interpretation["can_verify"] = False

        logger.debug(f"Interpretation: {interpretation}")
        return interpretation

    @staticmethod
    def explain_smtp_result(smtp_result: SMTPVerificationResult) -> str:
        """
        Human-readable explanation of SMTP result.
        
        Used for logging and debugging only.
        NOT for confidence calculations.
        """
        
        if not smtp_result.syntax_valid:
            return "Email syntax invalid"
        
        if not smtp_result.mx_valid:
            return "Domain has no valid MX records"
        
        if smtp_result.smtp_accepts and smtp_result.catch_all:
            return "Domain accepts all emails (catch-all)"
        
        if smtp_result.smtp_accepts and not smtp_result.catch_all:
            return "SMTP server accepts this specific email"
        
        if not smtp_result.smtp_accepts:
            return "SMTP server rejects this email"
        
        if smtp_result.smtp_error:
            return f"SMTP error: {smtp_result.smtp_error}"
        
        return "Verification complete"