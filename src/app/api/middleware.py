import time
from collections.abc import Awaitable, Callable

import structlog
from asgi_correlation_id import correlation_id
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()

        # Process the request
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time

            # Attach correlation ID as response header for client-side traceability
            request_id = correlation_id.get()
            if request_id:
                response.headers["X-Request-ID"] = request_id

            logger.info(
                "Request processed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2),
                request_id=request_id,
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
