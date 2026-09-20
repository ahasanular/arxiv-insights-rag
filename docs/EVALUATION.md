# RAG Pipeline Evaluation

This document outlines the evaluation strategy and retrieval performance for the arXiv Insight RAG pipeline.

## Why We Evaluate
RAG systems often fail silently when queries are out of domain or when retrieval precision drops. To convert "I built RAG" into "I measured my RAG," we have implemented a dynamic **Golden Set Evaluation Harness** (`agy-ingest eval` or `python -m app.cli eval`).

This harness performs end-to-end testing of our **Reciprocal Rank Fusion (RRF)** hybrid search and the semantic **Relevance Gate**.

## Metrics Explained
- **Recall@5**: The percentage of queries where the correct paper was retrieved in the top 5 results.
- **MRR (Mean Reciprocal Rank)**: A measure of how high up the correct paper appears. An MRR of 1.0 means it was always the #1 result.
- **Abstention Precision**: The percentage of out-of-corpus, irrelevant queries (e.g., "Who is xeng?") where the relevance gate correctly triggered an abstention instead of attempting to summarize unrelated papers.

## Tuning & Results

### Initial Baseline (`tau=0.5`)
With the default embedding model (`BAAI/bge-small-en-v1.5`), dense vectors exhibit a baseline similarity of ~0.6-0.7 even for completely unrelated sentences. At a relevance threshold of `0.5`, the system failed to abstain on nonsense questions and attempted to answer them using random papers.

### Tuned Baseline (`tau=0.75`)
By tuning the relevance gate threshold (`tau`) to `0.75` and enforcing a secondary lexical gate in our local extractive fallback, the system correctly filters out noise.

**Latest Run (13 Queries):**
- **Recall@5**: 1.0 (100%)
- **MRR**: 1.0 (100%)
- **Abstention Precision**: 1.0 (100%)
- **Avg Latency**: ~20ms (pure retrieval time via pgvector + FTS)

## Re-running the Evaluation
To verify these numbers against your local database, you can run the CLI command:
```bash
python -m app.cli eval --tau 0.75
```
*(or via `make eval`)*

The script dynamically picks random valid papers from your local DB to form the in-corpus queries. It also mixes in out-of-corpus queries, but first verifies via Full-Text Search (FTS) that these concepts do not actually exist in your database before using them, ensuring the abstention test is completely mathematically sound.
