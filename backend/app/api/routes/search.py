import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from app.api.deps import get_current_user, check_user_rate_limit, get_db
from app.users.model import User
from app.companies.service import CompanyService
from app.emails.service import EmailService
from app.discovery.crawler import WebCrawler
from app.discovery.extractor import EmailExtractor
from app.emails.generator import EmailGenerator
from app.inference.confidence import ConfidenceScorer
from app.verification.smtp import SMTPVerifier

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchRequest(BaseModel):
    """Domain search request."""
    domain: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class EmailResult(BaseModel):
    """Email result."""
    email: str
    confidence: float
    source: str
    status: str


class SearchResponse(BaseModel):
    """Search response."""
    domain: str
    emails: List[EmailResult]
    pattern: Optional[str]
    pattern_confidence: float


@router.post("/domain", response_model=SearchResponse)
async def search_domain(
    req: SearchRequest,
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Search for emails at a domain."""
    try:
        company_service = CompanyService(db)
        email_service = EmailService(db)

        # Get or create company
        company = await company_service.create_company(
            domain=req.domain,
            name=req.domain,
        )

        # Check if we have cached results
        existing_emails = await email_service.get_emails_by_company(
            company.id
        )

        if existing_emails:
            # Return cached results
            results = [
                EmailResult(
                    email=e.address,
                    confidence=e.confidence,
                    source=e.source,
                    status=e.status,
                )
                for e in existing_emails
            ]
            return SearchResponse(
                domain=req.domain,
                emails=results,
                pattern=company.detected_pattern,
                pattern_confidence=company.pattern_confidence,
            )

        # Crawl domain
        crawler = WebCrawler()
        await crawler.initialize()

        try:
            pages = await crawler.crawl_domain(req.domain)

            # Extract emails
            extractor = EmailExtractor()
            discovered_emails = set()

            for page in pages:
                result = extractor.extract_from_html(
                    page["content"],
                    req.domain,
                )
                discovered_emails.update(result.get("emails", []))

            # Detect pattern
            generator = EmailGenerator()
            pattern, pattern_confidence = generator.detect_pattern(
                list(discovered_emails),
                req.domain,
            )

            await company_service.set_detected_pattern(
                company.id,
                pattern,
                pattern_confidence,
            )

            # Generate candidate emails
            candidates = set()
            if req.first_name and req.last_name:
                generated = generator.generate_from_person(
                    req.first_name,
                    req.last_name,
                    req.domain,
                    pattern,
                )
                candidates.update(generated)

            # Combine discovered + generated
            all_emails = discovered_emails | candidates

            # Score each email
            scorer = ConfidenceScorer()
            verifier = SMTPVerifier()
            results = []

            for email in list(all_emails)[:50]:  # Limit to 50
                syntax_valid = await verifier.verify_syntax(email)
                confidence, status_val = scorer.score_email(
                    syntax_valid=syntax_valid,
                    pattern_confidence=pattern_confidence,
                    discovery_source="discovered" if email in discovered_emails else "inferred",
                )

                # Save to database
                await email_service.create_email(
                    address=email,
                    domain=req.domain,
                    company_id=company.id,
                    source="discovered" if email in discovered_emails else "inferred",
                    pattern_used=pattern if email not in discovered_emails else None,
                )

                results.append(
                    EmailResult(
                        email=email,
                        confidence=confidence,
                        source="discovered" if email in discovered_emails else "inferred",
                        status=status_val,
                    )
                )

            # Sort by confidence
            results = sorted(results, key=lambda x: x.confidence, reverse=True)

            await db.commit()

            return SearchResponse(
                domain=req.domain,
                emails=results,
                pattern=pattern,
                pattern_confidence=pattern_confidence,
            )

        finally:
            await crawler.close()

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )


@router.post("/person")
async def search_person(
    first_name: str,
    last_name: str,
    domain: str,
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Search for person at domain."""
    try:
        company_service = CompanyService(db)
        company = await company_service.get_company_by_domain(domain)

        if not company or not company.detected_pattern:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found or pattern not detected",
            )

        generator = EmailGenerator()
        emails = generator.generate_from_person(
            first_name,
            last_name,
            domain,
            company.detected_pattern,
        )

        scorer = ConfidenceScorer()
        results = []

        for email in emails:
            confidence, status_val = scorer.score_email(
                pattern_confidence=company.pattern_confidence,
            )
            results.append({
                "email": email,
                "confidence": confidence,
            })

        return {
            "first_name": first_name,
            "last_name": last_name,
            "domain": domain,
            "emails": sorted(results, key=lambda x: x["confidence"], reverse=True),
        }

    except Exception as e:
        logger.error(f"Person search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )