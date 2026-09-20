import asyncio
from typing import Annotated

import structlog
import typer

from app.db.repositories.author import AuthorRepository
from app.db.repositories.category import CategoryRepository
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.paper import PaperRepository
from app.db.repositories.run import RunRepository
from app.db.session import async_session_maker
from app.ingestion.client import ArxivClient
from app.ingestion.service import IngestionService
from app.services.embedder import EmbedderService

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="arxiv-insight",
    help="arXiv Ingestion and Analytics CLI",
    add_completion=False,
)


def run_async(coro):
    """Helper to run async commands."""
    return asyncio.run(coro)


@app.command()
def ingest(
    categories: Annotated[
        str, typer.Option("--categories", "-c", help="Search query/categories")
    ] = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
    max_results: Annotated[
        int, typer.Option("--max-results", "-m", help="Maximum papers to fetch")
    ] = 100,
    since_last: Annotated[
        bool, typer.Option("--since-last", help="Stop after encountering unchanged papers")
    ] = False,
    resume: Annotated[int, typer.Option("--resume", help="Resume from specific offset")] = 0,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not persist to DB")] = False,
):
    """
    Ingests papers from arXiv.
    """
    if dry_run:
        typer.echo("Dry run not fully implemented; would just fetch.")
        raise typer.Exit()

    async def _ingest():
        client = ArxivClient()
        embedder = EmbedderService()
        async with async_session_maker() as session:
            svc = IngestionService(
                client=client,
                paper_repo=PaperRepository(session),
                author_repo=AuthorRepository(session),
                category_repo=CategoryRepository(session),
                run_repo=RunRepository(session),
                embedding_repo=EmbeddingRepository(session),
                embedder=embedder,
            )

            typer.echo(
                f"Starting ingestion: query='{categories}', max={max_results}, incremental={since_last}"
            )
            run = await svc.ingest_papers(
                search_query=categories,
                max_results=max_results,
                since_last=since_last,
                resume_cursor=resume,
            )

            typer.echo(
                f"Ingestion {run.status}: "
                f"fetched={run.fetched}, "
                f"inserted={run.inserted}, "
                f"updated={run.updated}, "
                f"unchanged={run.unchanged}, "
                f"failed={run.failed}"
            )

        await client.close()

    run_async(_ingest())


@app.command()
def reindex(
    all: Annotated[bool, typer.Option("--all", help="Reindex all papers")] = False,
    missing: Annotated[
        bool, typer.Option("--missing", help="Reindex papers missing embeddings")
    ] = True,
):
    """
    Triggers the embedding indexer.
    (Not fully implemented, will be done later)
    """
    typer.echo("Embedding indexer stub. Will be fully wired in Phase 4.")


@app.command()
def eval(
    tau: Annotated[
        float, typer.Option("--tau", help="Cosine similarity threshold for relevance gate")
    ] = 0.75,
):
    """
    Runs the RAG evaluation harness (Recall@5, MRR, Abstention Precision).
    """

    async def _eval():
        from app.services.evaluation import EvaluationService

        embedder = EmbedderService()
        svc = EvaluationService(embedder)

        typer.echo(f"Starting RAG Evaluation (tau={tau})...")
        metrics = await svc.run_evaluation(tau=tau)

        typer.echo("\n--- Evaluation Results ---")
        for k, v in metrics.items():
            if k not in ("in_corpus_questions", "out_of_corpus_questions"):
                typer.echo(f"{k}: {v}")

        typer.echo("\n[In-Corpus Questions]")
        for q in metrics.get("in_corpus_questions", []):
            typer.echo(f" - {q}")

        typer.echo("\n[Out-of-Corpus Questions]")
        for q in metrics.get("out_of_corpus_questions", []):
            typer.echo(f" - {q}")

    run_async(_eval())


@app.command()
def wipe(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm wipe")] = False,
):
    """
    Wipe all papers, authors, categories, embeddings, and run history.
    """
    if not yes:
        typer.echo("Use --yes to confirm.")
        raise typer.Exit(1)

    async def _wipe():
        from sqlalchemy import text

        async with async_session_maker() as session:
            # CASCADE on papers deletes paper_authors, paper_categories, paper_embeddings
            await session.execute(
                text("TRUNCATE papers, authors, categories, ingest_runs RESTART IDENTITY CASCADE")
            )
            await session.commit()
            typer.echo("Database wiped successfully.")

    run_async(_wipe())


@app.command()
def status():
    """
    Displays current DB counts and the last successful ingest run.
    """

    async def _status():
        from sqlalchemy import text

        async with async_session_maker() as session:
            papers = await session.scalar(text("SELECT COUNT(*) FROM papers"))
            authors = await session.scalar(text("SELECT COUNT(*) FROM authors"))
            cats = await session.scalar(text("SELECT COUNT(*) FROM categories"))
            runs = await session.scalar(text("SELECT COUNT(*) FROM ingest_runs"))
            typer.echo("DB Status:")
            typer.echo(f"  Papers: {papers}")
            typer.echo(f"  Authors: {authors}")
            typer.echo(f"  Categories: {cats}")
            typer.echo(f"  Ingest Runs: {runs}")

    run_async(_status())


if __name__ == "__main__":
    app()
