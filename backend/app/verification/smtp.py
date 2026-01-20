import logging
import aiosmtplib
import asyncio
from email_validator import validate_email, EmailNotValidError
import dns.resolver
from typing import Dict, Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class SMTPVerificationResult:
    """
    Raw SMTP verification result.
    
    CRITICAL: This returns ONLY technical signals.
    NO confidence, NO status, NO existence claims.
    
    SMTP is a sensor, not a judge.
    """
    
    def __init__(self, email: str):
        self.email = email
        self.domain = email.split("@")[1]
        
        # Technical signals ONLY
        self.syntax_valid = False
        self.mx_valid = False
        self.smtp_accepts = False
        self.catch_all = False
        self.greylisted = False
        self.smtp_error = None
        self.checked_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Return technical results only."""
        return {
            "email": self.email,
            "domain": self.domain,
            
            # Technical signals
            "syntax_valid": self.syntax_valid,
            "mx_valid": self.mx_valid,
            "smtp_accepts": self.smtp_accepts,
            "catch_all": self.catch_all,
            "greylisted": self.greylisted,
            "smtp_error": self.smtp_error,
            "checked_at": self.checked_at.isoformat(),
            
            # NO confidence
            # NO status
            # NO existence claim
        }


class SMTPVerifier:
    """
    SMTP verification - sensor only.
    
    Responsibility:
    - Check syntax ✓
    - Check MX records ✓
    - Check SMTP handshake ✓
    - Detect catch-all ✓
    - Detect greylisting ✓
    
    NOT responsible for:
    - Confidence scoring ✗
    - Status assignment ✗
    - Existence determination ✗
    
    That's confidence_layered.py's job.
    """

    async def verify(self, email: str) -> SMTPVerificationResult:
        """
        Verify email and return technical results.
        
        CRITICAL: Does NOT assign confidence or status.
        Only returns what was actually tested.
        """
        result = SMTPVerificationResult(email)

        try:
            # Step 1: Syntax
            logger.debug(f"[{email}] Checking syntax...")
            if not await self._check_syntax(email):
                logger.debug(f"[{email}] Syntax failed")
                return result  # Return early, other checks not meaningful

            result.syntax_valid = True

            # Step 2: MX
            logger.debug(f"[{email}] Checking MX...")
            if not await self._check_mx(result.domain):
                logger.debug(f"[{email}] MX failed")
                return result  # Return early, SMTP check not possible

            result.mx_valid = True

            # Step 3: SMTP
            logger.debug(f"[{email}] Checking SMTP...")
            await self._check_smtp(email, result)

            logger.debug(f"[{email}] Verification complete: {result.to_dict()}")

        except Exception as e:
            logger.error(f"[{email}] Verification error: {e}")
            result.smtp_error = str(e)

        return result

    async def _check_syntax(self, email: str) -> bool:
        """
        Check email syntax.
        
        Returns: True/False (no confidence)
        """
        try:
            validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError as e:
            logger.debug(f"Syntax error: {e}")
            return False

    async def _check_mx(self, domain: str) -> bool:
        """
        Check if domain has MX records.
        
        Returns: True/False (no confidence)
        """
        try:
            mx_records = await asyncio.to_thread(
                dns.resolver.resolve,
                domain,
                'MX',
            )
            has_mx = len(mx_records) > 0
            logger.debug(f"MX check for {domain}: {has_mx}")
            return has_mx
        except Exception as e:
            logger.debug(f"MX lookup failed for {domain}: {e}")
            return False

    async def _check_smtp(self, email: str, result: SMTPVerificationResult):
        """
        Check SMTP handshake with enhanced catch-all and greylisting detection.
        
        Sets:
        - smtp_accepts: True/False
        - catch_all: True/False/Unknown
        - greylisted: True/False
        - smtp_error: Optional error message
        
        Does NOT set confidence or status.
        """
        try:
            # Get MX host
            mx_records = await asyncio.to_thread(
                dns.resolver.resolve,
                result.domain,
                'MX',
            )
            mx_host = str(mx_records[0].exchange)

            logger.debug(f"[{email}] Attempting SMTP on {mx_host}")

            # SMTP handshake
            async with aiosmtplib.SMTP(
                hostname=mx_host,
                timeout=30,
            ) as smtp:
                # EHLO
                try:
                    await asyncio.wait_for(smtp.ehlo(), timeout=5)
                except Exception as e:
                    logger.debug(f"[{email}] EHLO failed: {e}")
                    result.smtp_error = "EHLO failed"
                    return

                # MAIL FROM
                try:
                    await asyncio.wait_for(
                        smtp.mail("verify@verification.service"),
                        timeout=5,
                    )
                except Exception as e:
                    logger.debug(f"[{email}] MAIL FROM failed: {e}")
                    result.smtp_error = "MAIL FROM failed"
                    return

                # RCPT TO - This is the key test
                try:
                    response = await asyncio.wait_for(
                        smtp.rcpt(email),
                        timeout=5,
                    )
                    
                    # Check for greylisting (4xx codes)
                    if hasattr(response, 'code') and 400 <= response.code < 500:
                        result.greylisted = True
                        logger.debug(f"[{email}] Greylisted (4xx response)")
                        # RSET and return early
                        try:
                            await asyncio.wait_for(smtp.rset(), timeout=5)
                        except Exception:
                            pass
                        return
                    
                    # Server accepted the recipient
                    result.smtp_accepts = True
                    logger.debug(f"[{email}] SMTP accepts: YES")

                except aiosmtplib.SMTPRecipientsRefused as e:
                    # Check if it's a temporary failure (greylisting)
                    error_str = str(e)
                    if any(code in error_str for code in ['450', '451', '452']):
                        result.greylisted = True
                        logger.debug(f"[{email}] Greylisted (refused with 4xx)")
                    else:
                        # Server rejected the recipient
                        result.smtp_accepts = False
                        logger.debug(f"[{email}] SMTP accepts: NO ({e})")

                except aiosmtplib.SMTPServerAuth as e:
                    # Catch-all detected (server wants auth, likely catch-all)
                    result.catch_all = True
                    result.smtp_accepts = True  # Technically accepts
                    logger.debug(f"[{email}] Catch-all detected (auth challenge)")

                # Silent catch-all detection
                # Only run if email was accepted but not already flagged as catch-all
                if result.smtp_accepts and not result.catch_all:
                    logger.debug(f"[{email}] Running silent catch-all detection...")
                    is_catch_all = await self._detect_silent_catchall(
                        smtp, 
                        result.domain
                    )
                    if is_catch_all:
                        result.catch_all = True
                        logger.debug(f"[{email}] Silent catch-all detected")

                # RSET - reset connection
                try:
                    await asyncio.wait_for(smtp.rset(), timeout=5)
                except Exception:
                    pass  # Not critical

        except asyncio.TimeoutError:
            logger.warning(f"[{email}] SMTP timeout")
            result.smtp_error = "SMTP timeout"

        except Exception as e:
            logger.error(f"[{email}] SMTP connection error: {e}")
            result.smtp_error = str(e)

    async def _detect_silent_catchall(
        self, 
        smtp: aiosmtplib.SMTP, 
        domain: str
    ) -> bool:
        """
        Detect silent catch-all by testing a random non-existent address.
        
        Logic:
        - Generate random email that definitely doesn't exist
        - Test RCPT TO with that address
        - If server accepts it → catch-all
        
        Returns: True if catch-all detected, False otherwise
        """
        try:
            # Generate random address that definitely doesn't exist
            random_local = f"nonexistent_{uuid4().hex[:16]}"
            test_email = f"{random_local}@{domain}"
            
            logger.debug(f"Testing catch-all with: {test_email}")
            
            # Test RCPT TO with random address
            try:
                await asyncio.wait_for(
                    smtp.rcpt(test_email),
                    timeout=5,
                )
                # If server accepts random address → catch-all
                logger.debug(f"Server accepted random address → catch-all")
                return True
                
            except aiosmtplib.SMTPRecipientsRefused:
                # Server rejected random address → NOT catch-all
                logger.debug(f"Server rejected random address → NOT catch-all")
                return False
                
            except aiosmtplib.SMTPServerAuth:
                # Auth challenge for random address → catch-all
                logger.debug(f"Auth challenge for random address → catch-all")
                return True
                
        except Exception as e:
            logger.debug(f"Catch-all detection failed: {e}")
            # On error, assume NOT catch-all (conservative)
            return False


class BulkSMTPVerifier:
    """
    Verify multiple emails concurrently.
    
    Still returns ONLY technical results, no confidence.
    """

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.verifier = SMTPVerifier()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def verify_batch(
        self,
        emails: list,
    ) -> list:
        """
        Verify multiple emails with concurrency control.
        
        Returns: List of SMTPVerificationResult objects
        """
        tasks = [self._verify_with_limit(email) for email in emails]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log them
        clean_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch verification error: {result}")
            else:
                clean_results.append(result)

        logger.info(f"Batch verification: {len(clean_results)}/{len(emails)} completed")
        return clean_results

    async def _verify_with_limit(self, email: str) -> SMTPVerificationResult:
        """Verify with semaphore to limit concurrency."""
        async with self.semaphore:
            return await self.verifier.verify(email)