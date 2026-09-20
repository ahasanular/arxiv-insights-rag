import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from app.api.limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.stats import (
    AuthorsPerPaperStats,
    CorpusSummary,
    TimeSeriesPoint,
    TopAuthor,
    TopCategory,
)
from app.db.repositories.stats import StatsRepository
from app.db.session import get_db_session
from app.services.stats import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


def get_stats_service(session: AsyncSession = Depends(get_db_session)) -> StatsService:
    repo = StatsRepository(session)
    return StatsService(repo)


@router.get("/papers-over-time", response_model=list[TimeSeriesPoint])
@limiter.limit("60/minute")
async def papers_over_time(
    request: Request,
    granularity: Annotated[str, Query(pattern="^(month|year)$")] = "month",
    category: Annotated[str | None, Query()] = None,
    start_date: Annotated[datetime.datetime | None, Query(alias="from")] = None,
    end_date: Annotated[datetime.datetime | None, Query(alias="to")] = None,
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_papers_over_time(
        granularity=granularity,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/top-categories", response_model=list[TopCategory])
@limiter.limit("60/minute")
async def top_categories(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    start_date: Annotated[datetime.datetime | None, Query(alias="from")] = None,
    end_date: Annotated[datetime.datetime | None, Query(alias="to")] = None,
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_top_categories(
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/top-authors", response_model=list[TopAuthor])
@limiter.limit("60/minute")
async def top_authors(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    category: Annotated[str | None, Query()] = None,
    start_date: Annotated[datetime.datetime | None, Query(alias="from")] = None,
    end_date: Annotated[datetime.datetime | None, Query(alias="to")] = None,
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_top_authors(
        limit=limit,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/authors-per-paper", response_model=AuthorsPerPaperStats)
@limiter.limit("60/minute")
async def authors_per_paper(
    request: Request,
    category: Annotated[str | None, Query()] = None,
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_authors_per_paper(category=category)


@router.get("/summary", response_model=CorpusSummary)
@limiter.limit("60/minute")
async def summary(
    request: Request,
    service: StatsService = Depends(get_stats_service),
):
    return await service.get_summary()
