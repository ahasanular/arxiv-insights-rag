import asyncio
import datetime

from cachetools import TTLCache

from app.api.schemas.stats import (
    AuthorsPerPaperStats,
    CorpusSummary,
    TimeSeriesPoint,
    TopAuthor,
    TopCategory,
)
from app.db.repositories.stats import StatsRepository

# Global TTL cache for stats (5 minutes)
_stats_cache = TTLCache(maxsize=100, ttl=300)
_cache_lock = asyncio.Lock()


class StatsService:
    def __init__(self, stats_repo: StatsRepository):
        self.stats_repo = stats_repo

    async def _get_cached_or_fetch(self, cache_key: str, fetch_func):
        # Very simple async read-through cache
        if cache_key in _stats_cache:
            return _stats_cache[cache_key]

        async with _cache_lock:
            # Double check inside lock
            if cache_key in _stats_cache:
                return _stats_cache[cache_key]

            result = await fetch_func()
            _stats_cache[cache_key] = result
            return result

    async def get_papers_over_time(
        self,
        granularity: str = "month",
        category: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[TimeSeriesPoint]:
        cache_key = f"papers_time:{granularity}:{category}:{start_date}:{end_date}"

        async def _fetch():
            data = await self.stats_repo.get_papers_over_time(
                granularity, category, start_date, end_date
            )
            return [TimeSeriesPoint(**d) for d in data]

        return await self._get_cached_or_fetch(cache_key, _fetch)

    async def get_top_categories(
        self,
        limit: int = 10,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[TopCategory]:
        cache_key = f"top_cats:{limit}:{start_date}:{end_date}"

        async def _fetch():
            data = await self.stats_repo.get_top_categories(limit, start_date, end_date)
            return [TopCategory(**d) for d in data]

        return await self._get_cached_or_fetch(cache_key, _fetch)

    async def get_top_authors(
        self,
        limit: int = 10,
        category: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[TopAuthor]:
        cache_key = f"top_authors:{limit}:{category}:{start_date}:{end_date}"

        async def _fetch():
            data = await self.stats_repo.get_top_authors(limit, category, start_date, end_date)
            return [TopAuthor(**d) for d in data]

        return await self._get_cached_or_fetch(cache_key, _fetch)

    async def get_authors_per_paper(
        self,
        category: str | None = None,
    ) -> AuthorsPerPaperStats:
        cache_key = f"authors_stats:{category}"

        async def _fetch():
            data = await self.stats_repo.get_authors_per_paper(category)
            return AuthorsPerPaperStats(**data)

        return await self._get_cached_or_fetch(cache_key, _fetch)

    async def get_summary(self) -> CorpusSummary:
        cache_key = "summary"

        async def _fetch():
            data = await self.stats_repo.get_summary()
            return CorpusSummary(**data)

        return await self._get_cached_or_fetch(cache_key, _fetch)
