import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.author import Author
from app.db.repositories.base import BaseRepository


class AuthorRepository(BaseRepository[Author]):
    def __init__(self, session: AsyncSession):
        super().__init__(Author, session)

    async def bulk_upsert(self, authors_data: list[dict]) -> dict[str, uuid.UUID]:
        """
        Upserts multiple authors based on normalized_name.
        Returns a mapping from normalized_name to the database UUID.
        """
        if not authors_data:
            return {}

        insert_stmt = insert(Author).values(
            [
                {"display_name": a["display_name"], "normalized_name": a["normalized_name"]}
                for a in authors_data
            ]
        )

        # On conflict (normalized_name), just update display_name (or do nothing).
        # We'll update the display_name to the latest seen.
        update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["normalized_name"],
            set_={"display_name": insert_stmt.excluded.display_name},
        ).returning(Author.normalized_name, Author.id)

        result = await self.session.execute(update_stmt)
        return {row.normalized_name: row.id for row in result.all()}
