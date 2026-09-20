import structlog

from app.db.models.ingest_run import IngestRun
from app.db.repositories.author import AuthorRepository
from app.db.repositories.category import CategoryRepository
from app.db.repositories.embedding import EmbeddingRepository
from app.db.repositories.paper import PaperRepository
from app.db.repositories.run import RunRepository
from app.ingestion.client import ArxivClient, ArxivEmptyFeedError
from app.ingestion.normalizer import normalize_paper
from app.ingestion.parser import parse_arxiv_response
from app.services.embedder import EmbedderService

logger = structlog.get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        client: ArxivClient,
        paper_repo: PaperRepository,
        author_repo: AuthorRepository,
        category_repo: CategoryRepository,
        run_repo: RunRepository,
        embedding_repo: EmbeddingRepository,
        embedder: EmbedderService,
    ):
        self.client = client
        self.paper_repo = paper_repo
        self.author_repo = author_repo
        self.category_repo = category_repo
        self.run_repo = run_repo
        self.embedding_repo = embedding_repo
        self.embedder = embedder

    async def ingest_papers(
        self,
        search_query: str,
        max_results: int = 100,
        since_last: bool = False,
        resume_cursor: int | None = None,
    ) -> IngestRun:
        run = IngestRun(
            mode="incremental" if since_last else "full",
            params={
                "search_query": search_query,
                "max_results": max_results,
                "resume": resume_cursor,
            },
        )
        self.run_repo.add(run)
        await self.run_repo.session.commit()

        start = resume_cursor or 0
        consecutive_unchanged = 0
        seen_arxiv_ids = set()

        page_size = 100

        try:
            while start < max_results:
                fetch_size = min(page_size, max_results - start)
                logger.info("Fetching page", start=start, fetch_size=fetch_size)

                try:
                    xml_text = await self.client.fetch_page(
                        search_query, start=start, max_results=fetch_size
                    )
                except ArxivEmptyFeedError:
                    logger.error("Arxiv returned an empty feed after retries. Aborting run.")
                    run.status = "failed"
                    run.error = "Empty feed"
                    break
                except Exception as e:
                    logger.exception("Failed to fetch page from arxiv", error=str(e))
                    run.status = "failed"
                    run.error = str(e)
                    break

                dtos = parse_arxiv_response(xml_text)

                if not dtos:
                    logger.info("No more papers returned. Ending crawl.")
                    break

                for dto in dtos:
                    run.fetched += 1
                    try:
                        normalized = normalize_paper(dto)
                        arxiv_id = normalized["arxiv_id"]

                        # Dedupe within run to prevent double-insert if window shifted
                        if arxiv_id in seen_arxiv_ids:
                            continue
                        seen_arxiv_ids.add(arxiv_id)

                        # 1. Bulk Upsert Authors
                        authors_map = await self.author_repo.bulk_upsert(normalized["authors"])
                        # Create ordered author_ids
                        author_ids = [
                            authors_map[a["normalized_name"]] for a in normalized["authors"]
                        ]

                        # 2. Bulk Upsert Categories
                        cats_map = await self.category_repo.bulk_upsert(normalized["categories"])
                        category_data = [
                            (cats_map[c["code"]], c["is_primary"]) for c in normalized["categories"]
                        ]

                        # Fix up the primary category ID for the paper
                        primary_code = normalized.pop("primary_category_code", None)
                        normalized["primary_category_id"] = (
                            cats_map.get(primary_code) if primary_code else None
                        )

                        # 3. Upsert Paper and relationships
                        paper_id, status, hash_changed = await self.paper_repo.upsert_paper(
                            normalized, author_ids, category_data
                        )

                        if hash_changed:
                            # 4. We need to embed this paper
                            text_to_embed = f"{normalized['title']}\n\n{normalized['abstract']}"
                            # fastembed is synchronous but very fast locally; ideally run in executor
                            # but for ingestion script we can block briefly
                            vector = self.embedder.embed_texts([text_to_embed])[0]

                            embedding_data = {
                                "paper_id": paper_id,
                                "chunk_index": 0,
                                "embedding": vector,
                                "model": self.embedder.model_name,
                                "dim": len(vector),
                                "content_hash": normalized["content_hash"],
                            }
                            await self.embedding_repo.upsert_embeddings([embedding_data])

                        if status == "inserted":
                            run.inserted += 1
                            consecutive_unchanged = 0
                        elif status == "updated":
                            run.updated += 1
                            consecutive_unchanged = 0
                        else:
                            run.unchanged += 1
                            consecutive_unchanged += 1

                        # Commit per-paper or per-page?
                        # Since upsert_paper might rely on author/category locks, we'll flush/commit per paper
                        # to isolate failures.
                        await self.paper_repo.session.commit()
                        await self.embedding_repo.session.commit()

                        if since_last and consecutive_unchanged >= 50:
                            logger.info("Incremental threshold reached. Stopping.")
                            start = max_results  # break outer loop
                            break

                    except Exception as e:
                        logger.exception("Failed to ingest paper", arxiv_id=dto.id, error=str(e))
                        run.failed += 1
                        await self.paper_repo.session.rollback()

                start += page_size
                run.cursor = start

                # Update run stats periodically
                await self.run_repo.session.commit()

        finally:
            if run.status == "running":
                run.status = "completed"
            import datetime

            run.finished_at = datetime.datetime.now(datetime.UTC)
            await self.run_repo.session.commit()

        return run
