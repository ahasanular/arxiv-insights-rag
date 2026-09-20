"""initial schema

Revision ID: 90a93b4df15f
Revises:
Create Date: 2026-09-20 16:34:49.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "90a93b4df15f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Authors
    op.create_table(
        "authors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_authors_normalized_name"), "authors", ["normalized_name"], unique=True)

    # 3. Categories
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_categories_code"), "categories", ["code"], unique=True)

    # 4. Ingest Runs
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("fetched", sa.Integer(), nullable=False),
        sa.Column("inserted", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. Papers
    op.create_table(
        "papers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("arxiv_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("abstract_raw", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_source", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doi", sa.String(), nullable=True),
        sa.Column("journal_ref", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("primary_category_id", sa.UUID(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("abs_url", sa.String(), nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["primary_category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_papers_arxiv_id"), "papers", ["arxiv_id"], unique=True)
    op.create_index(
        op.f("ix_papers_primary_category_id"), "papers", ["primary_category_id"], unique=False
    )
    op.create_index(op.f("ix_papers_published_at"), "papers", ["published_at"], unique=False)
    op.create_index(
        op.f("ix_papers_updated_at_source"), "papers", ["updated_at_source"], unique=False
    )

    # 5a. TSVECTOR generated column
    op.execute(
        "ALTER TABLE papers ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('english', coalesce(abstract, '')), 'B')) STORED;"
    )
    op.create_index(
        "ix_papers_search_vector", "papers", ["search_vector"], unique=False, postgresql_using="gin"
    )

    # 6. Paper Authors
    op.create_table(
        "paper_authors",
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("paper_id", "author_id"),
    )
    op.create_index("ix_paper_authors_author_id", "paper_authors", ["author_id"], unique=False)

    # 7. Paper Categories
    op.create_table(
        "paper_categories",
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("paper_id", "category_id"),
    )
    op.create_index(
        "ix_paper_categories_category_id_paper_id",
        "paper_categories",
        ["category_id", "paper_id"],
        unique=False,
    )

    # 8. Paper Embeddings
    import pgvector.sqlalchemy

    op.create_table(
        "paper_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=384), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "chunk_index", "model", name="uq_paper_embeddings_chunk"),
    )
    op.create_index(
        "ix_paper_embeddings_embedding",
        "paper_embeddings",
        ["embedding"],
        unique=False,
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("paper_embeddings")
    op.drop_table("paper_categories")
    op.drop_table("paper_authors")
    op.drop_table("papers")
    op.drop_table("ingest_runs")
    op.drop_table("categories")
    op.drop_table("authors")
    op.execute("DROP EXTENSION IF EXISTS vector;")
