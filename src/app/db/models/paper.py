import datetime
import uuid

from sqlalchemy import (
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)

    author: Mapped["Author"] = relationship("Author")

    # Indexes
    __table_args__ = (Index("ix_paper_authors_author_id", "author_id"),)


class PaperCategory(Base):
    __tablename__ = "paper_categories"

    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(default=False)

    category: Mapped["Category"] = relationship("Category")

    __table_args__ = (Index("ix_paper_categories_category_id_paper_id", "category_id", "paper_id"),)


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)
    abstract_raw: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)

    published_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at_source: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )

    doi: Mapped[str | None] = mapped_column(String, nullable=True)
    journal_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    primary_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    content_hash: Mapped[str] = mapped_column(String)
    abs_url: Mapped[str] = mapped_column(String)
    pdf_url: Mapped[str] = mapped_column(String)

    # Generated full-text search vector. Setup in Alembic.
    search_vector = mapped_column(TSVECTOR, server_default=FetchedValue())

    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC)
    )
    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC)
    )

    authors: Mapped[list["PaperAuthor"]] = relationship(
        "PaperAuthor", backref="paper", cascade="all, delete-orphan"
    )
    categories: Mapped[list["PaperCategory"]] = relationship(
        "PaperCategory", backref="paper", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_papers_search_vector", "search_vector", postgresql_using="gin"),)
