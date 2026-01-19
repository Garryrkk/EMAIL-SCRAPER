import logging
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, AsyncGenerator

from app.core.database import get_session
from app.core.security import get_user_id_from_token
from app.core.rate_limit import check_rate_limit
from app.users.model import User
from app.users.service import UserService
from app.core.constants import UserStatus

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with get_session() as session:
        yield session


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")
    user_id = get_user_id_from_token(token)

    # Get user from database
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended",
        )

    return user


async def check_user_rate_limit(
    current_user: User = Depends(get_current_user),
) -> User:
    """Check if user has rate limit remaining."""
    allowed, remaining = await check_rate_limit(current_user.id)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    return current_user


async def check_credits(
    min_credits: int = 1,
) -> callable:
    """Factory to check if user has credits."""
    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.credits < min_credits:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits",
            )
        return current_user

    return _check