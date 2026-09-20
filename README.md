# arXiv Insight

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
Because the CLI is packaged into the API container, you can ingest papers directly without installing Python locally:
```bash
docker compose exec api agy-ingest ingest -c cat:cs.AI -m 100
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

**1. Analytics Aggregation (Cached)**
```bash
curl -X GET "http://localhost:8000/api/v1/stats/authors-per-paper"
```
```json
{
  "data": [
    { "author_count": 1, "paper_count": 12 },
    { "author_count": 2, "paper_count": 45 }
  ],
  "meta": { "cached": true, "timestamp": "2026-09-21T00:00:00Z" }
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
1. **Author Over-merging:** Name variations like "J. Smith" and "John Smith" are currently treated as distinct authors without disambiguation.
2. **Pagination Shifts:** arXiv's pagination can shift if new papers are published during a large, multi-hour crawl.
3. **Single-Threaded Ingestion:** The `agy-ingest` CLI fetches and embeds papers sequentially on a single thread.
4. **Single LLM Provider:** The system strictly uses Groq without dynamic fallback or model-switching capabilities (e.g., automatically trying OpenAI if Groq goes down).
5. **RAG Context Constraints:** The RAG system only retrieves and reads abstracts, meaning it cannot answer highly specific methodological questions hidden deep inside the PDF bodies of the papers.

## 🔮 Future Improvements
1. **Background Indexing:** Shift local `fastembed` computation and database inserts into a Celery background worker to free up the CLI during massive multi-thousand paper ingests.
2. **Advanced Semantic Chunking:** Implement sliding-window chunking to ingest full PDF documents rather than just abstracts, providing deeper insights.
3. **Multi-Agent RAG**: Upgrade the LLM pipeline to a multi-agent system where a "Researcher" agent gathers context and a "Writer" agent synthesizes it.
4. **Multi-Model Routing:** Introduce LiteLLM or an internal routing layer to seamlessly switch between OpenAI, Groq, and Anthropic based on rate-limit exhaustion or specific query types.

---

<div align="center">
  <b>Developed by Arafath</b><br>
  <a href="https:/ahasanularafath.com">Visit my website</a>
</div>
