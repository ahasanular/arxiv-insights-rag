import asyncio
import datetime
import json
from typing import Any

import structlog
from redis.asyncio import Redis

from app.api.schemas.stats import (
    AuthorsPerPaperStats,
    CorpusSummary,
    TimeSeriesPoint,
    TopAuthor,
    TopCategory,
    VisualizationResponse,
)
from app.db.repositories.stats import StatsRepository

logger = structlog.get_logger(__name__)


class StatsService:
    def __init__(self, stats_repo: StatsRepository, redis_client: Redis):
        self.stats_repo = stats_repo
        self.redis_client = redis_client
        self.cache_ttl = 300  # 5 minutes

    async def _get_cached_or_fetch(self, cache_key: str, fetch_func, schema_cls):
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                parsed = json.loads(cached_data)
                if isinstance(parsed, list):
                    return [schema_cls(**item) for item in parsed]
                return schema_cls(**parsed)
        except Exception as e:
            logger.warning("Redis cache read failed", cache_key=cache_key, error=str(e))

        # Fetch fresh data
        result = await fetch_func()

        # Cache it
        try:
            if isinstance(result, list):
                dumped = json.dumps([item.model_dump() for item in result])
            else:
                dumped = json.dumps(result.model_dump())
            await self.redis_client.setex(cache_key, self.cache_ttl, dumped)
        except Exception as e:
            logger.warning("Redis cache write failed", cache_key=cache_key, error=str(e))

        return result

    async def get_visualization(self) -> VisualizationResponse:
        """Fetches all visualization data concurrently for the single visualization API."""
        cache_key = "stats:visualization"

        async def _fetch():
            # SQLAlchemy AsyncSession is not thread-safe and does not support concurrent queries.
            # We must await these sequentially.
            summary_data = await self.stats_repo.get_summary()
            papers_data = await self.stats_repo.get_papers_over_time(granularity="month")
            cats_data = await self.stats_repo.get_top_categories(limit=10)
            authors_data = await self.stats_repo.get_top_authors(limit=10)

            return VisualizationResponse(
                summary=CorpusSummary(**summary_data),
                papers_over_time=[TimeSeriesPoint(**d) for d in papers_data],
                top_categories=[TopCategory(**d) for d in cats_data],
                top_authors=[TopAuthor(**d) for d in authors_data],
            )

        return await self._get_cached_or_fetch(cache_key, _fetch, VisualizationResponse)

    async def get_authors_per_paper(
        self,
        category: str | None = None,
    ) -> AuthorsPerPaperStats:
        cache_key = f"stats:authors_stats:{category}"

        async def _fetch():
            data = await self.stats_repo.get_authors_per_paper(category)
            return AuthorsPerPaperStats(**data)

        return await self._get_cached_or_fetch(cache_key, _fetch, AuthorsPerPaperStats)

    async def get_summary(self) -> CorpusSummary:
        cache_key = "stats:summary"

        async def _fetch():
            data = await self.stats_repo.get_summary()
            return CorpusSummary(**data)

        return await self._get_cached_or_fetch(cache_key, _fetch, CorpusSummary)
