from pydantic import BaseModel


class AuthorDTO(BaseModel):
    name: str


class CategoryDTO(BaseModel):
    term: str


class PaperDTO(BaseModel):
    id: str  # e.g., http://arxiv.org/abs/2401.12345v2
    updated: str
    published: str
    title: str
    summary: str
    authors: list[AuthorDTO]
    categories: list[CategoryDTO]
    primary_category: str | None = None
    doi: str | None = None
    journal_ref: str | None = None
    comment: str | None = None
    pdf_url: str | None = None
