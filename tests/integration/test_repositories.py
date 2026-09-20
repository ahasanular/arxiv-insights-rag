import pytest
import uuid
import datetime
from app.db.repositories.paper import PaperRepository
from app.db.models.paper import Paper
from sqlalchemy import select

@pytest.mark.asyncio
async def test_upsert_paper_idempotency(db_session):
    repo = PaperRepository(db_session)
    
    # 1. Insert a new paper
    paper_data = {
        "arxiv_id": "2401.00001",
        "version": 1,
        "title": "Initial Title",
        "abstract_raw": "Raw abstract",
        "abstract": "Clean abstract",
        "published_at": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        "updated_at_source": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        "doi": None,
        "journal_ref": None,
        "comment": None,
        "primary_category_id": None,
        "content_hash": "hash1",
        "abs_url": "http://example.com/abs",
        "pdf_url": "http://example.com/pdf",
    }
    
    paper_id, status, hash_changed = await repo.upsert_paper(paper_data, [], [])
    assert status == "inserted"
    assert hash_changed is True
    
    # 2. Upsert the exact same paper (same hash)
    # The updated_at_source and version haven't changed, content_hash hasn't changed
    paper_id2, status2, hash_changed2 = await repo.upsert_paper(paper_data, [], [])
    assert status2 == "unchanged"
    assert hash_changed2 is False
    assert paper_id2 == paper_id
    
    # 3. Upsert a modified paper (changed hash)
    paper_data["title"] = "Modified Title"
    paper_data["content_hash"] = "hash2"
    paper_data["updated_at_source"] = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
    
    paper_id3, status3, hash_changed3 = await repo.upsert_paper(paper_data, [], [])
    assert status3 == "updated"
    assert hash_changed3 is True
    assert paper_id3 == paper_id
    
    # Verify in DB
    result = await db_session.execute(select(Paper).where(Paper.arxiv_id == "2401.00001"))
    db_paper = result.scalar_one()
    assert db_paper.title == "Modified Title"
