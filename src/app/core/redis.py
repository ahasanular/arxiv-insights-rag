from collections.abc import AsyncGenerator

import structlog
from redis.asyncio import Redis

from app.core.settings import settings

logger = structlog.get_logger(__name__)


# Global Redis connection pool
redis_client: Redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5.0,
    health_check_interval=30,
)


async def get_redis_client() -> AsyncGenerator[Redis]:
    """Dependency to inject the global Redis client."""
    yield redis_client
