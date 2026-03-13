from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Item(Base):
    """Stored text item for the thin-slice library."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_type: Mapped[str] = mapped_column(Text, nullable=False, default="pasted_text")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    stored_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_items_item_type", "item_type"),
        Index("ix_items_source_url", "source_url"),
        Index("ix_items_source_filename", "source_filename"),
        Index("ix_items_title", "title"),
        Index("ix_items_content", "content"),
    )


class ItemChunk(Base):
    """Chunked item content with a stored embedding vector for retrieval."""

    __tablename__ = "item_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_preview: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_item_chunks_item_id", "item_id"),
        Index("ix_item_chunks_item_id_chunk_index", "item_id", "chunk_index"),
    )
