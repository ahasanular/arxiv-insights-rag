import structlog
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.settings import settings

logger = structlog.get_logger(__name__)


def get_real_ip(request: Request) -> str:
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    """
    Build the rate limiter. Attempts to connect to Redis for distributed
    rate limiting. If Redis is unavailable, falls back to in-memory storage
    with a clear warning so the operator knows immediately.
    """
    redis_url = settings.REDIS_URL

    try:
        from limits.storage import RedisStorage

        storage = RedisStorage(redis_url)
        # Verify the connection is alive — fail fast instead of silently
        storage.check()
        logger.info("Rate limiter connected to Redis", redis_url=redis_url)
        return Limiter(
            key_func=get_real_ip,
            storage_uri=redis_url,
            default_limits=["1000/day"],
        )
    except Exception as exc:
        logger.warning(
            "Redis unavailable for rate limiter — falling back to in-memory storage. "
            "Rate limits will NOT be shared across workers.",
            redis_url=redis_url,
            error=str(exc),
        )
        return Limiter(
            key_func=get_real_ip,
            storage_uri="memory://",
            default_limits=["1000/day"],
        )


limiter = _build_limiter()
