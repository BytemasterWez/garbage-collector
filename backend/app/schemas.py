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


class ItemDetail(BaseModel):
    """Full item shape for the detail view."""

    id: int
    item_type: str
    source_url: str | None = None
    source_filename: str | None = None
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Basic health endpoint response."""

    status: str
