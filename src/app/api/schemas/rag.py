from typing import Any

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class SourceSchema(BaseModel):
    arxiv_id: str
    title: str
    authors: list[
        str
    ] = []  # Optional, we didn't join authors in hybrid search yet, wait, we can add it or omit it
    published_at: str
    score: float
    url: str


class AskResponse(BaseModel):
    answer: str
    abstained: bool
    sources: list[SourceSchema]
    meta: dict[str, Any]
