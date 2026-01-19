import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid

from app.users.model import User
from app.core.security import hash_password, verify_password
from app.core.constants import UserStatus, UserPlan

logger = logging.getLogger(__name__)


class UserService:
    """User management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        email: str,
        password: str,
        name: str,
        company: str = None,
        plan: str = UserPlan.FREE,
    ) -> User:
        """Create new user."""
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=hash_password(password),
            name=name,
            company=company if company and company.strip() else None,
            plan=plan,
        )
        self.db.add(user)
        await self.db.flush()
        logger.info(f"User created: {email}")
        return user

    async def get_user_by_email(self, email: str) -> User:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def get_user_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()

    async def verify_credentials(self, email: str, password: str) -> User:
        """Verify user credentials."""
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        await self.db.flush()
        return user

    async def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.password_hash = hash_password(new_password)
        await self.db.flush()
        logger.info(f"Password updated for user: {user.email}")
        return True

    async def deduct_credits(self, user_id: str, amount: int) -> bool:
        """Deduct credits from user."""
        user = await self.get_user_by_id(user_id)
        if not user or user.credits < amount:
            return False

        user.credits -= amount
        await self.db.flush()
        return True

    async def add_credits(self, user_id: str, amount: int) -> bool:
        """Add credits to user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.credits += amount
        await self.db.flush()
        return True

    async def update_plan(self, user_id: str, plan: str) -> bool:
        """Update user plan."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.plan = plan
        await self.db.flush()
        logger.info(f"Plan updated for user {user.email}: {plan}")
        return True

    async def suspend_user(self, user_id: str, reason: str = None) -> bool:
        """Suspend user account."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.status = UserStatus.SUSPENDED
        user.suspension_reason = reason
        await self.db.flush()
        logger.warning(f"User suspended: {user.email} - {reason}")
        return True

    async def verify_email(self, user_id: str) -> bool:
        """Mark email as verified."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.email_verified = True
        await self.db.flush()
        return True

    async def update_risk_score(self, user_id: str, risk_score: float) -> bool:
        """Update user risk score."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.risk_score = risk_score
        user.is_risky = risk_score > 0.7  # Configurable threshold
        await self.db.flush()
        return True