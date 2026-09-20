import datetime
import uuid

import pytest

from app.api.schemas.rag import AskRequest
from app.core.settings import settings
from app.db.models.embedding import PaperEmbedding
from app.db.models.paper import Paper
from app.db.repositories.paper import PaperRepository
from app.db.repositories.rag import RagRepository
from app.services.llm import LlmService
from app.services.rag import RagService


class MockEmbedder:
    def __init__(self):
        self.dim = 384
        self.model_name = "mock"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            if "time series" in text.lower():
                # Positive vector for time series concepts
                results.append([0.5] * self.dim)
            elif "france" in text.lower():
                # Opposite vector for unrelated concepts
                results.append([-0.5] * self.dim)
            else:
                # Default vector
                results.append([0.1] * self.dim)
        return results


# We need to pre-seed the database with some papers for the golden set
@pytest.fixture
async def golden_dataset(db_session):
    # Ensure pgvector extension is created
    await db_session.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
    await db_session.commit()

    p1 = Paper(
        id=uuid.uuid4(),
        arxiv_id="1111.22222",
        version=1,
        title="Transformers for Time Series",
        abstract_raw="We propose a transformer model for time series forecasting.",
        abstract="We propose a transformer model for time series forecasting.",
        published_at=datetime.datetime(2023, 5, 1, tzinfo=datetime.UTC),
        updated_at_source=datetime.datetime(2023, 5, 1, tzinfo=datetime.UTC),
        content_hash="h1",
        abs_url="u1",
        pdf_url="u1",
    )

    db_session.add(p1)
    await db_session.commit()

    # Add embedding
    emb1 = PaperEmbedding(
        paper_id=p1.id,
        embedding=[0.5] * 384,  # Matches the MockEmbedder's "time series" vector
        model="mock",
        dim=384,
        chunk_index=0,
        content_hash="h1",
    )
    db_session.add(emb1)
    await db_session.commit()

    yield db_session


@pytest.fixture
def rag_service(golden_dataset):
    # Using LlmService in "none" fallback mode to avoid hitting real APIs in eval
    settings.LLM_PROVIDER = "none"
    llm = LlmService()

    # We patch embedder to our mock to avoid downloading BGE in CI purely for testing DB retrieval
    embedder = MockEmbedder()
    rag_repo = RagRepository(golden_dataset)
    paper_repo = PaperRepository(golden_dataset)

    return RagService(rag_repo, paper_repo, embedder, llm)


@pytest.mark.asyncio
async def test_rag_golden_match(rag_service):
    # "Transformers for Time Series" exists in the golden dataset
    # We expect FTS and Vector to hit it.
    req = AskRequest(question="What is a good model for time series forecasting?")
    resp = await rag_service.ask(req)

    assert resp.abstained is False
    assert len(resp.sources) > 0
    assert resp.sources[0].arxiv_id == "1111.22222"
    assert resp.meta["strategy"] == "hybrid_rrf"


@pytest.mark.asyncio
async def test_rag_intent_guard(rag_service):
    # Counting questions should be immediately rejected by the Intent Guard
    req = AskRequest(question="How many papers were published about transformers?")
    resp = await rag_service.ask(req)

    assert resp.abstained is True
    assert resp.meta["strategy"] == "intent_guard_abstained"
    assert "analytics" in resp.answer.lower() or "stats" in resp.answer.lower()


@pytest.mark.asyncio
async def test_rag_relevance_gate(rag_service):
    # Completely unrelated question.
    # Because 'france' is in the text, our smarter MockEmbedder will return [-0.5]*384
    # which is opposite to the stored [0.5]*384 paper embedding, resulting in cosine sim = -1.0.
    req = AskRequest(question="What is the capital of France?")
    resp = await rag_service.ask(req)

    # Because vector sim is negative (opposite) and FTS fails to match any words,
    # it should trigger the tau=0.5 relevance gate
    assert resp.abstained is True
    assert resp.meta["strategy"] == "relevance_gate_abstained"
