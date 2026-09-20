import datetime
import uuid

import pytest

from app.db.models.author import Author
from app.db.models.category import Category
from app.db.models.paper import Paper, PaperAuthor
from app.db.repositories.stats import StatsRepository


@pytest.mark.asyncio
async def test_authors_per_paper(db_session):
    # Seed data
    cat1 = Category(id=uuid.uuid4(), code="cs.AI", label="Artificial Intelligence")
    author1 = Author(id=uuid.uuid4(), display_name="Alice", normalized_name="alice")
    author2 = Author(id=uuid.uuid4(), display_name="Bob", normalized_name="bob")

    paper1 = Paper(
        id=uuid.uuid4(),
        arxiv_id="1",
        version=1,
        title="P1",
        abstract_raw="A",
        abstract="A",
        published_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        content_hash="h1",
        abs_url="url1",
        pdf_url="url1",
    )
    paper2 = Paper(
        id=uuid.uuid4(),
        arxiv_id="2",
        version=1,
        title="P2",
        abstract_raw="A",
        abstract="A",
        published_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        content_hash="h2",
        abs_url="url2",
        pdf_url="url2",
    )

    db_session.add_all([cat1, author1, author2, paper1, paper2])
    await db_session.commit()

    # Paper 1 has 1 author
    db_session.add(PaperAuthor(paper_id=paper1.id, author_id=author1.id, position=1))
    # Paper 2 has 2 authors
    db_session.add(PaperAuthor(paper_id=paper2.id, author_id=author1.id, position=1))
    db_session.add(PaperAuthor(paper_id=paper2.id, author_id=author2.id, position=2))

    await db_session.commit()

    repo = StatsRepository(db_session)
    stats = await repo.get_authors_per_paper()

    assert stats["avg"] == 1.5
    assert stats["median"] == 1
    assert stats["histogram"] == {"1": 1, "2": 1}


@pytest.mark.asyncio
async def test_papers_over_time(db_session):
    # Seed papers in different months
    p1 = Paper(
        id=uuid.uuid4(),
        arxiv_id="3",
        version=1,
        title="T",
        abstract_raw="A",
        abstract="A",
        content_hash="3",
        published_at=datetime.datetime(2024, 1, 15, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2024, 1, 15, tzinfo=datetime.UTC),
        abs_url="u3",
        pdf_url="u3",
    )
    p2 = Paper(
        id=uuid.uuid4(),
        arxiv_id="4",
        version=1,
        title="T",
        abstract_raw="A",
        abstract="A",
        content_hash="4",
        published_at=datetime.datetime(2024, 1, 20, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2024, 1, 20, tzinfo=datetime.UTC),
        abs_url="u4",
        pdf_url="u4",
    )
    p3 = Paper(
        id=uuid.uuid4(),
        arxiv_id="5",
        version=1,
        title="T",
        abstract_raw="A",
        abstract="A",
        content_hash="5",
        published_at=datetime.datetime(2024, 2, 5, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2024, 2, 5, tzinfo=datetime.UTC),
        abs_url="u5",
        pdf_url="u5",
    )

    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    repo = StatsRepository(db_session)
    points = await repo.get_papers_over_time(granularity="month")

    assert len(points) == 2

    # Sort just in case, but they should be ordered
    points.sort(key=lambda x: x["period"])

    assert points[0]["period"].startswith("2024-01-01")
    assert points[0]["count"] == 2

    assert points[1]["period"].startswith("2024-02-01")
    assert points[1]["count"] == 1
