import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.limiter import limiter
from app.api.schemas.stats import (
    AuthorsPerPaperStats,
    CorpusSummary,
    StatsEnvelope,
    StatsMeta,
    TimeSeriesPoint,
    TopAuthor,
    TopCategory,
    VisualizationResponse,
)
from app.db.repositories.stats import StatsRepository
from app.db.session import get_db_session
from app.services.stats import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


from app.core.redis import get_redis_client
from redis.asyncio import Redis

def get_stats_service(
    session: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
) -> StatsService:
    repo = StatsRepository(session)
    return StatsService(repo, redis_client)


@router.get("/visualization", response_model=StatsEnvelope[VisualizationResponse])
@limiter.limit("60/minute")
async def visualization(
    request: Request,
    service: StatsService = Depends(get_stats_service),
):
    data = await service.get_visualization()
    return StatsEnvelope(
        data=data,
        meta=StatsMeta(),
    )


@router.get("/authors-per-paper", response_model=StatsEnvelope[AuthorsPerPaperStats])
@limiter.limit("60/minute")
async def authors_per_paper(
    request: Request,
    category: Annotated[str | None, Query()] = None,
    service: StatsService = Depends(get_stats_service),
):
    data = await service.get_authors_per_paper(category=category)
    return StatsEnvelope(
        data=data,
        meta=StatsMeta(filters={"category": category}),
    )


@router.get("/summary", response_model=StatsEnvelope[CorpusSummary])
@limiter.limit("60/minute")
async def summary(
    request: Request,
    service: StatsService = Depends(get_stats_service),
):
    data = await service.get_summary()
    return StatsEnvelope(
        data=data,
        meta=StatsMeta(),
    )
