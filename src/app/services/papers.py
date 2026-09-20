import datetime
import uuid

from app.api.schemas.papers import PaginatedPapersResponse, PaperSchema
from app.db.repositories.paper import PaperRepository


class PaperService:
    def __init__(self, paper_repo: PaperRepository):
        self.paper_repo = paper_repo

    async def list_papers(
        self,
        category: str | None = None,
        author: str | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        cursor_published_at: datetime.datetime | None = None,
        cursor_id: uuid.UUID | None = None,
        limit: int = 20,
    ) -> PaginatedPapersResponse:
        # Fetch one extra to determine if there's a next page
        papers = await self.paper_repo.list_papers(
            category=category,
            author=author,
            start_date=start_date,
            end_date=end_date,
            cursor_published_at=cursor_published_at,
            cursor_id=cursor_id,
            limit=limit + 1,
        )

        has_more = len(papers) > limit
        items = papers[:limit]

        next_cursor_pub = None
        next_cursor_id = None

        if items and has_more:
            last_item = items[-1]
            next_cursor_pub = last_item.published_at
            next_cursor_id = last_item.id

        # Convert ORM to Pydantic
        # Since we use joinedload, we must extract authors and categories correctly
        schemas = []
        for p in items:
            p_dict = p.__dict__.copy()
            # Handle relationships
            p_dict["authors"] = [pa.author.__dict__ for pa in p.authors]
            p_dict["categories"] = [pc.category.__dict__ for pc in p.categories]
            schemas.append(PaperSchema.model_validate(p_dict))

        return PaginatedPapersResponse(
            items=schemas,
            next_cursor_published_at=next_cursor_pub,
            next_cursor_id=next_cursor_id,
        )

    async def get_paper(self, arxiv_id: str) -> PaperSchema | None:
        p = await self.paper_repo.get_by_arxiv_id(arxiv_id)
        if not p:
            return None

        p_dict = p.__dict__.copy()
        p_dict["authors"] = [pa.author.__dict__ for pa in p.authors]
        p_dict["categories"] = [pc.category.__dict__ for pc in p.categories]
        return PaperSchema.model_validate(p_dict)
