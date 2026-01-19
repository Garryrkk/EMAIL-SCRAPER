import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.users.model import User
from app.users.service import UserService
from app.auth.schemas import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    """Update profile request."""
    name: str = None
    company: str = None


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile."""
    return current_user


@router.put("/me")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile."""
    try:
        user_service = UserService(db)

        if req.name:
            current_user.name = req.name
        if req.company:
            current_user.company = req.company

        await db.flush()
        await db.commit()

        return UserResponse.model_validate(current_user)

    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        )


@router.get("/credits")
async def get_credits(
    current_user: User = Depends(get_current_user),
):
    """Get user credits."""
    return {
        "credits": current_user.credits,
        "monthly_limit": current_user.monthly_credits_limit,
        "plan": current_user.plan,
    }


@router.get("/usage")
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user usage statistics."""
    try:
        # TODO: Get from usage tracking table
        return {
            "user_id": current_user.id,
            "plan": current_user.plan,
            "credits_used": 0,
            "credits_remaining": current_user.credits,
            "searches_this_month": 0,
            "verifications_this_month": 0,
            "exports_this_month": 0,
        }

    except Exception as e:
        logger.error(f"Get usage error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage",
        )