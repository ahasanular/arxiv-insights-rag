# arXiv Insight RAG

A complete pipeline and API for ingesting arXiv research papers, storing them relationally, and querying them using an Advanced Retrieval-Augmented Generation (RAG) system with strictly engineered guardrails.

---

## 🚀 Setup & Run

**1. Configure Environment**
Copy the example environment file and add your Groq API key:
```bash
cp .env.example .env
# Edit .env to add your Groq API Key
```

**2. Start Services (via Docker)**
The easiest way to run the entire stack (Database, Redis, API, and Migrations) is via Docker Compose:
```bash
docker compose up --build
```
- **Dashboard UI**: http://localhost:8000/
- **API Docs**: http://localhost:8000/docs

**3. Ingest Papers**
Because the CLI is packaged into the API container, you can ingest papers directly without installing Python locally (run this multiple times to ingest 1000 records from multiple choosen categories):
```bash
docker compose exec api agy-ingest ingest -c cat:cs.AI -m 200
```
or for better customized usage
```bash
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

We utilize **Groq** as our exclusive LLM provider to power lightning-fast inference using high-tier models like `llama3-70b-8192`. 

The conversational RAG pipeline is fortified with advanced prompt engineering to ensure maximum accuracy and security:
- **Chain-of-Thought (CoT) Verification**: The LLM is forced to output a `reasoning` field first, internally verifying if the retrieved documents definitively answer the question before committing to an answer.
- **Strict Anti-Hallucination Guardrails**: The system rejects tangentially related documents and explicitly refuses to guess or infer information outside the provided text.
- **Jailbreak Prevention**: User queries are strictly quarantined in XML tags to prevent prompt injection attacks.
- **Inline Citations**: The LLM synthesizes cohesive narratives while meticulously citing its sources inline (e.g., `[1234.5678]`), which the frontend elegantly renders as clickable badges.
- **Extractive Fallback**: If no API key is provided, the system gracefully falls back to a local extractive mode, surfacing the most relevant abstracts directly.

---

## 🏗️ Architecture & Schema

**Architecture:**
- **Ingestion (`agy-ingest`)**: CLI tool that fetches papers from arXiv, sanitizes abstracts (`abstract` vs `abstract_raw`), and computes vector embeddings locally using `fastembed`.
- **API (`app.main`)**: FastAPI backend exposing endpoints for the RAG engine and unified analytics.
- **Database (`PostgreSQL + pgvector`)**: Handles relational joins and vector similarity search (hybrid search) natively.
- **Caching & Rate Limiting (`Redis`)**: Redis backs our `SlowAPI` tiered rate limiter (`5/minute`, `50/day` for LLM endpoints) and aggressively caches heavy statistical queries to ensure lightning-fast dashboard loads.

**Schema (Core Tables):**
- `papers`: Core metadata (ID, title, abstract).
- `authors` & `categories`: Unique records linked via join tables (`paper_authors`, `paper_categories`).
- `paper_embeddings`: 384-dimensional vector embeddings for semantic search.

---

## ⚡ Sample API Requests

**1. Dashboard Visualization Data (Cached)**
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

**2. RAG Search**
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

## 🏛️ Decisions & Trade-offs

This project was built with a philosophy of maintaining simplicity and avoiding premature optimization. Below are our key Architectural Decision Records (ADRs):

- [ADR 1: Why pgvector over Chroma](docs/adr/0001-pgvector-over-chroma.md)
- [ADR 2: Why no semantic chunking for abstracts](docs/adr/0002-no-semantic-chunking.md)
- [ADR 3: Why fastembed is the default embedder](docs/adr/0003-fastembed-default.md)

---

## ⚠️ Known Limitations
1. **Abstract-Only Context Window:** The RAG system embeds and retrieves only paper abstracts (~150 words). It cannot answer deep methodological questions buried in the full PDF body (e.g., hyperparameter choices, proof details). This is an intentional trade-off to keep embedding costs near-zero and latency under 50ms.
2. **Author Disambiguation:** Name variations like "J. Smith" and "John Smith" are treated as distinct authors. True disambiguation requires cross-referencing ORCID IDs or affiliation data, which arXiv's Atom API does not provide.
3. **arXiv Pagination Drift:** During large multi-hour crawls, newly published papers can shift pagination windows, potentially causing duplicates or gaps. The system mitigates this with in-run `seen_arxiv_ids` deduplication, but cannot fully prevent it without a stable cursor API.
4. **Sequential Ingestion:** The `agy-ingest` CLI fetches and embeds papers sequentially on a single thread to respect arXiv's strict 1-request-per-3-seconds rate limit. A 1,000-paper ingest takes ~50 minutes.
5. **Single LLM Provider:** The system uses Groq exclusively. If Groq is rate-limited or down, the only fallback is the local extractive mode (no LLM call), which surfaces raw abstracts without synthesis.
6. **Dense Vector Baseline Similarity:** The `bge-small-en-v1.5` model produces baseline cosine similarities of ~0.6–0.7 even for unrelated text. The relevance gate (`tau=0.75`) was empirically tuned to compensate, but edge cases near the threshold may still pass or be incorrectly filtered.

## 🔮 Future Improvements
1. **Full-Text PDF Ingestion:** Implement sliding-window chunking with overlap to ingest entire paper PDFs (via `pymupdf` or `unstructured`), enabling the RAG system to answer deep technical questions beyond abstracts.
2. **Background Indexing with Celery:** Offload `fastembed` computation and database writes to a Celery worker queue, freeing the CLI and enabling parallel ingestion of multiple categories.
3. **Multi-Model Routing:** Introduce a routing layer (e.g., LiteLLM) to seamlessly switch between Groq, OpenAI, and Anthropic based on availability, rate-limit exhaustion, or query complexity — with automatic fallback chains.
4. **Conversational Memory:** Add session-based conversation history so users can ask follow-up questions (e.g., "Tell me more about that last paper") without re-stating context.
5. **Re-Ranking with Cross-Encoders:** Add a lightweight cross-encoder re-ranker (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) between retrieval and generation to dramatically improve precision on ambiguous queries.
6. **Automated CI/CD Pipeline:** Add GitHub Actions for automated testing (via Testcontainers), Docker image builds, and deployment to a cloud provider on every push to `main`.

---

<div align="center">
  <b>Developed by Arafath</b><br>
  <a href="https://ahasanularafath.com">Visit my website</a>
</div>
