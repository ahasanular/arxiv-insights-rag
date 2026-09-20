# ADR 3: Why fastembed is the default embedder

## Context
To power the vector search in our RAG pipeline, we must convert text abstracts into dense vectors. The industry default is often to use cloud APIs like OpenAI's `text-embedding-3-small`. However, relying entirely on a cloud API introduces costs, network latency, and requires API keys out of the box.

## Decision
We selected `fastembed` using the `BAAI/bge-small-en-v1.5` model (384 dimensions) running locally via ONNX as our default embedding provider, with OpenAI available as an optional drop-in replacement.

## Rationale
1. **Zero-Setup Developer Experience:** By defaulting to a local, CPU-optimized ONNX model, any reviewer or developer can clone the repository and run the entire ingestion and retrieval pipeline without needing to sign up for API keys or incur costs.
2. **Performance:** `fastembed` is heavily optimized for CPU execution. For the short lengths of arXiv abstracts, local embedding is significantly faster than establishing an HTTPS connection to a cloud provider, completely eliminating network round-trips.
3. **Determinism:** Local models guarantee that the embeddings generated today will be identical to those generated next year, without worrying about model deprecation on the provider's end.

## Consequences
- The Docker image size increases slightly to accommodate the model weights.
- `BAAI/bge-small-en-v1.5` is highly performant but maxes out at 512 tokens. This is perfectly adequate for our abstracts, but limits our ability to embed larger texts without chunking or changing models.
