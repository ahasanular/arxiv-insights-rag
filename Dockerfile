# Build stage
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt ./

# Upgrade pip and install dependencies into a wheelhouse/virtual environment
RUN python -m venv /app/.venv
RUN /app/.venv/bin/pip install --default-timeout=1000 --no-cache-dir -U pip setuptools wheel
RUN /app/.venv/bin/pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Download embedding model weights to bake into image
# Doing this in builder so it caches well
ENV HF_HOME=/app/model_cache
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY . .
# Install the project itself (which registers agy-ingest in .venv/bin)
RUN /app/.venv/bin/pip install --default-timeout=1000 --no-cache-dir -e .

# Final stage
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN useradd -m -U appuser

WORKDIR /app

# Copy virtualenv and app from builder
COPY --from=builder --chown=appuser:appuser /app /app
# Copy model cache
COPY --from=builder --chown=appuser:appuser /app/model_cache /app/model_cache
ENV HF_HOME=/app/model_cache

# Switch to non-root
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
