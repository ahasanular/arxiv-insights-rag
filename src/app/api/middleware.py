import time

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

from collections.abc import Awaitable, Callable

from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()

        # Process the request
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            logger.info(
                "Request processed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2),
            )
            return response
        except Exception as exc:
            process_time = time.perf_counter() - start_time
            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                duration_ms=round(process_time * 1000, 2),
                exc_info=exc,
            )
            raise
