import asyncio
import datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.paper import Paper
from app.db.repositories.paper import PaperRepository
from app.main import app


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
@patch("app.db.repositories.rag.RagRepository.hybrid_search")
async def test_rag_rate_limit(mock_hybrid, async_client):
    """Test that the 5/minute rate limit is enforced."""
    # Mocking hybrid search to avoid hitting the LLM and burning tokens
    mock_hybrid.return_value = ([], True)

    # We fire 6 sequential requests to ensure rate limit triggers.
    statuses = []
    for _ in range(6):
        response = await async_client.post(
            "/api/v1/ask", json={"question": "What is AI?"}
        )
        statuses.append(response.status_code)

    assert 429 in statuses, "Expected at least one request to be rate limited (429)"


@pytest.mark.asyncio
async def test_concurrent_db_writes(engine):
    """Simulate many concurrent upserts to test DB pool and locks."""
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def upsert_paper(idx):
        paper_data = {
            "arxiv_id": f"stress.{idx:05d}",
            "version": 1,
            "title": f"Stress Paper {idx}",
            "abstract_raw": "Abstract",
            "abstract": "Abstract",
            "published_at": datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
            "updated_at_source": datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
            "doi": None,
            "journal_ref": None,
            "comment": None,
            "primary_category_id": None,
            "content_hash": f"hash{idx}",
            "abs_url": "http://example.com",
            "pdf_url": "http://example.com",
        }
        async with async_session() as session:
            repo = PaperRepository(session)
            await repo.upsert_paper(paper_data, [], [])
            await session.commit()

    # 50 concurrent writes
    tasks = [upsert_paper(i) for i in range(50)]
    await asyncio.gather(*tasks)

    # Verify they were inserted
    async with async_session() as session:
        result = await session.execute(
            select(Paper).where(Paper.arxiv_id.like("stress.%"))
        )
        inserted_papers = result.scalars().all()
        assert len(inserted_papers) == 50
