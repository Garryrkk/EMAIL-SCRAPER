import logging
import asyncio
from typing import Dict, Optional
import dns.resolver
import aiosmtplib
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)


class VerificationResult:
    """Result of email verification."""
    
    def __init__(self, email: str):
        self.email = email
        self.domain = email.split("@")[1]
        
        # Results
        self.syntax_valid = False
        self.mx_exists = False
        self.smtp_accepted = False
        self.catch_all = False
        self.blocked = False
        
        # Final status
        self.verification_status = "unverified"
        self.confidence = 0.0
        self.reason = ""

    def to_dict(self):
        return {
            "email": self.email,
            "status": self.verification_status,
            "confidence": self.confidence,
            "reason": self.reason,
            "details": {
                "syntax_valid": self.syntax_valid,
                "mx_exists": self.mx_exists,
                "smtp_accepted": self.smtp_accepted,
                "catch_all": self.catch_all,
                "blocked": self.blocked,
            }
        }


class VerificationAggregator:
    """
    Multi-stage verification pipeline.
    
    RULES:
    - Syntax fail → INVALID (stop)
    - MX fail → INVALID (stop)
    - SMTP accept → VALID (high confidence)
    - SMTP reject → INVALID
    - Catch-all → RISKY
    """

    def __init__(self):
        self.result = None

    async def verify(self, email: str) -> VerificationResult:
        """
        Complete verification pipeline.
        """
        self.result = VerificationResult(email)

        try:
            # Step 1: Syntax
            logger.debug(f"[{email}] Verifying syntax...")
            if not await self._verify_syntax():
                self.result.verification_status = "invalid"
                self.result.reason = "Invalid email syntax"
                return self.result

            # Step 2: MX records
            logger.debug(f"[{email}] Checking MX records...")
            if not await self._check_mx():
                self.result.verification_status = "invalid"
                self.result.reason = "No valid MX records for domain"
                return self.result

            # Step 3: SMTP verification
            logger.debug(f"[{email}] Running SMTP verification...")
            await self._check_smtp()

            # Step 4: Determine final status
            self._determine_status()

            logger.info(
                f"[{email}] Verification complete: "
                f"{self.result.verification_status} ({self.result.confidence:.0%})"
            )

        except Exception as e:
            logger.error(f"Verification error for {email}: {e}")
            self.result.verification_status = "unknown"
            self.result.confidence = 0.3
            self.result.reason = "Verification error"

        return self.result

    async def _verify_syntax(self) -> bool:
        """Check email syntax is valid."""
        try:
            validate_email(self.result.email, check_deliverability=False)
            self.result.syntax_valid = True
            return True
        except EmailNotValidError as e:
            logger.debug(f"Syntax error: {e}")
            return False

    async def _check_mx(self) -> bool:
        """Check if domain has MX records."""
        try:
            mx_records = await asyncio.to_thread(
                dns.resolver.resolve,
                self.result.domain,
                'MX',
            )
            self.result.mx_exists = len(mx_records) > 0
            return self.result.mx_exists
        except Exception as e:
            logger.debug(f"MX lookup failed: {e}")
            return False

    async def _check_smtp(self):
        """Check deliverability via SMTP handshake."""
        if not self.result.mx_exists:
            return

        try:
            # Get MX host
            mx_records = await asyncio.to_thread(
                dns.resolver.resolve,
                self.result.domain,
                'MX',
            )
            mx_host = str(mx_records[0].exchange)

            # SMTP check
            try:
                async with aiosmtplib.SMTP(
                    hostname=mx_host,
                    timeout=30,
                ) as smtp:
                    await asyncio.wait_for(smtp.ehlo(), timeout=5)
                    await asyncio.wait_for(
                        smtp.mail("verify@verification.service"),
                        timeout=5,
                    )

                    try:
                        await asyncio.wait_for(
                            smtp.rcpt(self.result.email),
                            timeout=5,
                        )
                        self.result.smtp_accepted = True
                        logger.debug(f"[{self.result.email}] SMTP accepted")

                    except aiosmtplib.SMTPRecipientsRefused:
                        self.result.smtp_accepted = False
                        logger.debug(f"[{self.result.email}] SMTP rejected")

                    except aiosmtplib.SMTPServerAuth:
                        # Catch-all detection
                        self.result.catch_all = True
                        logger.debug(f"[{self.result.email}] Catch-all detected")

                    # Reset
                    try:
                        await asyncio.wait_for(smtp.rset(), timeout=5)
                    except Exception:
                        pass

            except asyncio.TimeoutError:
                logger.warning(f"[{self.result.email}] SMTP timeout")
                self.result.verification_status = "unknown"

        except Exception as e:
            logger.debug(f"SMTP check error: {e}")

    def _determine_status(self):
        """
        Determine final status based on all checks.
        
        Logic:
        - SMTP accepted → VALID
        - MX valid but SMTP rejected → INVALID
        - Catch-all detected → RISKY
        - Unknown → UNVERIFIED
        """
        if self.result.smtp_accepted:
            self.result.verification_status = "valid"
            self.result.confidence = 0.95
            self.result.reason = "SMTP verification passed"
        elif self.result.catch_all:
            self.result.verification_status = "catch_all"
            self.result.confidence = 0.5
            self.result.reason = "Domain is catch-all (accepts any email)"
        else:
            self.result.verification_status = "invalid"
            self.result.confidence = 0.1
            self.result.reason = "SMTP verification failed"