import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.limiter import limiter
from app.api.schemas.papers import PaginatedPapersResponse, PaperSchema
from app.db.repositories.paper import PaperRepository
from app.db.session import get_db_session
from app.services.papers import PaperService

router = APIRouter(prefix="/papers", tags=["papers"])


def get_paper_service(session: AsyncSession = Depends(get_db_session)) -> PaperService:
    repo = PaperRepository(session)
    return PaperService(repo)


@router.get("", response_model=PaginatedPapersResponse)
@limiter.limit("60/minute")
async def list_papers(
    request: Request,
    category: Annotated[str | None, Query(description="Filter by category code")] = None,
    author: Annotated[
        str | None, Query(description="Filter by exact author normalized_name")
    ] = None,
    start_date: Annotated[datetime.datetime | None, Query(description="Start published_at")] = None,
    end_date: Annotated[datetime.datetime | None, Query(description="End published_at")] = None,
    cursor_published_at: Annotated[
        datetime.datetime | None, Query(description="Pagination cursor (published_at)")
    ] = None,
    cursor_id: Annotated[uuid.UUID | None, Query(description="Pagination cursor (id)")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    service: PaperService = Depends(get_paper_service),
) -> PaginatedPapersResponse:
    if (cursor_published_at and not cursor_id) or (cursor_id and not cursor_published_at):
        raise HTTPException(
            status_code=400,
            detail="Both cursor_published_at and cursor_id must be provided together.",
        )

    return await service.list_papers(
        category=category,
        author=author,
        start_date=start_date,
        end_date=end_date,
        cursor_published_at=cursor_published_at,
        cursor_id=cursor_id,
        limit=limit,
    )


@router.get("/{arxiv_id}", response_model=PaperSchema)
@limiter.limit("60/minute")
async def get_paper(
    request: Request,
    arxiv_id: str,
    service: PaperService = Depends(get_paper_service),
) -> PaperSchema:
    paper = await service.get_paper(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper
