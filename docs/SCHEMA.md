# Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    PAPERS {
        UUID id PK
        string arxiv_id UK
        int version
        string title
        text abstract
        text abstract_raw
        datetime published_at
        datetime updated_at_source
        string doi
        string journal_ref
        text comment
        UUID primary_category_id FK
        string content_hash
        string abs_url
        string pdf_url
        datetime first_seen_at
        datetime last_synced_at
        tsvector search_vector "Generated"
    }

    AUTHORS {
        UUID id PK
        string display_name
        string normalized_name UK
    }

    CATEGORIES {
        UUID id PK
        string code UK
        string label
    }

    PAPER_AUTHORS {
        UUID paper_id PK, FK
        UUID author_id PK, FK
        int position
    }

    PAPER_CATEGORIES {
        UUID paper_id PK, FK
        UUID category_id PK, FK
        boolean is_primary
    }

    PAPER_EMBEDDINGS {
        UUID id PK
        UUID paper_id FK
        int chunk_index
        string model
        int dim
        string content_hash
        vector embedding
    }

    INGEST_RUNS {
        UUID id PK
        string mode
        json params
        datetime started_at
        datetime finished_at
        string status
        int fetched
        int inserted
        int updated
        int unchanged
        int failed
        int cursor
        text error
    }

    PAPERS ||--o{ PAPER_AUTHORS : "has"
    AUTHORS ||--o{ PAPER_AUTHORS : "written by"
    
    PAPERS ||--o{ PAPER_CATEGORIES : "categorized by"
    CATEGORIES ||--o{ PAPER_CATEGORIES : "contains"
    
    PAPERS ||--o{ PAPER_EMBEDDINGS : "embedded as"
    PAPERS }o--|| CATEGORIES : "primary_category"
```

## Index Rationale

| Table | Index / Constraint | Purpose / Query Supported |
|---|---|---|
| `papers` | `UNIQUE(arxiv_id)` | Upsert idempotency during ingestion (`INSERT ... ON CONFLICT (arxiv_id) DO UPDATE`). Versionless to support arXiv version updates gracefully. |
| `papers` | `INDEX(published_at)` | Aggregations: `GET /api/v1/stats/papers-over-time`. Fast date filtering. |
| `papers` | `INDEX(updated_at_source)` | Identifying out-of-date papers during incremental ingestions. |
| `papers` | `INDEX(primary_category_id)` | Fast top-level category groupings and aggregations. |
| `papers` | `GIN(search_vector)` | Full-text hybrid search (FTS leg of Reciprocal Rank Fusion). Generated column from `title` and `abstract`. |
| `authors` | `UNIQUE(normalized_name)` | Global author deduplication across papers. |
| `categories` | `UNIQUE(code)` | Guarantee idempotency when lazily seeding categories from the arXiv XML. |
| `paper_embeddings` | `HNSW(embedding)` | Fast Approximate Nearest Neighbor (ANN) vector search (Vector leg of RRF). Uses `vector_cosine_ops`. Configured with `m=16`, `ef_construction=64`. |
| `paper_embeddings` | `UNIQUE(paper_id, chunk_index, model)` | Prevents duplicating chunks for the same embedding model per paper. |
| `paper_categories` | `INDEX(category_id, paper_id)` | Fast lookup of all papers for a specific category. |
| `paper_authors` | `INDEX(author_id)` | Fast lookup of all papers for a specific author. |

## Important Design Constraints
1. **Cascade Deletes**: `paper_embeddings`, `paper_authors`, and `paper_categories` all have `ON DELETE CASCADE` foreign keys pointing to `papers`. A `wipe` operation can simply `TRUNCATE papers CASCADE` and efficiently clean up related states.
2. **Selective Re-Embedding**: `papers.content_hash` vs `paper_embeddings.content_hash`. The indexer compares these hashes. If a paper's text changes mid-crawl, the row is updated, and the new hash triggers the selective re-embedder instead of a full recompute.
3. **Generated TSVECTOR**: The `search_vector` on `papers` is maintained directly by Postgres triggers (`GENERATED ALWAYS AS`). No application-level sync logic is required, meaning keyword search is perfectly consistent.
