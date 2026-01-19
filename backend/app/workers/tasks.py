import logging
import asyncio
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import _session_factory
from app.companies.model import Company
from app.emails.model import Email
from app.discovery.crawler import WebCrawler
from app.discovery.extractor import EmailExtractor
from app.emails.generator import EmailGenerator
from app.verification.smtp import SMTPVerifier
from app.inference.confidence import ConfidenceScorer
from app.companies.service import CompanyService
from app.emails.service import EmailService

logger = logging.getLogger(__name__)


async def crawl_company_task(domain: str):
    """Background task to crawl company domain."""
    async with _session_factory() as session:
        try:
            company_service = CompanyService(session)
            email_service = EmailService(session)

            logger.info(f"Crawling domain: {domain}")

            crawler = WebCrawler()
            await crawler.initialize()

            try:
                pages = await crawler.crawl_domain(domain)

                # Extract emails
                extractor = EmailExtractor()
                discovered_emails = set()

                for page in pages:
                    result = extractor.extract_from_html(
                        page["content"],
                        domain,
                    )
                    discovered_emails.update(result.get("emails", []))

                # Detect pattern
                generator = EmailGenerator()
                pattern, confidence = generator.detect_pattern(
                    list(discovered_emails),
                    domain,
                )

                # Update company
                company = await company_service.get_company_by_domain(domain)
                if company:
                    await company_service.set_detected_pattern(
                        company.id,
                        pattern,
                        confidence,
                    )
                    await company_service.update_email_counts(
                        company.id,
                        crawl_count=len(discovered_emails),
                    )
                    await company_service.mark_crawled(company.id)

                logger.info(f"Crawl complete for {domain}: {len(discovered_emails)} emails found")

            finally:
                await crawler.close()

            await session.commit()

        except Exception as e:
            logger.error(f"Crawl task error for {domain}: {e}")
            await session.rollback()


async def verify_emails_task(company_id: str, batch_size: int = 50):
    """Background task to verify emails for company."""
    async with _session_factory() as session:
        try:
            email_service = EmailService(session)
            verifier = SMTPVerifier()
            scorer = ConfidenceScorer()

            logger.info(f"Verifying emails for company: {company_id}")

            emails = await email_service.get_emails_by_company(company_id, limit=batch_size)

            verified_count = 0
            for email in emails:
                if email.status != "unknown":
                    continue

                try:
                    result = await verifier.verify_smtp(
                        email.address,
                        email.domain,
                    )

                    if result.get("valid"):
                        confidence = 0.9
                        status = "valid"
                    else:
                        confidence = 0.3
                        status = "unknown"

                    await email_service.update_verification_status(
                        email.id,
                        status,
                        confidence=confidence,
                    )

                    verified_count += 1

                except Exception as e:
                    logger.error(f"Error verifying {email.address}: {e}")

            logger.info(f"Verified {verified_count} emails for company {company_id}")
            await session.commit()

        except Exception as e:
            logger.error(f"Verify task error: {e}")
            await session.rollback()


async def cleanup_old_data_task():
    """Background task to cleanup old data."""
    async with _session_factory() as session:
        try:
            logger.info("Running data cleanup task")

            cutoff_date = datetime.utcnow() - timedelta(days=90)

            # Delete old unverified emails
            result = await session.execute(
                select(Email).where(
                    Email.last_verified_at < cutoff_date,
                    Email.status == "unknown",
                )
            )
            old_emails = result.scalars().all()

            for email in old_emails:
                await session.delete(email)

            logger.info(f"Deleted {len(old_emails)} old emails")
            await session.commit()

        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            await session.rollback()


async def update_bounce_stats_task():
    """Background task to update bounce statistics."""
    async with _session_factory() as session:
        try:
            logger.info("Updating bounce statistics")

            result = await session.execute(select(Company))
            companies = result.scalars().all()

            for company in companies:
                emails = await session.execute(
                    select(Email).where(Email.company_id == company.id)
                )
                emails = emails.scalars().all()

                if not emails:
                    continue

                bounce_count = sum(1 for e in emails if e.bounce_count > 0)
                bounce_rate = bounce_count / len(emails) if emails else 0

                company.bounce_rate = bounce_rate

            await session.commit()
            logger.info("Bounce statistics updated")

        except Exception as e:
            logger.error(f"Bounce stats task error: {e}")
            await session.rollback()