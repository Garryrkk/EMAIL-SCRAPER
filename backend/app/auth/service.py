import logging
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.users.service import UserService
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.auth.schemas import SignupRequest, LoginRequest, TokenResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service."""

    def __init__(self, db: AsyncSession):
        self.user_service = UserService(db)

    async def signup(self, req: SignupRequest) -> TokenResponse:
        """Register new user."""
        # Check if user exists
        existing = await self.user_service.get_user_by_email(req.email)
        if existing:
            raise ValueError("Email already registered")

        # Create user
        user = await self.user_service.create_user(
            email=req.email,
            password=req.password,
            name=req.name,
            company=req.company if req.company and req.company.strip() else None,
        )

        # Generate tokens
        access_token = create_access_token({"user_id": user.id})
        refresh_token = create_refresh_token(user.id)

        logger.info(f"User registered: {req.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
        )

    async def login(self, req: LoginRequest) -> TokenResponse:
        """Authenticate user."""
        # Verify credentials
        user = await self.user_service.verify_credentials(
            req.email,
            req.password,
        )

        if not user:
            logger.warning(f"Failed login attempt: {req.email}")
            raise ValueError("Invalid credentials")

        # Generate tokens
        access_token = create_access_token({"user_id": user.id})
        refresh_token = create_refresh_token(user.id)

        logger.info(f"User logged in: {req.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token."""
        # Verify refresh token
        payload = verify_token(refresh_token)

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        user_id = payload.get("user_id")
        user = await self.user_service.get_user_by_id(user_id)

        if not user:
            raise ValueError("User not found")

        # Generate new access token
        access_token = create_access_token({"user_id": user.id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
        )

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        user = await self.user_service.get_user_by_id(user_id)

        if not user:
            raise ValueError("User not found")

        # Verify current password
        from core.security import verify_password
        if not verify_password(current_password, user.password_hash):
            raise ValueError("Invalid current password")

        # Update password
        return await self.user_service.update_password(user_id, new_password)