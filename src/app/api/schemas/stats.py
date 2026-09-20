from pydantic import BaseModel


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
