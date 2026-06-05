"""sentence-transformers EmbeddingProvider implementation."""

from __future__ import annotations

from loguru import logger
from sentence_transformers import SentenceTransformer

from core.interfaces.embedder import EmbeddingProvider

__all__ = ["SentenceTransformerEmbedder"]


DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
DEFAULT_DEVICE = "cpu"
DEFAULT_NORMALIZE = True


class SentenceTransformerEmbedder(EmbeddingProvider):
    """Synchronous sentence-transformers adapter.

    The adapter loads the model in ``__init__``. This is intentionally
    synchronous; application code should bridge it with ``asyncio.to_thread``
    when constructing it from an async context.

    Runtime values are provided through the constructor; this adapter does not
    read application settings directly.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str = DEFAULT_DEVICE,
        normalize: bool = DEFAULT_NORMALIZE,
    ) -> None:
        """Initialize the embedder and load the model.

        Args:
            model_name: HuggingFace model identifier.
            device: PyTorch device string such as ``"cpu"`` or ``"cuda"``.
            normalize: If True, L2-normalize output embeddings.

        Raises:
            ValueError: If ``model_name`` strips to empty, or if the loaded
                model does not report an embedding dimension.
        """
        if not model_name.strip():
            raise ValueError("model_name must be non-empty (after strip)")

        logger.info(
            "Loading sentence-transformer model: model_name={} device={}",
            model_name,
            device,
        )
        self._model = SentenceTransformer(model_name, device=device)
        self._normalize = normalize

        dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError(f"model dimension is unavailable for model_name={model_name!r}")
        self._dimension: int = dimension

        logger.info(
            "Model loaded: model_name={} dimension={} normalize={}",
            model_name,
            self._dimension,
            normalize,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch encode texts to embedding vectors."""
        if not texts:
            return []

        vectors = self._model.encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        return vectors.tolist()

    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension
