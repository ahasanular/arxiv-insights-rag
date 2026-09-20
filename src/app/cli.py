import asyncio
from typing import Annotated

import structlog
import typer

from app.db.repositories.author import AuthorRepository
from app.db.repositories.category import CategoryRepository
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.paper import PaperRepository
from app.db.repositories.run import RunRepository
from app.db.repositories.stats import StatsRepository
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
    ] = "cat:cs.AI",
    max_results: Annotated[
        int, typer.Option("--max-results", "-m", help="Maximum papers to fetch")
    ] = 1000,
    since_last: Annotated[
        bool, typer.Option("--since-last", help="Stop after encountering unchanged papers")
    ] = False,
    resume: Annotated[int, typer.Option("--resume", help="Resume from specific offset")] = 0,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Fetch and parse without persisting to DB")
    ] = False,
):
    """
    Ingests papers from arXiv into the local database.

    Examples:
        agy-ingest ingest                              # Default: cs.AI, 1000 papers
        agy-ingest ingest -c "cat:cs.LG" -m 500        # Custom category and limit
        agy-ingest ingest --dry-run                     # Preview without writing to DB
        agy-ingest ingest --since-last                  # Incremental (stop on unchanged)
    """

    async def _ingest():
        from app.core.redis import redis_client as global_redis_client

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
                redis_client=global_redis_client,
            )

            mode = "DRY RUN" if dry_run else ("incremental" if since_last else "full")
            typer.echo(
                f"Starting ingestion ({mode}): query='{categories}', max={max_results}"
            )
            run = await svc.ingest_papers(
                search_query=categories,
                max_results=max_results,
                since_last=since_last,
                resume_cursor=resume,
                dry_run=dry_run,
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
        await global_redis_client.aclose()

    run_async(_ingest())


@app.command()
def reindex():
    """
    Re-computes embeddings for papers with stale or missing vectors.

    This command is planned for a future release to support:
    - Switching embedding models (e.g., bge-small → bge-large)
    - Backfilling embeddings after a failed ingestion run
    - Refreshing vectors after abstract normalization changes

    Currently, embeddings are computed inline during ingestion.
    Re-running `ingest` will automatically refresh embeddings for any
    paper whose content_hash has changed.
    """
    typer.echo(
        "ℹ️  Embedding reindex is planned for a future release.\n"
        "\n"
        "Currently, embeddings are computed inline during ingestion.\n"
        "Re-running `ingest` will automatically refresh embeddings for\n"
        "any paper whose content has changed (via content_hash comparison).\n"
        "\n"
        "To force a full re-embed, use: agy-ingest wipe --yes && agy-ingest ingest"
    )


@app.command()
def eval(
    tau: Annotated[
        float, typer.Option("--tau", help="Cosine similarity threshold for relevance gate")
    ] = 0.75,
    samples: Annotated[
        int, typer.Option("--samples", help="Number of in-corpus questions to generate for evaluation")
    ] = 100,
):
    """
    Runs the RAG evaluation harness (Recall@5, MRR, Abstention Precision).
    """

    async def _eval():
        from app.services.evaluation import EvaluationService

        embedder = EmbedderService()
        svc = EvaluationService(embedder)

        typer.echo(f"Starting RAG Evaluation (tau={tau}, samples={samples})...")
        metrics = await svc.run_evaluation(tau=tau, samples=samples)

        typer.echo("\n[In-Corpus Questions]")
        for q in metrics.get("in_corpus_questions", []):
            typer.echo(f" - {q}")

        typer.echo("\n[Out-of-Corpus Questions]")
        for q in metrics.get("out_of_corpus_questions", []):
            typer.echo(f" - {q}")

        typer.echo("\n--- Evaluation Results ---")
        for k, v in metrics.items():
            if k not in ("in_corpus_questions", "out_of_corpus_questions"):
                typer.echo(f"{k}: {v}")

    run_async(_eval())


@app.command()
def wipe(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm wipe")] = False,
):
    """
    Wipe all papers, authors, categories, embeddings, and run history.
    This is a destructive operation that resets the database to a clean state.
    """
    if not yes:
        typer.echo("⚠️  This will delete ALL data. Use --yes to confirm.")
        raise typer.Exit(1)

    async def _wipe():
        async with async_session_maker() as session:
            stats_repo = StatsRepository(session)
            await stats_repo.wipe_all()
            typer.echo("✅ Database wiped successfully (papers, authors, categories, embeddings, runs).")

    run_async(_wipe())


@app.command()
def status():
    """
    Displays current DB counts and the last successful ingest run.
    """

    async def _status():
        async with async_session_maker() as session:
            stats_repo = StatsRepository(session)
            summary = await stats_repo.get_summary()

            typer.echo("DB Status:")
            typer.echo(f"  Papers:     {summary['total_papers']}")
            typer.echo(f"  Authors:    {summary['total_authors']}")
            typer.echo(f"  Categories: {summary['total_categories']}")
            typer.echo(f"  Embedding Coverage: {summary['embedding_coverage_pct']}%")
            typer.echo(f"  Date Range: {summary['min_date'] or 'N/A'} → {summary['max_date'] or 'N/A'}")
            typer.echo(f"  Last Ingest: {summary['last_ingest'] or 'Never'}")

    run_async(_status())


if __name__ == "__main__":
    app()
