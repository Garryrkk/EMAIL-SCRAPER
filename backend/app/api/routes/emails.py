import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from app.api.deps import get_current_user, check_user_rate_limit, get_db
from app.users.model import User
from app.users.service import UserService
from app.emails.service import EmailService
from app.verification.smtp import SMTPVerifier
from app.inference.confidence import ConfidenceScorer

logger = logging.getLogger(__name__)

router = APIRouter()


class VerifyEmailRequest(BaseModel):
    """Email verification request."""
    email: str
    domain: str


class VerifyEmailResponse(BaseModel):
    """Email verification response."""
    email: str
    status: str
    confidence: float
    reason: str


@router.post("/verify", response_model=VerifyEmailResponse)
async def verify_email(
    req: VerifyEmailRequest,
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Verify single email."""
    try:
        # Check credits
        user_service = UserService(db)
        if current_user.credits < 2:  # Verification costs 2 credits
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits",
            )

        email_service = EmailService(db)
        verifier = SMTPVerifier()

        # Verify
        result = await verifier.verify_email(req.email, req.domain)

        # Save verification result
        email = await email_service.create_email(
            address=req.email,
            domain=req.domain,
        )

        await email_service.update_verification_status(
            email.id,
            result["status"],
            confidence=result.get("confidence", 0.0),
        )

        # Deduct credits
        await user_service.deduct_credits(current_user.id, 2)
        await db.commit()

        return VerifyEmailResponse(
            email=req.email,
            status=result["status"],
            confidence=result.get("confidence", 0.0),
            reason=result.get("reason", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


@router.post("/bulk-verify")
async def bulk_verify(
    emails: List[str],
    domain: str,
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Verify multiple emails."""
    try:
        user_service = UserService(db)
        email_service = EmailService(db)
        verifier = SMTPVerifier()

        # Check credits
        cost = len(emails) * 2
        if current_user.credits < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. Need {cost}, have {current_user.credits}",
            )

        results = []
        email_ids = []

        for email_addr in emails:
            result = await verifier.verify_email(email_addr, domain)
            email = await email_service.create_email(
                address=email_addr,
                domain=domain,
            )
            await email_service.update_verification_status(
                email.id,
                result["status"],
                confidence=result.get("confidence", 0.0),
            )
            email_ids.append(email.id)

            results.append({
                "email": email_addr,
                "status": result["status"],
                "confidence": result.get("confidence", 0.0),
            })

        # Deduct credits
        await user_service.deduct_credits(current_user.id, cost)
        await db.commit()

        return {
            "verified": len(results),
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk verification failed",
        )


@router.get("/{email_id}")
async def get_email(
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get email details."""
    try:
        email_service = EmailService(db)
        email = await email_service.get_email_by_id(email_id)

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found",
            )

        # Record view
        await email_service.record_view(email_id)
        await db.commit()

        return {
            "id": email.id,
            "address": email.address,
            "domain": email.domain,
            "status": email.status,
            "confidence": email.confidence,
            "source": email.source,
            "view_count": email.view_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get email error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get email",
        )