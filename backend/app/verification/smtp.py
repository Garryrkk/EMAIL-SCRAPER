import logging
import aiosmtplib
from email_validator import validate_email, EmailNotValidError
import asyncio

from app.core.config import settings
from app.core.constants import EmailStatus

logger = logging.getLogger(__name__)


class SMTPVerifier:
    """SMTP-based email verification."""

    async def verify_syntax(self, email: str) -> bool:
        """Verify email syntax."""
        try:
            validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError:
            return False

    async def verify_smtp(
        self,
        email: str,
        domain: str,
    ) -> dict:
        """Verify email via SMTP handshake."""
        if not settings.SMTP_VERIFICATION_ENABLED:
            return {
                "valid": False,
                "reason": "SMTP verification disabled",
            }

        try:
            # Get MX records for domain
            import dns.resolver
            
            try:
                mx_records = await asyncio.to_thread(
                    dns.resolver.resolve,
                    domain,
                    'MX',
                )
                if not mx_records:
                    return {
                        "valid": False,
                        "reason": "No MX records",
                    }
            except Exception as e:
                logger.error(f"MX lookup failed for {domain}: {e}")
                return {
                    "valid": False,
                    "reason": "MX lookup failed",
                }

            # Try SMTP verification with first MX
            mx_host = str(mx_records[0].exchange)
            
            result = await self._check_smtp(email, mx_host)
            return result

        except Exception as e:
            logger.error(f"SMTP verification error for {email}: {e}")
            return {
                "valid": False,
                "reason": "SMTP check failed",
            }

    async def _check_smtp(self, email: str, mx_host: str) -> dict:
        """Check email with SMTP server."""
        try:
            async with aiosmtplib.SMTP(
                hostname=mx_host,
                timeout=settings.SMTP_VERIFY_TIMEOUT,
            ) as smtp:
                # EHLO
                await asyncio.wait_for(
                    smtp.ehlo(),
                    timeout=5,
                )

                # MAIL FROM
                await asyncio.wait_for(
                    smtp.mail(settings.SMTP_FROM),
                    timeout=5,
                )

                # RCPT TO
                try:
                    await asyncio.wait_for(
                        smtp.rcpt(email),
                        timeout=5,
                    )
                    # Reset connection
                    await asyncio.wait_for(
                        smtp.rset(),
                        timeout=5,
                    )

                    return {
                        "valid": True,
                        "reason": "SMTP accepted",
                    }

                except aiosmtplib.SMTPRecipientsRefused as e:
                    return {
                        "valid": False,
                        "reason": "SMTP rejected recipient",
                        "error": str(e),
                    }
                except aiosmtplib.SMTPServerAuth as e:
                    return {
                        "valid": False,
                        "reason": "SMTP auth error",
                    }

        except asyncio.TimeoutError:
            logger.warning(f"SMTP timeout for {email}")
            return {
                "valid": False,
                "reason": "SMTP timeout",
            }
        except Exception as e:
            logger.error(f"SMTP connection error: {e}")
            return {
                "valid": False,
                "reason": "SMTP connection failed",
            }

    async def verify_email(self, email: str, domain: str) -> dict:
        """Complete email verification."""
        # Syntax check
        syntax_valid = await self.verify_syntax(email)
        if not syntax_valid:
            return {
                "status": EmailStatus.INVALID,
                "confidence": 0.0,
                "reason": "Invalid syntax",
            }

        # SMTP check
        smtp_result = await self.verify_smtp(email, domain)

        if smtp_result.get("valid"):
            return {
                "status": EmailStatus.VALID,
                "confidence": 0.9,
                "reason": "SMTP verification passed",
            }
        else:
            return {
                "status": EmailStatus.UNKNOWN,
                "confidence": 0.3,
                "reason": smtp_result.get("reason"),
            }