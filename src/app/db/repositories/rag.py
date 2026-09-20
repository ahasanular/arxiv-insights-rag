import re
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text
from app.db.models.paper import Paper, PaperCategory
from app.db.models.category import Category
from app.db.models.embedding import PaperEmbedding

class RagRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def extract_prefilters(self, question: str) -> Tuple[List[str], List[str]]:
        """
        Extracts years and categories from the question for deterministic filtering.
        Returns: (years, categories)
        """
        years = re.findall(r"\b(19|20)\d{2}\b", question)
        years = list(set(years))  # Deduplicate
        
        categories = re.findall(r"cs\.[a-zA-Z]{2}\b", question, re.IGNORECASE)
        categories = list(set([c.lower() for c in categories]))
        
        return years, categories

    def is_aggregate_intent(self, question: str) -> bool:
        """
        Detects counting or superlative questions that RAG cannot answer reliably.
        """
        q = question.lower()
        if re.search(r"\b(how many|count|number of|top|most|average)\b", q):
            return True
        return False

    async def hybrid_search(
        self, 
        query_text: str, 
        query_vector: List[float], 
        limit: int = 50,
        tau: float = 0.5
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Executes a hybrid search using pgvector (cosine similarity) and ts_rank_cd.
        Combines results using Reciprocal Rank Fusion (RRF).
        Returns:
            - list of documents (dicts)
            - should_abstain (boolean) indicating if the results fell below the relevance gate.
        """
        years, categories = self.extract_prefilters(query_text)
        
        # We will use raw SQL for the RRF query for maximum control and performance,
        # but we use SQLAlchemy text() and bind parameters securely.
        
        sql = """
        WITH vector_search AS (
            SELECT 
                p.id,
                1 - (pe.embedding <=> :query_vector) AS cosine_sim,
                ROW_NUMBER() OVER(ORDER BY pe.embedding <=> :query_vector) as vector_rank
            FROM papers p
            JOIN paper_embeddings pe ON p.id = pe.paper_id
            WHERE 1=1
        """
        
        # Inject deterministic prefilters if present
        if years:
            sql += " AND EXTRACT(YEAR FROM p.published_at) = ANY(:years)"
        if categories:
            sql += """ AND EXISTS (
                SELECT 1 FROM paper_categories pc 
                JOIN categories c ON pc.category_id = c.id 
                WHERE pc.paper_id = p.id AND LOWER(c.code) = ANY(:categories)
            )"""
            
        sql += """
            ORDER BY pe.embedding <=> :query_vector
            LIMIT :limit
        ),
        fts_search AS (
            SELECT 
                p.id,
                ts_rank_cd(
                    to_tsvector('english', p.title || ' ' || p.abstract), 
                    plainto_tsquery('english', :query_text)
                ) AS fts_score,
                ROW_NUMBER() OVER(
                    ORDER BY ts_rank_cd(
                        to_tsvector('english', p.title || ' ' || p.abstract), 
                        plainto_tsquery('english', :query_text)
                    ) DESC
                ) as fts_rank
            FROM papers p
            WHERE 1=1
        """
        
        if years:
            sql += " AND EXTRACT(YEAR FROM p.published_at) = ANY(:years)"
        if categories:
            sql += """ AND EXISTS (
                SELECT 1 FROM paper_categories pc 
                JOIN categories c ON pc.category_id = c.id 
                WHERE pc.paper_id = p.id AND LOWER(c.code) = ANY(:categories)
            )"""
            
        sql += """
            ORDER BY fts_score DESC
            LIMIT :limit
        ),
        rrf AS (
            SELECT 
                COALESCE(v.id, f.id) as paper_id,
                COALESCE(v.cosine_sim, 0.0) as cosine_sim,
                COALESCE(f.fts_score, 0.0) as fts_score,
                (
                    COALESCE(1.0 / (60 + v.vector_rank), 0.0) + 
                    COALESCE(1.0 / (60 + f.fts_rank), 0.0)
                ) AS rrf_score
            FROM vector_search v
            FULL OUTER JOIN fts_search f ON v.id = f.id
        )
        SELECT 
            p.arxiv_id,
            p.title,
            p.abstract,
            p.published_at,
            r.rrf_score,
            r.cosine_sim,
            r.fts_score
        FROM rrf r
        JOIN papers p ON r.paper_id = p.id
        ORDER BY r.rrf_score DESC
        LIMIT 8
        """
        
        params = {
            "query_text": query_text,
            "query_vector": str(query_vector), # pgvector natively casts text '[...]' to vector
            "limit": limit
        }
        if years:
            params["years"] = [int(y) for y in years]
        if categories:
            params["categories"] = categories
            
        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()
        
        # Map to dicts
        docs = []
        best_cosine = 0.0
        best_fts = 0.0
        
        for row in rows:
            if row.cosine_sim > best_cosine:
                best_cosine = row.cosine_sim
            if row.fts_score > best_fts:
                best_fts = row.fts_score
                
            docs.append({
                "arxiv_id": row.arxiv_id,
                "title": row.title,
                "abstract": row.abstract,
                "published_at": row.published_at.isoformat(),
                "score": round(row.rrf_score, 4)
            })
            
        # Relevance Gate (tau check)
        # If the best cosine similarity is worse than tau and FTS is ~0, we abstain.
        should_abstain = False
        if docs:
            if best_cosine < tau and best_fts < 0.01:
                should_abstain = True
        else:
            # No documents retrieved at all
            should_abstain = True
            
        return docs, should_abstain
