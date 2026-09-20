# Developer Guide

Welcome to the arXiv Insight developer guide. This document outlines the project architecture, the development workflow, and the pre-commit checks required to maintain code quality.

## 🏗 Architecture Overview

The system consists of three primary components:
1. **Data Ingestion (`agy-ingest`)**: A CLI tool that fetches papers from the arXiv API, parses the XML, generates 384-dimensional dense vectors locally using `fastembed` (`BAAI/bge-small-en-v1.5`), and inserts them into the database.
2. **PostgreSQL Database (`pgvector`)**: Stores relational metadata (authors, categories) and dense vector embeddings. Uses Reciprocal Rank Fusion (RRF) to combine traditional Full-Text Search (BM25) with Cosine Similarity vector search.
3. **Redis**: Powers our `SlowAPI` tiered rate limiter to prevent abuse and aggressively caches heavy statistical dashboard queries for instant load times.
4. **FastAPI Backend (`app.main`)**: Serves the REST API, the Advanced RAG endpoints (powered exclusively by Groq via the `llama3-70b-8192` model), and the static HTML/CSS/JS frontend.

## 📁 Project Structure

```text
.
├── docker-compose.yml       # Production/Local Docker orchestration
├── Dockerfile               # Builds the unified API + Ingestion container
├── Makefile                 # Shortcuts for all common developer commands
├── pyproject.toml           # The SINGLE Source of Truth for dependencies & config
├── migrations/              # Alembic database migrations
└── src/
    └── app/
        ├── api/             # FastAPI routers and Pydantic schemas
        ├── db/              # SQLAlchemy models, repositories, and session management
        ├── services/        # Core business logic (RAG, LLM, Ingestion, Evaluation)
        ├── static/          # HTML, CSS, and Vanilla JS frontend
        ├── cli.py           # Typer CLI entrypoint (`agy-ingest`)
        └── main.py          # FastAPI application entrypoint
```

## 🛠 Development Workflow

### 1. Environment Setup
We use standard Python packaging via `pip` and `pyproject.toml`.
```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install the project in editable mode WITH developer dependencies
pip install -e ".[dev]"

# 3. Spin up the local database and redis
make up
```

### 2. Making Database Changes
If you need to change the database schema (e.g., adding a new column to `papers`):
1. Modify the SQLAlchemy models in `src/app/db/models.py`.
2. Generate a new Alembic migration:
   ```bash
   alembic revision --autogenerate -m "Add new column"
   ```
3. The `migrate` container will automatically apply this migration the next time you run `docker compose up --build`.

### 3. Modifying the Frontend
The frontend is written in pure HTML/CSS/Vanilla JS and is located in `src/app/static/index.html`.
- Because the `Dockerfile` and local environment install the project in "editable" mode (`pip install -e .`), any changes you make to `index.html` are instantly reflected upon browser refresh.

### 4. Running the Pipeline Locally
To test the full RAG pipeline locally:
```bash
# 1. Ingest papers
make ingest

# 2. Start the API locally (or use Docker)
uvicorn app.main:app --reload

# 3. Test the RAG Evaluation metrics
make eval
```

## ✅ Pre-Commit Checks

Before you commit any code, you must ensure it passes all our strict quality gates. We use `Makefile` shortcuts to make this easy.

Run these checks in order:

1. **Format the code (Auto-fixes issues):**
   ```bash
   make format
   ```
2. **Type-Check the code (Strict Mypy):**
   ```bash
   make check
   ```
3. **Run Unit Tests:**
   ```bash
   make test
   ```
4. **Run RAG Evaluation:**
   If you modified `rag.py`, `evaluation.py`, or any database query logic, you must ensure the retrieval metrics have not degraded.
   ```bash
   make eval
   ```
   *(Ensure Recall@5, MRR, and Abstention Precision remain high).*

Once all of the above commands pass cleanly, your code is ready to be committed and pushed! CI will enforce these exact same checks on GitHub.
