import logging
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection."""
    global _redis_client
    _redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connection established")


async def close_redis():
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        logger.info("Redis connection closed")


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    if _redis_client is None:
        await init_redis()
    return _redis_client


class RateLimiter:
    """Rate limiter using Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        limit: int,
        period: int,
    ) -> bool:
        """Check if request is allowed (sliding window)."""
        if not settings.RATE_LIMIT_ENABLED:
            return True

        try:
            current_time = datetime.utcnow().timestamp()
            window_start = current_time - period

            # Remove old entries
            await self.redis.zremrangebyscore(key, 0, window_start)

            # Count current requests
            count = await self.redis.zcard(key)

            if count >= limit:
                return False

            # Add current request
            await self.redis.zadd(key, {str(current_time): current_time})
            await self.redis.expire(key, period + 1)

            return True
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if Redis fails
            return True

    async def get_remaining(
        self,
        key: str,
        limit: int,
        period: int,
    ) -> int:
        """Get remaining requests in current window."""
        try:
            current_time = datetime.utcnow().timestamp()
            window_start = current_time - period

            await self.redis.zremrangebyscore(key, 0, window_start)
            count = await self.redis.zcard(key)

            return max(0, limit - count)
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return limit


async def check_rate_limit(
    user_id: str,
    limit: int = settings.RATE_LIMIT_REQUESTS,
    period: int = settings.RATE_LIMIT_PERIOD_SECONDS,
) -> tuple[bool, int]:
    """Check rate limit for user."""
    redis = await get_redis()
    limiter = RateLimiter(redis)

    key = f"ratelimit:user:{user_id}"
    allowed = await limiter.is_allowed(key, limit, period)
    remaining = await limiter.get_remaining(key, limit, period)

    return allowed, remaining


async def check_ip_rate_limit(
    ip: str,
    limit: int = 1000,
    period: int = 3600,
) -> tuple[bool, int]:
    """Check rate limit for IP address."""
    redis = await get_redis()
    limiter = RateLimiter(redis)

    key = f"ratelimit:ip:{ip}"
    allowed = await limiter.is_allowed(key, limit, period)
    remaining = await limiter.get_remaining(key, limit, period)

    return allowed, remaining