import datetime
import uuid

from sqlalchemy import and_, column, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.author import Author
from app.db.models.category import Category
from app.db.models.paper import Paper, PaperAuthor, PaperCategory
from app.db.repositories.base import BaseRepository


class PaperRepository(BaseRepository[Paper]):
    def __init__(self, session: AsyncSession):
        super().__init__(Paper, session)

    async def upsert_paper(
        self,
        paper_data: dict,
        author_ids: list[uuid.UUID],
        categories_data: list[tuple[uuid.UUID, bool]],
    ) -> tuple[uuid.UUID | None, str, bool]:
        """
        Upserts a paper. Returns a tuple (paper_id, status) where status is one of
        'inserted', 'updated', or 'unchanged'.
        Handles association tables (paper_authors, paper_categories).
        """
        # Prepare data for insert
        # 0. Check existing content hash
        sel = select(Paper.content_hash, Paper.id).where(Paper.arxiv_id == paper_data["arxiv_id"])
        existing_row = await self.session.execute(sel)
        existing_paper = existing_row.one_or_none()

        hash_changed = True
        if existing_paper:
            if existing_paper.content_hash == paper_data["content_hash"]:
                hash_changed = False

        now = datetime.datetime.now(datetime.UTC)

        insert_stmt = insert(Paper).values(
            arxiv_id=paper_data["arxiv_id"],
            version=paper_data["version"],
            title=paper_data["title"],
            abstract_raw=paper_data["abstract_raw"],
            abstract=paper_data["abstract"],
            published_at=paper_data["published_at"],
            updated_at_source=paper_data["updated_at_source"],
            doi=paper_data["doi"],
            journal_ref=paper_data["journal_ref"],
            comment=paper_data["comment"],
            primary_category_id=paper_data.get("primary_category_id"),
            content_hash=paper_data["content_hash"],
            abs_url=paper_data["abs_url"],
            pdf_url=paper_data["pdf_url"],
            last_synced_at=now,
        )

        # The DO UPDATE action checks if the new row is newer or the content changed
        update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["arxiv_id"],
            set_={
                "version": insert_stmt.excluded.version,
                "title": insert_stmt.excluded.title,
                "abstract_raw": insert_stmt.excluded.abstract_raw,
                "abstract": insert_stmt.excluded.abstract,
                "updated_at_source": insert_stmt.excluded.updated_at_source,
                "doi": insert_stmt.excluded.doi,
                "journal_ref": insert_stmt.excluded.journal_ref,
                "comment": insert_stmt.excluded.comment,
                "primary_category_id": insert_stmt.excluded.primary_category_id,
                "content_hash": insert_stmt.excluded.content_hash,
                "pdf_url": insert_stmt.excluded.pdf_url,
                "last_synced_at": insert_stmt.excluded.last_synced_at,
            },
            where=and_(
                Paper.arxiv_id == insert_stmt.excluded.arxiv_id,
                (
                    (insert_stmt.excluded.updated_at_source > Paper.updated_at_source)
                    | (insert_stmt.excluded.content_hash.is_distinct_from(Paper.content_hash))
                    | (insert_stmt.excluded.version > Paper.version)
                ),
            ),
        ).returning(Paper.id, (column("xmax") == 0).label("inserted"))

        result = await self.session.execute(update_stmt)
        row = result.one_or_none()

        # If row is None, it means the ON CONFLICT WHERE condition failed, so it's unchanged.
        if row is None:
            # We still need the paper ID to potentially check related tables,
            # but since it's completely unchanged, we can skip rewriting joins.
            existing_id = existing_paper.id if existing_paper else None
            return existing_id, "unchanged", hash_changed

        paper_id = row.id
        status = "inserted" if row.inserted else "updated"

        # If updated or inserted, we rewrite the join tables completely.
        # Since we use ON DELETE CASCADE for embeddings and we want to preserve them
        # if the hash is the SAME, wait! We don't delete embeddings if hash is the same.
        # The prompt says: "Join rows are diff-and-replaced inside the same transaction."
        # Actually, if we just delete paper_authors and paper_categories, we can re-insert.

        # 1. Clean existing joins
        await self.session.execute(delete(PaperAuthor).where(PaperAuthor.paper_id == paper_id))
        await self.session.execute(delete(PaperCategory).where(PaperCategory.paper_id == paper_id))

        # 2. Re-insert authors
        if author_ids:
            author_inserts = [
                {"paper_id": paper_id, "author_id": auth_id, "position": pos}
                for pos, auth_id in enumerate(author_ids)
            ]
            await self.session.execute(insert(PaperAuthor).values(author_inserts))

        # 3. Re-insert categories
        if categories_data:
            cat_inserts = [
                {"paper_id": paper_id, "category_id": cat_id, "is_primary": is_prim}
                for cat_id, is_prim in categories_data
            ]
            await self.session.execute(insert(PaperCategory).values(cat_inserts))

        return paper_id, status, hash_changed

    async def list_papers(
        self,
        category: str | None = None,
        author: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        cursor_published_at: datetime.datetime | None = None,
        cursor_id: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[Paper]:
        """
        List papers with keyset pagination.
        Sorted by (published_at DESC, id DESC).
        """
        # We need eager loading for authors and categories to serialize to API easily
        stmt = select(Paper).options(
            selectinload(Paper.authors).selectinload(PaperAuthor.author),
            selectinload(Paper.categories).selectinload(PaperCategory.category),
        )

        if category:
            stmt = stmt.join(PaperCategory, Paper.id == PaperCategory.paper_id)
            stmt = stmt.join(Category, PaperCategory.category_id == Category.id)
            stmt = stmt.where(Category.code == category)

        if author:
            stmt = stmt.join(PaperAuthor, Paper.id == PaperAuthor.paper_id)
            stmt = stmt.join(Author, PaperAuthor.author_id == Author.id)
            stmt = stmt.where(Author.normalized_name == author)

        if start_date:
            stmt = stmt.where(Paper.published_at >= start_date)
        if end_date:
            stmt = stmt.where(Paper.published_at <= end_date)

        # Keyset pagination condition:
        # (published_at, id) < (cursor_published_at, cursor_id)
        if cursor_published_at and cursor_id:
            stmt = stmt.where(
                (Paper.published_at < cursor_published_at)
                | ((Paper.published_at == cursor_published_at) & (Paper.id < cursor_id))
            )

        # Order must be stable and match the cursor direction
        stmt = stmt.order_by(Paper.published_at.desc(), Paper.id.desc())
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_arxiv_id(self, arxiv_id: str) -> Paper | None:
        stmt = (
            select(Paper)
            .options(
                selectinload(Paper.authors).selectinload(PaperAuthor.author),
                selectinload(Paper.categories).selectinload(PaperCategory.category),
            )
            .where(Paper.arxiv_id == arxiv_id)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
