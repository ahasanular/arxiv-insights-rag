# arXiv Insight RAG

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791.svg?style=flat-square&logo=postgresql)](https://github.com/pgvector/pgvector)
[![Groq](https://img.shields.io/badge/LLM-Groq-f55036.svg?style=flat-square)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED.svg?style=flat-square&logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

An end-to-end data pipeline and REST API for ingesting arXiv research papers, storing them in PostgreSQL with pgvector, and querying them using a hybrid Retrieval-Augmented Generation (RAG) system with strict anti-hallucination guardrails.

---

## 🚀 Setup & Run

### 1. Configure Environment
Copy the example environment file and configure your Groq API key:
```bash
cp .env.example .env
# Edit .env to add your Groq API Key (or leave empty for local extractive fallback)
```

### 2. Start Services (Docker)
The easiest way to run the entire stack (PostgreSQL + pgvector, Redis, API, and Alembic migrations) is via Docker Compose:
```bash
docker compose up --build -d
```
- **Dashboard UI**: [http://localhost:8000/](http://localhost:8000/)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Ingest Papers
The CLI tool is packaged directly into the container. Ingest papers from any arXiv category:
```bash
# Ingest papers from a category (e.g., cs.AI, cs.LG, stat.ML)
docker compose exec api agy-ingest ingest -c cat:cs.AI -m 100

# View all CLI options
docker compose exec api agy-ingest ingest --help
```

*Alternative: Local Installation (For Development)*
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
agy-ingest ingest -c cat:cs.AI -m 100
```

---

## 🤖 Advanced RAG & LLM Engine

Powered by **Groq** for high-throughput inference (e.g. `llama-3.3-70b-versatile` or `llama3-70b-8192`), fortified with structured retrieval and defense guardrails:

- **Hybrid Search (RRF)**: Merges dense semantic embeddings (`fastembed` ONNX `bge-small-en-v1.5`) with PostgreSQL Full-Text Search (`tsvector`) using Reciprocal Rank Fusion.
- **Chain-of-Thought (CoT) Verification**: The LLM outputs an internal `reasoning` trace first, verifying whether retrieved documents answer the question before committing to a response.
- **Strict Anti-Hallucination Guardrails**: Filters out low-relevance contexts and explicitly abstains if the query falls outside the indexed corpus ($\tau=0.75$).
- **Prompt Injection Defense**: User queries are quarantined within XML boundaries to neutralize injection attempts.
- **Inline Citations**: Synthesizes responses with verifiable inline citations (e.g., `[2305.18290]`), rendered as clickable badges on the dashboard.
- **Offline Fallback**: Automatically falls back to a local extractive search mode if no LLM API key is present.

---

## 🏗️ Architecture & Stack

- **Ingestion CLI (`agy-ingest`)**: Fetches arXiv metadata via Atom API, sanitizes abstracts, and generates 384-dimensional embeddings locally on CPU via ONNX Runtime.
- **Database (`PostgreSQL + pgvector`)**: Normalizes papers, authors, and categories with HNSW vector indexing and GIN full-text search indexes.
- **Backend API (`FastAPI`)**: Asynchronous endpoints for RAG queries, analytics, and Prometheus health metrics.
- **Caching & Rate Limiting (`Redis`)**: Powers `SlowAPI` rate limiting and aggressively caches heavy statistical queries for instant dashboard loads.

For deeper technical documentation, see:
- 📖 [System Architecture & Developer Guide](docs/DEVELOPMENT.md)
- 📊 [Database Schema & ER Diagram](docs/SCHEMA.md)
- 🎯 [RAG Evaluation Harness & Metrics](docs/EVALUATION.md)
- 🏛️ [Architectural Decision Records (ADRs)](docs/adr/)

---

## ⚡ Sample API Requests

### 1. Dashboard Visualization Data (Cached)
```bash
curl -X GET "http://localhost:8000/api/v1/stats/visualization"
```
```json
{
  "data": {
    "summary": {
      "total_papers": 1250,
      "total_authors": 3405,
      "total_categories": 12,
      "min_date": "2020-01-01T00:00:00Z",
      "max_date": "2024-01-01T00:00:00Z",
      "embedding_coverage_pct": 100.0,
      "last_ingest": "2026-09-21T06:00:00Z"
    },
    "papers_over_time": [
      { "period": "2023-01", "count": 150 },
      { "period": "2023-02", "count": 180 }
    ],
    "top_categories": [
      { "code": "cs.AI", "label": "Artificial Intelligence", "count": 450, "share_pct": 36.0 }
    ],
    "top_authors": [
      { "display_name": "Yoshua Bengio", "normalized_name": "yoshua bengio", "count": 15 }
    ]
  },
  "meta": {
    "generated_at": "2026-09-21T06:00:00Z",
    "total": null,
    "filters": {}
  }
}
```

### 2. RAG Query
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "Advancements in Transformers"}'
```
```json
{
  "answer": "The authors propose a 12-layer transformer model that significantly outperforms previous architectures on language tasks [1234.5678].",
  "abstained": false,
  "sources": [
    {
      "arxiv_id": "1234.5678",
      "title": "Hybrid-Attention Language Models",
      "authors": ["Anton Xue", "Litu Rout"],
      "published_at": "2026-09-17T17:39:46Z",
      "score": 0.0328,
      "url": "https://arxiv.org/abs/1234.5678"
    }
  ],
  "meta": {
    "strategy": "hybrid_rrf",
    "retrieval_ms": 15.2,
    "embed_ms": 42.1,
    "llm_ms": 1204.5,
    "total_ms": 1261.8,
    "model": "llama3-70b-8192"
  }
}
```

---

## ⚖️ Trade-offs & Considerations

1. **Abstract-Level Indexing:** The system indexes paper abstracts (~150 words) rather than full PDFs. This keeps embedding costs minimal and retrieval latency under 50ms, while remaining highly effective for paper discovery and synthesis.
2. **Author Disambiguation:** Author names are normalized, but distinct authors with identical names are aggregated. True disambiguation requires cross-referencing external identifiers (e.g., ORCID).
3. **API Rate Compliance:** Ingestion crawls are paced at ~3.1 seconds per request to adhere to arXiv's fair usage policies.
4. **Dense Vector Baseline Similarity:** Dense models (`bge-small-en-v1.5`) exhibit non-zero baseline similarities for unrelated texts; an empirical relevance gate ($\tau=0.75$) prevents irrelevant retrieval.

---

## 🔮 Roadmap

- [ ] **Full-Text PDF Ingestion**: Sliding-window chunking to index full paper PDFs for deeper technical queries.
- [ ] **Asynchronous Workers**: Offload batch crawling and embeddings to Celery/Redis workers.
- [ ] **Multi-Model Support**: Dynamic routing between Groq, OpenAI, Anthropic, and local Ollama models.
- [ ] **Cross-Encoder Re-Ranking**: Optional secondary re-ranker (`ms-marco-MiniLM-L-6-v2`) for complex search queries.
- [ ] **Conversational Memory**: Multi-turn conversation sessions for contextual follow-up questions.

---

## 📄 License

Distributed under the [MIT License](LICENSE).

---

<div align="center">
  <b>Developed by Arafath</b><br>
  <a href="https://ahasanularafath.com">ahasanularafath.com</a>
</div>

