# Use local virtual environment
PYTHON = PYTHONPATH=src .venv/bin/python
BIN = .venv/bin

.PHONY: up down build logs ingest reindex wipe status eval test

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# CLI commands
ingest:
	$(PYTHON) -m app.cli ingest

reindex:
	$(PYTHON) -m app.cli reindex

wipe:
	$(PYTHON) -m app.cli wipe

status:
	$(PYTHON) -m app.cli status

eval:
	$(PYTHON) -m app.cli eval

# Dev commands
test:
	PYTHONPATH=src $(BIN)/pytest
