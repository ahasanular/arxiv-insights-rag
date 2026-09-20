import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession):
        super().__init__(Category, session)

    async def bulk_upsert(self, categories_data: list[dict]) -> dict[str, uuid.UUID]:
        """
        Upserts multiple categories based on code.
        Returns a mapping from category code to the database UUID.
        """
        if not categories_data:
            return {}

        insert_stmt = insert(Category).values(
            [{"code": c["code"], "label": c.get("label")} for c in categories_data]
        )

        # On conflict (code), we can update the label if we want.
        update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["code"], set_={"label": insert_stmt.excluded.label}
        ).returning(Category.code, Category.id)

        result = await self.session.execute(update_stmt)
        return {row.code: row.id for row in result.all()}
