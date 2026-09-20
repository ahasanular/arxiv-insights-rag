import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class TimeSeriesPoint(BaseModel):
    period: str
    count: int


class TopCategory(BaseModel):
    code: str
    label: str | None
    count: int
    share_pct: float


class TopAuthor(BaseModel):
    display_name: str
    normalized_name: str
    count: int


class AuthorsPerPaperStats(BaseModel):
    avg: float
    median: int
    p90: int
    histogram: dict[str, int]


class CorpusSummary(BaseModel):
    total_papers: int
    total_authors: int
    total_categories: int
    min_date: str | None
    max_date: str | None
    embedding_coverage_pct: float
    last_ingest: str | None


class StatsMeta(BaseModel):
    """Standard metadata envelope for all stats responses."""

    generated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC))
    total: int | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class StatsEnvelope(BaseModel, Generic[T]):
    """Generic response wrapper for stats endpoints: {data, meta}."""

    data: T
    meta: StatsMeta


class VisualizationResponse(BaseModel):
    """Aggregate response containing data for all dashboard charts."""

    summary: CorpusSummary
    papers_over_time: list[TimeSeriesPoint]
    top_categories: list[TopCategory]
    top_authors: list[TopAuthor]
