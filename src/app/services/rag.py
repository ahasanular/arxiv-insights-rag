import time
import structlog
from typing import Dict, Any

from app.api.schemas.rag import AskRequest, AskResponse, SourceSchema
from app.db.repositories.rag import RagRepository
from app.db.repositories.paper import PaperRepository
from app.services.embedder import EmbedderService
from app.services.llm import LlmService

logger = structlog.get_logger(__name__)


class RagService:
    def __init__(
        self,
        rag_repo: RagRepository,
        paper_repo: PaperRepository,
        embedder: EmbedderService,
        llm: LlmService
    ):
        self.rag_repo = rag_repo
        self.paper_repo = paper_repo
        self.embedder = embedder
        self.llm = llm

    async def ask(self, request: AskRequest) -> AskResponse:
        t0 = time.time()
        
        # 1. Intent Guard
        if self.rag_repo.is_aggregate_intent(request.question):
            return AskResponse(
                answer="This looks like a counting or aggregate question. Please use the /api/v1/stats endpoints for analytics.",
                abstained=True,
                sources=[],
                meta={"strategy": "intent_guard_abstained"}
            )
            
        # 2. Embed Question
        t_embed_start = time.time()
        query_vector = self.embedder.embed_texts([request.question])[0]
        t_embed = time.time() - t_embed_start
        
        # 3. Hybrid Search
        t_ret_start = time.time()
        docs, should_abstain = await self.rag_repo.hybrid_search(
            query_text=request.question,
            query_vector=query_vector,
            limit=50,
            tau=0.5
        )
        t_ret = time.time() - t_ret_start
        
        if should_abstain or not docs:
            return AskResponse(
                answer="I could not find any papers in the database relevant to your question.",
                abstained=True,
                sources=[],
                meta={"strategy": "relevance_gate_abstained"}
            )
            
        # 4. Generate Answer
        t_llm_start = time.time()
        # We only pass top 8 docs to LLM for context limit & noise reduction
        top_docs = docs[:8]
        llm_response, llm_abstained = await self.llm.generate_rag_answer(request.question, top_docs)
        t_llm = time.time() - t_llm_start
        
        # 5. Hydrate Sources with Authors
        # Since hybrid search didn't join authors to avoid group_by explosion, we fetch them here
        used_ids = set(llm_response.used_source_ids) if llm_response.used_source_ids else {d["arxiv_id"] for d in top_docs[:3]}
        
        sources = []
        for d in top_docs:
            if d["arxiv_id"] in used_ids:
                # get_by_arxiv_id joins authors
                paper_obj = await self.paper_repo.get_by_arxiv_id(d["arxiv_id"])
                authors = [a.author.display_name for a in paper_obj.authors] if paper_obj else []
                
                sources.append(
                    SourceSchema(
                        arxiv_id=d["arxiv_id"],
                        title=d["title"],
                        authors=authors,
                        published_at=d["published_at"],
                        score=d["score"],
                        url=f"https://arxiv.org/abs/{d['arxiv_id']}"
                    )
                )

        total_time = time.time() - t0
        meta = {
            "strategy": "hybrid_rrf",
            "retrieval_ms": round(t_ret * 1000, 2),
            "embed_ms": round(t_embed * 1000, 2),
            "llm_ms": round(t_llm * 1000, 2),
            "total_ms": round(total_time * 1000, 2),
            "model": self.llm.model_name if hasattr(self.llm, "model_name") else "litellm"
        }

        return AskResponse(
            answer=llm_response.answer,
            abstained=llm_abstained,
            sources=sources,
            meta=meta
        )
