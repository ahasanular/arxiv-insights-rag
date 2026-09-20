# arXiv Insight

A complete pipeline and API for ingesting arXiv research papers, storing them relationally, and querying them using a Retrieval-Augmented Generation (RAG) system.

---

## 🚀 Setup & Run

**1. Configure Environment**
```bash
cp .env.example .env
```

**2. Start Services**
```bash
docker compose up -d db redis
```

**3. Install Application (Locally)**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

**4. Ingest Papers**
```bash
agy-ingest ingest -c cat:cs.AI -m 100
```

**5. Start API & Dashboard**
```bash
uvicorn app.main:app --reload
```
- Dashboard: http://localhost:8000/
- Docs: http://localhost:8000/docs

---

## 🤖 Extractive RAG Mode (No API Key Required)

By default, the RAG API runs in **Extractive Mode**. If you do not provide an `LLM_API_KEY` in your `.env` file, the system will use local vector embeddings (`fastembed`) to search the database and extract the most relevant paper abstracts exactly as they appear in the text. 

If you provide an `LLM_API_KEY`, the system automatically upgrades to **Conversational Mode**, using an LLM to synthesize and summarize the retrieved context into a conversational answer.

---

## 🏗️ Architecture & Schema

**Architecture:**
- **Ingestion (`agy-ingest`):** CLI tool that fetches papers from arXiv, dedupes data, and computes vector embeddings locally using `fastembed`.
- **API (`app.main`):** FastAPI backend exposing endpoints for analytics (charts) and RAG (Hybrid Search).
- **Database (`PostgreSQL + pgvector`):** Handles relational joins and vector similarity search natively.

**Schema (Core Tables):**
- `papers`: Core metadata (ID, title, abstract).
- `authors` & `categories`: Unique records linked via join tables (`paper_authors`, `paper_categories`).
- `paper_embeddings`: 384-dimensional vector embeddings for semantic search.

---

## ⚡ Sample API Requests

**1. Analytics Aggregation**
```bash
curl -X GET "http://localhost:8000/api/v1/stats/papers-over-time?granularity=month"
```
```json
[
  { "period": "2026-09-01T00:00:00+00:00", "count": 42 }
]
```

**2. RAG Search**
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "Advancements in Transformers"}'
```
```json
{
  "answer": "Extracted context regarding Transformers...",
  "abstained": false,
  "sources": [
    {
      "arxiv_id": "2609.20751",
      "title": "Hybrid-Attention Language Models",
      "authors": ["Anton Xue", "Litu Rout"],
      "published_at": "2026-09-17T17:39:46+00:00",
      "score": 0.0328,
      "url": "https://arxiv.org/abs/2609.20751"
    }
  ]
}
```

---

## ⚠️ Known Limitations
1. **Author Over-merging:** "J. Smith" and "John Smith" are treated as distinct authors.
2. **Pagination Shifts:** arXiv's pagination can shift if new papers are published during a large crawl.

## 🔮 Future Improvements
1. **Background Indexing:** Use Celery to recompute embeddings without locking the database.
2. **LLM Citation Checking:** Add self-reflection to the LLM to verify its answer against the retrieved chunks, eliminating hallucinations.
3. **Advanced Chunking:** Implement semantic chunking for longer documents (full PDFs).
