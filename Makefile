.PHONY: up down build logs ingest test eval wipe lint format check

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# CLI commands (run inside uv environment)
ingest:
	uv run python -m app.cli ingest

reindex:
	uv run python -m app.cli reindex

wipe:
	uv run python -m app.cli wipe

status:
	uv run python -m app.cli status

eval:
	uv run python -m app.cli eval

# Dev commands
test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint format
	uv run mypy .
