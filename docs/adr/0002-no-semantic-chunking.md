# ADR 2: Why no semantic chunking for abstracts

## Context
Standard RAG pipelines often involve "chunking" large documents into smaller, overlapping segments (e.g., using a sliding window of 500 tokens) before generating embeddings. This ensures that the context provided to the LLM is highly relevant and fits within context limits.

## Decision
We chose **not** to implement semantic chunking for the arXiv dataset, and instead embed each paper's title and abstract as a single, contiguous document.

## Rationale
1. **Natural Semantic Units:** arXiv abstracts are typically around 150-250 words long. They are already dense, highly structured, and represent a single coherent semantic unit.
2. **Dilution Risk:** Slicing a 200-word abstract into multiple overlapping 50-word chunks risks separating the methodology from the results, or the problem statement from the proposed solution. This dilutes the embedding quality.
3. **Simplicity & Performance:** Skipping chunking eliminates the need to manage chunk boundary logic, reduces embedding computation time, and keeps the vector database small and perfectly 1:1 with the relational tables.

## Consequences
- If we later expand the scope to ingest full PDFs (which can be 10,000+ words), we will *have* to introduce a chunking strategy. The schema anticipates this by including a `chunk_index` column, ensuring it will only be a configuration change rather than a structural database migration.
