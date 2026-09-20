from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    generic_exception_handler,
    http_exception_handler,
    rate_limit_handler,
    validation_exception_handler,
)
from app.api.limiter import limiter
from app.api.middleware import LoggingMiddleware
from app.api.router import api_router, health_router
from app.core.logging import setup_logging
from app.core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Setup logging on startup
    setup_logging()
    logger = structlog.get_logger()
    logger.info("Application starting up", env=settings.ENVIRONMENT)

    yield

    logger.info("Application shutting down")

    # Gracefully close global Redis connection pool
    try:
        from app.core.redis import redis_client
        await redis_client.aclose()
        logger.info("Redis connection pool closed")
    except Exception as e:
        logger.warning("Error closing Redis connection pool", error=str(e))


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # Middlewares
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.state.limiter = limiter

    # Exception Handlers
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # CORS — controlled via CORS_ORIGINS env var (comma-separated or list)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Metrics
    Instrumentator().instrument(app).expose(app)

    # Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Mount UI at root (Catch-all)
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
