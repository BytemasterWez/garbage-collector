import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Item, ItemChunk


@dataclass
class ChunkRecord:
    """Prepared chunk data before it is stored by the vector backend."""

    chunk_index: int
    content: str
    content_preview: str
    character_count: int


@dataclass
class ChunkSearchMatch:
    """Search result with both the stored chunk and its parent item."""

    chunk: ItemChunk
    item: Item
    score: float


class VectorStoreBackend(Protocol):
    """Boundary for storing and searching vectors independently from chunking."""

    def replace_item_vectors(
        self,
        db: Session,
        *,
        item_id: int,
        chunks: list[ChunkRecord],
        vectors: list[list[float]],
        embedding_model: str,
    ) -> None:
        """Replace stored vectors for a single item."""

    def search(
        self, db: Session, *, query_vector: list[float], limit: int
    ) -> list[ChunkSearchMatch]:
        """Return ranked chunk matches for a query vector."""


class SqliteJsonVectorStore:
    """SQLite-backed vector store that hides JSON serialization from the rest of the app."""

    def replace_item_vectors(
        self,
        db: Session,
        *,
        item_id: int,
        chunks: list[ChunkRecord],
        vectors: list[list[float]],
        embedding_model: str,
    ) -> None:
        db.execute(delete(ItemChunk).where(ItemChunk.item_id == item_id))

        for chunk, vector in zip(chunks, vectors, strict=True):
            db.add(
                ItemChunk(
                    item_id=item_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    content_preview=chunk.content_preview,
                    character_count=chunk.character_count,
                    embedding_model=embedding_model,
                    embedding_vector_json=json.dumps(vector),
                )
            )

    def search(
        self, db: Session, *, query_vector: list[float], limit: int
    ) -> list[ChunkSearchMatch]:
        if not any(query_vector):
            return []

        statement = select(ItemChunk, Item).join(Item, ItemChunk.item_id == Item.id)
        matches: list[ChunkSearchMatch] = []

        for chunk, item in db.execute(statement):
            chunk_vector = json.loads(chunk.embedding_vector_json)
            score = cosine_similarity(query_vector, chunk_vector)
            if score <= 0:
                continue

            matches.append(ChunkSearchMatch(chunk=chunk, item=item, score=score))

        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[:limit]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between normalized vectors."""
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))


def get_default_vector_store() -> VectorStoreBackend:
    """Return the current SQLite adapter for stored vectors."""
    return SqliteJsonVectorStore()
