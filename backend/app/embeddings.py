import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
EMBEDDING_DIMENSIONS = 256


class EmbeddingProvider(Protocol):
    """Small boundary so embedding generation can be replaced later."""

    model_name: str

    def embed_text(self, text: str) -> list[float]:
        """Return one normalized vector for a text block."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized vectors for multiple text blocks."""


class LocalHashEmbeddingProvider:
    """A deterministic local embedding approximation for early retrieval work."""

    model_name = "local-hash-v1"

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        terms = extract_terms(text)

        if not terms:
            return vector

        for term in terms:
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        return normalize_vector(vector)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


def extract_terms(text: str) -> list[str]:
    """Use unigrams and bigrams so related phrases share more signal."""
    tokens = TOKEN_PATTERN.findall(text.lower())
    if not tokens:
        return []

    terms = list(tokens)
    if len(tokens) > 1:
        terms.extend(f"{left}_{right}" for left, right in zip(tokens, tokens[1:]))
    return terms


def normalize_vector(vector: list[float]) -> list[float]:
    """Normalize vectors so cosine similarity works with a dot product."""
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def get_default_embedding_provider() -> EmbeddingProvider:
    """Return the single stable local provider for this phase."""
    return LocalHashEmbeddingProvider()
