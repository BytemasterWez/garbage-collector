from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ItemCreate(BaseModel):
    """Payload for saving pasted text into the library."""

    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace-only submissions early."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Content must not be blank.")
        return cleaned


class UrlItemCreate(BaseModel):
    """Payload for fetching and saving a URL-backed item."""

    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def url_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("URL must not be blank.")
        return cleaned


class SemanticSearchRequest(BaseModel):
    """Payload for chunk-level semantic retrieval."""

    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Search query must not be blank.")
        return cleaned


class ItemSummary(BaseModel):
    """Compact item shape for the library view."""

    id: int
    item_type: str
    source_url: str | None = None
    source_filename: str | None = None
    title: str
    preview: str
    created_at: datetime
    updated_at: datetime


class ItemMetadata(BaseModel):
    """Parsed lightweight metadata for display and later enrichment phases."""

    item_type: str
    word_count: int
    character_count: int
    line_count: int
    hostname: str | None = None
    source_filename: str | None = None


class ItemEntities(BaseModel):
    """Conservative rule-based entity buckets."""

    people: list[str]
    organizations: list[str]
    places: list[str]
    dates: list[str]


class ItemDetail(BaseModel):
    """Full item shape for the detail view."""

    id: int
    item_type: str
    source_url: str | None = None
    source_filename: str | None = None
    title: str
    content: str
    metadata: ItemMetadata
    entities: ItemEntities
    created_at: datetime
    updated_at: datetime


class SemanticSearchResult(BaseModel):
    """Ranked semantic retrieval match at the chunk level."""

    item_id: int
    item_type: str
    item_title: str
    source_url: str | None = None
    source_filename: str | None = None
    chunk_id: int
    chunk_index: int
    chunk_text: str
    score: float


class HealthResponse(BaseModel):
    """Basic health endpoint response."""

    status: str
