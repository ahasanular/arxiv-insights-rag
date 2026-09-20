from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingest_run import IngestRun
from app.db.repositories.base import BaseRepository


class RunRepository(BaseRepository[IngestRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(IngestRun, session)
