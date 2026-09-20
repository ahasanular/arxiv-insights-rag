# ADR 1: Why pgvector over Chroma

## Context
When building a Retrieval-Augmented Generation (RAG) system, we need a vector database to store and query embeddings. Popular choices include dedicated vector stores like Chroma, Qdrant, or FAISS, as well as extending traditional relational databases like PostgreSQL using `pgvector`.

## Decision
We chose to use PostgreSQL with the `pgvector` extension instead of a dedicated vector database like Chroma or FAISS.

## Rationale
1. **Single Source of Truth:** Using a second datastore creates a dual-write consistency problem. We would need to keep the relational metadata (authors, categories, publication dates) perfectly synced with the vector store. With `pgvector`, rows and their embeddings are kept in a single transaction.
2. **Advanced Metadata Filtering:** Hybrid search often requires pre-filtering by metadata (e.g., date ranges or categories). Traditional vector DBs have limited and often clunky metadata filtering. PostgreSQL provides native, highly optimized B-Tree and GIN indexes that can be combined seamlessly with `pgvector`'s HNSW vector search in a single SQL query.
3. **Simplicity:** It removes the need for a separate volume, a separate backup strategy, and a separate container service, keeping our deployment topology simple (just API + DB + Redis).

## Consequences
- Queries that perform similarity search must be written in SQL (via SQLAlchemy) rather than using a vector DB's Python client.
- The `pgvector` HNSW index requires careful tuning of `ef_search` and `m` parameters depending on the dataset size.
