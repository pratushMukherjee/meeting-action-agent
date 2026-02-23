"""Redis-backed rate limiter for per-user and per-session limits."""

from __future__ import annotations

import time

import redis.asyncio as redis

from src.core.config import settings
from src.core.exceptions import RateLimitExceeded
from src.core.logging import get_logger
from src.core.metrics import GUARDRAIL_VIOLATIONS

logger = get_logger(__name__)

# Rate limit defaults
DEFAULT_REQUESTS_PER_MINUTE = 10
DEFAULT_REQUESTS_PER_HOUR = 100


class RateLimiter:
    """Token bucket rate limiter backed by Redis."""

    def __init__(
        self,
        redis_url: str | None = None,
        requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        requests_per_hour: int = DEFAULT_REQUESTS_PER_HOUR,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def check_rate_limit(self, user_id: str) -> None:
        """Check if a user has exceeded their rate limit.

        Raises RateLimitExceeded if the limit is hit.
        """
        client = await self._get_client()
        now = time.time()

        # Check per-minute limit
        minute_key = f"ratelimit:{user_id}:minute"
        minute_count = await client.get(minute_key)

        if minute_count and int(minute_count) >= self.requests_per_minute:
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="rate_limit_minute").inc()
            logger.warning("rate_limit_exceeded", user_id=user_id, window="minute")
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
            )

        # Check per-hour limit
        hour_key = f"ratelimit:{user_id}:hour"
        hour_count = await client.get(hour_key)

        if hour_count and int(hour_count) >= self.requests_per_hour:
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="rate_limit_hour").inc()
            logger.warning("rate_limit_exceeded", user_id=user_id, window="hour")
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self.requests_per_hour} requests per hour"
            )

        # Increment counters
        pipe = client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        await pipe.execute()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
