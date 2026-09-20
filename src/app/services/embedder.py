import structlog
from fastembed import TextEmbedding

logger = structlog.get_logger()


class EmbedderService:
    """
    Singleton-like wrapper for FastEmbed to ensure the model is loaded
    lazily and only once in the process.
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
