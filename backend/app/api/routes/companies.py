import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.users.model import User
from app.companies.service import CompanyService
from app.emails.service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{domain}")
async def get_company(
    domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get company information."""
    try:
        company_service = CompanyService(db)
        company = await company_service.get_company_by_domain(domain)

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # Get email stats
        email_service = EmailService(db)
        emails = await email_service.get_emails_by_company(company.id, limit=1000)

        return {
            "id": company.id,
            "domain": company.domain,
            "name": company.name,
            "industry": company.industry,
            "size": company.size,
            "confidence_score": company.confidence_score,
            "detected_pattern": company.detected_pattern,
            "pattern_confidence": company.pattern_confidence,
            "public_emails_count": company.public_emails_count,
            "bounce_rate": company.bounce_rate,
            "is_verified": company.is_verified,
            "last_crawled_at": company.last_crawled_at,
            "last_verified_at": company.last_verified_at,
            "email_count": len(emails),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get company error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get company",
        )


@router.post("/{domain}/rescan")
async def rescan_company(
    domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rescan company for emails."""
    try:
        company_service = CompanyService(db)
        company = await company_service.get_company_by_domain(domain)

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # TODO: Queue background job to rescan

        return {
            "message": "Rescan queued",
            "domain": domain,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rescan error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue rescan",
        )