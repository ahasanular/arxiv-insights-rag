import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class AuthorSchema(BaseModel):
    id: uuid.UUID
    display_name: str
    normalized_name: str

    model_config = ConfigDict(from_attributes=True)


class CategorySchema(BaseModel):
    id: uuid.UUID
    code: str
    label: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaperSchema(BaseModel):
    id: uuid.UUID
    arxiv_id: str
    version: int
    title: str
    abstract: str
    published_at: datetime.datetime
    updated_at_source: datetime.datetime
    doi: str | None = None
    journal_ref: str | None = None
    comment: str | None = None
    abs_url: str
    pdf_url: str

    authors: list[AuthorSchema]
    categories: list[CategorySchema]

    model_config = ConfigDict(from_attributes=True)


class PaginatedPapersResponse(BaseModel):
    items: list[PaperSchema]
    next_cursor_published_at: datetime.datetime | None = None
    next_cursor_id: uuid.UUID | None = None
