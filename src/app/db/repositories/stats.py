import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.author import Author
from app.db.models.category import Category
from app.db.models.embedding import PaperEmbedding
from app.db.models.ingest_run import IngestRun
from app.db.models.paper import Paper, PaperAuthor, PaperCategory


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_papers_over_time(
        self,
        granularity: str = "month",
        category: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Counts papers per period.
        """
        # Valid granularity for date_trunc
        valid_granularity = {"month": "month", "year": "year"}.get(granularity, "month")

        # We use date_trunc on published_at
        date_col = func.date_trunc(valid_granularity, Paper.published_at).label("period")

        stmt = select(date_col, func.count(Paper.id).label("count"))

        if category:
            stmt = stmt.join(PaperCategory, Paper.id == PaperCategory.paper_id)
            stmt = stmt.join(Category, PaperCategory.category_id == Category.id)
            stmt = stmt.where(Category.code == category)

        if start_date:
            stmt = stmt.where(Paper.published_at >= start_date)
        if end_date:
            stmt = stmt.where(Paper.published_at <= end_date)

        stmt = stmt.group_by(date_col).order_by(date_col)

        result = await self.session.execute(stmt)
        return [
            {"period": row.period.isoformat() if row.period else None, "count": row.count}
            for row in result.all()
        ]

    async def get_top_categories(
        self,
        limit: int = 10,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Top N categories by paper count + share %.
        """
        # 1. Get total papers in range for percentage calculation
        total_stmt = select(func.count(Paper.id))
        if start_date:
            total_stmt = total_stmt.where(Paper.published_at >= start_date)
        if end_date:
            total_stmt = total_stmt.where(Paper.published_at <= end_date)

        total_papers = await self.session.scalar(total_stmt) or 1  # prevent div by zero

        # 2. Get top categories
        stmt = select(
            Category.code, Category.label, func.count(PaperCategory.paper_id).label("count")
        ).join(PaperCategory, Category.id == PaperCategory.category_id)

        if start_date or end_date:
            stmt = stmt.join(Paper, PaperCategory.paper_id == Paper.id)
            if start_date:
                stmt = stmt.where(Paper.published_at >= start_date)
            if end_date:
                stmt = stmt.where(Paper.published_at <= end_date)

        stmt = (
            stmt.group_by(Category.code, Category.label)
            .order_by(func.count(PaperCategory.paper_id).desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)

        return [
            {
                "code": row.code,
                "label": row.label,
                "count": row._mapping["count"],
                "share_pct": round((row._mapping["count"] / total_papers) * 100, 2),
            }
            for row in result.all()
        ]

    async def get_top_authors(
        self,
        limit: int = 10,
        category: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Top N authors by paper count.
        """
        stmt = select(
            Author.display_name,
            Author.normalized_name,
            func.count(PaperAuthor.paper_id).label("count"),
        ).join(PaperAuthor, Author.id == PaperAuthor.author_id)

        if category or start_date or end_date:
            stmt = stmt.join(Paper, PaperAuthor.paper_id == Paper.id)

            if category:
                # We need to join PaperCategory to filter by category
                stmt = stmt.join(PaperCategory, Paper.id == PaperCategory.paper_id)
                stmt = stmt.join(Category, PaperCategory.category_id == Category.id)
                stmt = stmt.where(Category.code == category)

            if start_date:
                stmt = stmt.where(Paper.published_at >= start_date)
            if end_date:
                stmt = stmt.where(Paper.published_at <= end_date)

        stmt = (
            stmt.group_by(Author.display_name, Author.normalized_name)
            .order_by(func.count(PaperAuthor.paper_id).desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return [
            {
                "display_name": row.display_name,
                "normalized_name": row.normalized_name,
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_authors_per_paper(
        self,
        category: str | None = None,
    ) -> dict[str, Any]:
        """
        Avg, median, p90 + histogram buckets of authors per paper.
        """
        # CTE to count authors per paper
        subq = select(PaperAuthor.paper_id, func.count(PaperAuthor.author_id).label("author_count"))

        if category:
            subq = subq.join(PaperCategory, PaperAuthor.paper_id == PaperCategory.paper_id)
            subq = subq.join(Category, PaperCategory.category_id == Category.id)
            subq = subq.where(Category.code == category)

        cte_subq = subq.group_by(PaperAuthor.paper_id).cte("author_counts")

        # Calculate stats (avg, median, p90)
        stats_stmt = select(
            func.avg(cte_subq.c.author_count).label("avg"),
            func.percentile_cont(0.5).within_group(cte_subq.c.author_count.asc()).label("median"),
            func.percentile_cont(0.9).within_group(cte_subq.c.author_count.asc()).label("p90"),
        )
        stats_row = await self.session.execute(stats_stmt)
        stats = stats_row.one_or_none()

        if not stats or stats.avg is None:
            return {"avg": 0, "median": 0, "p90": 0, "histogram": {}}

        # Histogram buckets using width_bucket
        # Let's bucketize up to 20 authors.
        hist_stmt = (
            select(
                func.width_bucket(cte_subq.c.author_count, 1, 21, 20).label("bucket"),
                func.count().label("freq"),
            )
            .group_by("bucket")
            .order_by("bucket")
        )

        hist_result = await self.session.execute(hist_stmt)
        histogram = {str(row.bucket): row.freq for row in hist_result.all()}

        return {
            "avg": round(float(stats.avg), 2),
            "median": int(stats.median) if stats.median is not None else 0,
            "p90": int(stats.p90) if stats.p90 is not None else 0,
            "histogram": histogram,
        }

    async def get_summary(self) -> dict[str, Any]:
        """
        Corpus card: totals, distinct authors/categories, date range, embedding coverage %, last ingest
        """
        total_papers = await self.session.scalar(select(func.count(Paper.id))) or 0
        total_authors = await self.session.scalar(select(func.count(Author.id))) or 0
        total_categories = await self.session.scalar(select(func.count(Category.id))) or 0

        dates_row = await self.session.execute(
            select(
                func.min(Paper.published_at).label("min_date"),
                func.max(Paper.published_at).label("max_date"),
            )
        )
        dates = dates_row.one_or_none()

        # Calculate embedding coverage (approximate by checking distinct paper_ids in embeddings)
        embedded_papers = (
            await self.session.scalar(select(func.count(func.distinct(PaperEmbedding.paper_id))))
            or 0
        )

        coverage_pct = round((embedded_papers / total_papers * 100), 2) if total_papers > 0 else 0.0

        last_run_row = await self.session.execute(
            select(IngestRun.finished_at)
            .where(IngestRun.status == "completed")
            .order_by(IngestRun.finished_at.desc())
            .limit(1)
        )
        last_run = last_run_row.scalar_one_or_none()

        return {
            "total_papers": total_papers,
            "total_authors": total_authors,
            "total_categories": total_categories,
            "min_date": dates.min_date.isoformat() if dates and dates.min_date else None,
            "max_date": dates.max_date.isoformat() if dates and dates.max_date else None,
            "embedding_coverage_pct": coverage_pct,
            "last_ingest": last_run.isoformat() if last_run else None,
        }
