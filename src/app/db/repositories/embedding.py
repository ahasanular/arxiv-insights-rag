from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.embedding import PaperEmbedding
from app.db.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[PaperEmbedding]):
    def __init__(self, session: AsyncSession):
        super().__init__(PaperEmbedding, session)

    async def upsert_embeddings(self, data: list[dict]):
        """
        data: list of dicts with keys: paper_id, embedding, model, dimensions, content_hash
        """
        from sqlalchemy.dialects.postgresql import insert
        if not data:
            return
            
        stmt = insert(PaperEmbedding).values(data)
        update_stmt = stmt.on_conflict_do_update(
            index_elements=["paper_id", "chunk_index", "model"],
            set_={
                "embedding": stmt.excluded.embedding,
                "model": stmt.excluded.model,
                "dim": stmt.excluded.dim,
                "content_hash": stmt.excluded.content_hash,
            }
        )
        await self.session.execute(update_stmt)
