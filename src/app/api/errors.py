import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handles SlowAPI RateLimitExceeded and maps it to our standardized error envelope.
    """
    logger.warning(
        "Rate limit exceeded",
        client=request.client.host if request.client else "unknown",
        path=request.url.path,
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "TOO_MANY_REQUESTS",
                "message": "Rate limit exceeded. Please try again later.",
                "details": str(exc.detail),
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Transforms Pydantic validation errors into our standardized envelope.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request data was invalid.",
                "details": exc.errors(),
            }
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Standard HTTP exceptions (404, 401, etc.)
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": None}},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled 500 exceptions.
    """
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": None,
            }
        },
    )
