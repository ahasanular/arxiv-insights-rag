import time
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.rag import RagRepository
from app.db.session import async_session_maker
from app.services.embedder import EmbedderService

logger = structlog.get_logger(__name__)


class EvaluationService:
    def __init__(self, embedder: EmbedderService):
        self.embedder = embedder

    async def _get_random_papers(
        self, session: AsyncSession, limit: int = 100
    ) -> list[dict[str, Any]]:
        # Fetch some random papers that actually exist in the DB to form the golden set
        sql = """
            SELECT id, arxiv_id, title, abstract 
            FROM papers 
            WHERE title IS NOT NULL AND abstract IS NOT NULL
            ORDER BY RANDOM() 
            LIMIT :limit
        """
        result = await session.execute(text(sql), {"limit": limit})
        rows = result.fetchall()
        return [
            {"id": r.id, "arxiv_id": r.arxiv_id, "title": r.title, "abstract": r.abstract}
            for r in rows
        ]

    async def _generate_golden_set(
        self, session: AsyncSession, papers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Creates a golden set dynamically based on real papers.
        Mixes in out-of-corpus questions, verifying they actually don't exist in the DB.
        """
        golden_set = []

        # 1. In-corpus (Answerable)
        for p in papers:
            golden_set.append(
                {
                    "question": p["title"],
                    "expected_arxiv_id": p["arxiv_id"],
                    "should_abstain": False,  # In-corpus: we expect the system to answer
                }
            )

        # 2. Out-of-corpus (Deliberately unanswerable)
        # Expanded to include tricky, domain-adjacent, and completely irrelevant questions
        candidate_out_of_corpus = [
            # Trivial/Irrelevant
            "How do I bake a chocolate cake?",
            "What is the capital of France?",
            "What are the rules of competitive underwater basket weaving?",
            "What is the weather like in Tokyo today?",
            "How do I change the oil in a 2012 Honda Civic?",
            
            # Domain-adjacent but out-of-corpus (assuming cs.*)
            "What is the mechanism of action of penicillin in treating bacterial infections?",
            "How did the fall of the Roman Empire affect medieval trade routes?",
            "Explain the process of photosynthesis in C4 plants.",
            "What are the key differences between Keynesian and Austrian economics?",
            "How does quantum tunneling affect the half-life of radioactive isotopes?",
            
            # Tricky/Adversarial (sounds like CS/ML but is nonsense or explicitly unsupported)
            "What is the optimal hyperparameter setting for baking a cake using neural networks?",
            "Who won the Super Bowl in the year 2045?",
            "Can you write a poem about artificial intelligence?",
            "Why is the time complexity of a unicorn O(N log N)?",
            "What does the arXiv say about the best way to cook an egg?"
        ]

        # Verify these don't accidentally exist in the DB
        verified_out_of_corpus = []
        for q in candidate_out_of_corpus:
            # Simple FTS check to ensure no paper matches the core nouns
            sql = """
            SELECT 1 FROM papers 
            WHERE to_tsvector('english', title || ' ' || abstract) @@ plainto_tsquery('english', :q)
            LIMIT 1
            """
            result = await session.execute(text(sql), {"q": q})
            if not result.scalar():
                verified_out_of_corpus.append(q)

        # Fallback if somehow all of them matched real papers
        if not verified_out_of_corpus:
            import uuid

            verified_out_of_corpus.append(f"What is the scientific significance of {uuid.uuid4()}?")

        for q in verified_out_of_corpus:
            golden_set.append({"question": q, "expected_arxiv_id": None, "should_abstain": True})

        return golden_set

    async def run_evaluation(self, tau: float = 0.5, samples: int = 100) -> dict[str, Any]:
        """
        Runs the RAG evaluation harness and calculates metrics.
        """
        metrics: dict[str, Any] = {
            "tau": tau,
            "samples": samples,
            "total_questions": 0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "abstention_precision": 0.0,
            "avg_latency_ms": 0.0,
        }

        async with async_session_maker() as session:
            rag_repo = RagRepository(session)

            papers = await self._get_random_papers(session, limit=samples)
            if not papers:
                logger.error("No papers found in database to evaluate against.")
                return metrics

            golden_set = await self._generate_golden_set(session, papers)
            metrics["total_questions"] = len(golden_set)

            hits_at_5 = 0
            reciprocal_ranks = []
            correct_abstentions = 0
            total_abstention_cases = 0

            total_time: float = 0.0

            for item in golden_set:
                question = item["question"]
                expected_id = item["expected_arxiv_id"]
                expected_abstain = item["should_abstain"]

                if expected_abstain:
                    total_abstention_cases += 1

                t0 = time.time()
                query_vector = self.embedder.embed_texts([question])[0]

                docs, should_abstain = await rag_repo.hybrid_search(
                    query_text=question, query_vector=query_vector, limit=50, tau=tau
                )
                total_time += time.time() - t0

                # Check abstention
                if expected_abstain and should_abstain:
                    correct_abstentions += 1
                elif not expected_abstain and should_abstain:
                    # False negative (abstained when it shouldn't have)
                    logger.warning(
                        f"Failed to answer in-corpus question: '{question}'. Top result score: {docs[0]['score'] if docs else 0}"
                    )
                elif expected_abstain and not should_abstain:
                    # False positive (didn't abstain when it should have)
                    logger.warning(
                        f"Failed to abstain on out-of-corpus question: '{question}'. Top result score: {docs[0]['score'] if docs else 0}"
                    )

                if not expected_abstain:
                    # Check retrieval metrics
                    rank = -1
                    for idx, d in enumerate(docs):
                        if d["arxiv_id"] == expected_id:
                            rank = idx + 1
                            break

                    if rank != -1:
                        if rank <= 5:
                            hits_at_5 += 1
                        reciprocal_ranks.append(1.0 / rank)
                    else:
                        reciprocal_ranks.append(0.0)

            # Calculate final metrics
            answerable_count = len(golden_set) - total_abstention_cases
            if answerable_count > 0:
                metrics["recall_at_5"] = round(hits_at_5 / answerable_count, 4)
                metrics["mrr"] = round(sum(reciprocal_ranks) / answerable_count, 4)

            if total_abstention_cases > 0:
                metrics["abstention_precision"] = round(
                    correct_abstentions / total_abstention_cases, 4
                )

            metrics["avg_latency_ms"] = round((total_time / len(golden_set)) * 1000, 2)
            metrics["in_corpus_questions"] = [
                q["question"] for q in golden_set if not q["should_abstain"]
            ]
            metrics["out_of_corpus_questions"] = [
                q["question"] for q in golden_set if q["should_abstain"]
            ]

        return metrics
