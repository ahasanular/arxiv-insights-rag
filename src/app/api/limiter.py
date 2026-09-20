from fastapi import Request
from limits.storage import RedisStorage
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.settings import settings


def get_real_ip(request: Request) -> str:
    return get_remote_address(request)


storage = RedisStorage(settings.REDIS_URL)

limiter = Limiter(
    key_func=get_real_ip,
    storage_uri=settings.REDIS_URL,
    default_limits=["1000/day"],
)
