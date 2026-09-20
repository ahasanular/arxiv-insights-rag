import structlog
from fastapi import APIRouter

from app.api.routers import papers, rag, stats
from app.db.session import async_session_maker

logger = structlog.get_logger(__name__)

api_router = APIRouter()
api_router.include_router(papers.router)
api_router.include_router(stats.router)
api_router.include_router(rag.router, tags=["rag"])

health_router = APIRouter()


@health_router.get("/healthz", status_code=200)
async def healthz() -> dict[str, str]:
    """
    Liveness probe — confirms the process is running.
    """
    return {"status": "ok"}


@health_router.get("/readyz", status_code=200)
async def readyz() -> dict[str, str | bool]:
    """
    Readiness probe — verifies the application can serve traffic by checking:
    1. Database connectivity (SELECT 1)
    2. Alembic migration state (current revision)

    Returns 503 if any check fails so orchestrators (Docker, K8s) know
    not to route traffic to this instance yet.
    """
    from fastapi.responses import JSONResponse
    from sqlalchemy import text

    checks: dict[str, str | bool] = {}

    # 1. Database connectivity
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = "connected"

            # 2. Check that migrations have been applied
            result = await session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.scalar_one_or_none()
            checks["migration"] = row if row else "no_migration_found"
    except Exception as exc:
        logger.error("Readiness check failed", error=str(exc))
        checks["database"] = "unavailable"
        checks["migration"] = "unknown"
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks},
        )

    checks["status"] = "ready"
    return checks
