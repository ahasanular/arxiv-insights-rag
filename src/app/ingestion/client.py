import asyncio

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.settings import settings

logger = structlog.get_logger(__name__)


class ArxivEmptyFeedError(Exception):
    """Raised when arXiv returns an empty feed unexpectedly."""

    pass


class ArxivClient:
    def __init__(self) -> None:
        self.base_url = settings.ARXIV_API_URL
        self._last_request_time = 0.0
        self._rate_limit = settings.INGESTION_RATE_LIMIT
        self._lock = asyncio.Lock()
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def _throttle(self) -> None:
        """Global async throttle at 1 request / 3.1s."""
        async with self._lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._rate_limit:
                await asyncio.sleep(self._rate_limit - elapsed)
            self._last_request_time = asyncio.get_running_loop().time()

    async def fetch_page(self, search_query: str, start: int = 0, max_results: int = 100) -> str:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }

        # Tenacity retry policy: retry on timeout, 5xx, or empty feed
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, ArxivEmptyFeedError)),
            reraise=True,
        ):
            with attempt:
                await self._throttle()
                logger.info(
                    "Fetching from arXiv", params=params, attempt=attempt.retry_state.attempt_number
                )

                response = await self.client.get(self.base_url, params=params)

                # Handle Retry-After header
                if response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", 30))
                    logger.warning(f"Rate limited by arXiv. Sleeping for {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    response.raise_for_status()

                response.raise_for_status()
                text = response.text

                # Known arXiv quirk: sometimes returns empty feed even for valid queries.
                # If we expect results but get 0 entries (and it's not actually the end of the query),
                # we should retry. An empty feed looks like it has no <entry> tags.
                # Since we page by 100, if start=0 we absolutely expect entries.
                # If we get no <entry> tags, we raise ArxivEmptyFeedError to trigger tenacity.
                # However, this might actually be the end of the results.
                # A safer heuristic: arXiv's "empty" response is often missing opensearch:totalResults or has it as 0.
                if "<entry>" not in text and max_results > 0:
                    # If this is the first page (start=0), an empty feed is almost certainly
                    # a transient arXiv glitch — raise to trigger tenacity retries.
                    # For later pages, an empty feed is the normal end-of-results signal.
                    if start == 0:
                        raise ArxivEmptyFeedError(
                            f"Expected results for '{search_query}' at start={start} "
                            f"but received empty feed (no <entry> tags)."
                        )
                    else:
                        logger.info(
                            "No <entry> tags found — likely end of results",
                            start=start,
                            search_query=search_query,
                        )

                return text

    async def close(self) -> None:
        await self.client.aclose()
