from fastapi import APIRouter

from app.api.routers import papers, rag, stats

api_router = APIRouter()
api_router.include_router(papers.router)
api_router.include_router(stats.router)
api_router.include_router(rag.router, tags=["rag"])

health_router = APIRouter()


@health_router.get("/healthz", status_code=200)
async def healthz() -> dict[str, str]:
    """
    Liveness probe.
    """
    return {"status": "ok"}


@health_router.get("/readyz", status_code=200)
async def readyz() -> dict[str, str]:
    """
    Readiness probe.
    Will be updated to check DB connection and embedder initialization.
    """
    return {"status": "ready"}
