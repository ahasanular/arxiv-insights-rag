from typing import Protocol, runtime_checkable

import structlog
from fastembed import TextEmbedding

logger = structlog.get_logger()


@runtime_checkable
class EmbedderProtocol(Protocol):
    """
    Protocol for embedding services. Any class implementing embed_texts()
    and exposing model_name can be used interchangeably — production fastembed,
    mock for tests, or a future OpenAI embedder.
    """

    model_name: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class EmbedderService:
    """
    Production embedder using FastEmbed. Model is loaded lazily on first
    call to avoid blocking import time.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        if self._model is None:
            logger.info("Initializing fastembed model", model=self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Takes a list of strings and returns a list of embedding vectors.
        """
        if not texts:
            return []

        # TextEmbedding.embed returns a generator of numpy arrays
        embeddings = list(self.model.embed(texts))

        # Convert numpy arrays to standard python lists for pgvector
        return [e.tolist() for e in embeddings]
