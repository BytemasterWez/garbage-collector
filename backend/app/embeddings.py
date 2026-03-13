import logging
import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Small boundary so embedding generation can be replaced later."""

    model_name: str
    vector_dimensions: int

    def embed_text(self, text: str) -> list[float]:
        """Return one normalized vector for a text block."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized vectors for multiple text blocks."""


class SentenceTransformerEmbeddingProvider:
    """A thin wrapper around one stable sentence-transformer model."""

    def __init__(
        self,
        *,
        model_name: str = EMBEDDING_MODEL_NAME,
        vector_dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        self.model_name = model_name
        self.vector_dimensions = vector_dimensions
        self.cache_folder = os.getenv("SENTENCE_TRANSFORMERS_HOME", "").strip() or None
        self._model: SentenceTransformer | None = None

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._load_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def _load_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model

        logger.warning(
            "Loading embedding model '%s'. First use may download model files and cache them locally. Cache behavior: %s",
            self.model_name,
            describe_cache_behavior(),
        )
        self._model = SentenceTransformer(
            self.model_name,
            cache_folder=self.cache_folder,
        )
        loaded_dimensions = self._model.get_sentence_embedding_dimension()

        logger.info(
            "Loaded embedding model '%s' with %s dimensions.",
            self.model_name,
            loaded_dimensions,
        )
        if loaded_dimensions != self.vector_dimensions:
            raise RuntimeError(
                f"Expected {self.vector_dimensions} embedding dimensions but loaded {loaded_dimensions}."
            )

        return self._model


def describe_cache_behavior() -> str:
    """Return a readable summary of where model files will be cached."""
    sentence_transformers_home = os.getenv("SENTENCE_TRANSFORMERS_HOME", "").strip()
    hf_home = os.getenv("HF_HOME", "").strip()

    if sentence_transformers_home:
        return f"SENTENCE_TRANSFORMERS_HOME={sentence_transformers_home}"
    if hf_home:
        return f"HF_HOME={hf_home}"
    return "default Hugging Face cache"


@lru_cache(maxsize=1)
def get_default_embedding_provider() -> EmbeddingProvider:
    """Return the single stable local provider for this phase."""
    return SentenceTransformerEmbeddingProvider()
