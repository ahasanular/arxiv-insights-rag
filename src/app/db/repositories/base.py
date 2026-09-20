from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    def add(self, obj: ModelType) -> None:
        self.session.add(obj)

    async def get(self, id: Any) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
