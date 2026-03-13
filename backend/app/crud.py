import json
import logging
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .chunking import split_text_into_chunks
from .db import PDF_STORAGE_DIR
from .embeddings import EmbeddingProvider, get_default_embedding_provider
from .models import Item, ItemChunk
from .retrieval import (
    ChunkRecord,
    ChunkSearchMatch,
    VectorStoreBackend,
    cosine_similarity,
    get_default_vector_store,
)

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "GarbageCollector/0.2 (+http://localhost)"
}
REQUEST_TIMEOUT_SECONDS = 10
SEMANTIC_RESULT_LIMIT = 8
RELATED_ITEM_LIMIT = 5

# Local Windows Python installs sometimes miss certificate chain setup.
# For this personal localhost tool, retrying once without verification is a pragmatic fallback.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_PATTERN = "|".join(MONTH_NAMES)
DATE_PATTERNS = (
    re.compile(rf"\b(?:{MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(rf"\b\d{{1,2}}\s+(?:{MONTH_PATTERN})\s+\d{{4}}\b"),
)
ORG_SUFFIX_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,4}\s+"
    r"(?:Inc|LLC|Ltd|Corp|Corporation|Company|University|Bank|Agency|Committee))\b"
)
PERSON_PATTERN = re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")
PLACE_TERMS = {
    "Louisiana",
    "New Orleans",
    "Texas",
    "California",
    "New York",
    "London",
    "Paris",
    "United States",
    "England",
}
logger = logging.getLogger(__name__)


def derive_title(content: str) -> str:
    """Use the first non-empty line as the title and keep it short."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:80]
    return content.strip()[:80]


def build_preview(content: str, max_length: int = 160) -> str:
    """Create a short single-line preview for the list view."""
    compact = " ".join(content.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def dedupe_preserving_order(values: list[str]) -> list[str]:
    """Keep the first appearance of each extracted value."""
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def build_metadata(
    content: str,
    item_type: str,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> dict[str, str | int | None]:
    """Compute small, explainable metadata for any stored item."""
    lines = [line for line in content.splitlines() if line.strip()]
    parsed_url = urlparse(source_url) if source_url else None

    return {
        "item_type": item_type,
        "word_count": len(content.split()),
        "character_count": len(content),
        "line_count": len(lines),
        "hostname": parsed_url.netloc if parsed_url else None,
        "source_filename": source_filename,
    }


def extract_dates(text: str) -> list[str]:
    """Extract only a few clear date formats."""
    matches: list[str] = []
    for pattern in DATE_PATTERNS:
        matches.extend(pattern.findall(text))
    return dedupe_preserving_order(matches)


def extract_organizations(text: str) -> list[str]:
    """Extract organizations conservatively using suffix-based matches."""
    return dedupe_preserving_order(ORG_SUFFIX_PATTERN.findall(text))


def extract_people(text: str) -> list[str]:
    """Extract people conservatively only when a title is present."""
    return dedupe_preserving_order(PERSON_PATTERN.findall(text))


def extract_places(text: str) -> list[str]:
    """Extract only a small conservative place set for this phase."""
    matches = [place for place in PLACE_TERMS if re.search(rf"\b{re.escape(place)}\b", text)]
    return dedupe_preserving_order(matches)


def build_entities(text: str) -> dict[str, list[str]]:
    """Build conservative entity buckets with precision over recall."""
    return {
        "people": extract_people(text),
        "organizations": extract_organizations(text),
        "places": extract_places(text),
        "dates": extract_dates(text),
    }


def serialize_json(data: dict[str, object]) -> str:
    """Store JSON deterministically for easier debugging."""
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def enrich_item(
    item: Item,
    *,
    item_type: str,
    content: str,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> None:
    """Attach metadata and entities to a newly created item."""
    item.metadata_json = serialize_json(
        build_metadata(
            content=content,
            item_type=item_type,
            source_url=source_url,
            source_filename=source_filename,
        )
    )
    item.entities_json = serialize_json(build_entities(content))


def parse_metadata_json(item: Item) -> dict[str, object]:
    """Return parsed metadata for API responses."""
    if item.metadata_json:
        return json.loads(item.metadata_json)

    return build_metadata(
        content=item.content,
        item_type=item.item_type,
        source_url=item.source_url,
        source_filename=item.source_filename,
    )


def parse_entities_json(item: Item) -> dict[str, list[str]]:
    """Return parsed entities for API responses."""
    if item.entities_json:
        return json.loads(item.entities_json)

    return build_entities(item.content)


def create_item(db: Session, content: str) -> Item:
    """Insert a new item into SQLite."""
    provider = get_default_embedding_provider()
    backend = get_default_vector_store()
    backfill_missing_item_chunks(db, embedding_provider=provider, vector_store=backend)

    item = Item(item_type="pasted_text", title=derive_title(content), content=content)
    enrich_item(item, item_type="pasted_text", content=content)
    db.add(item)
    db.flush()
    sync_item_chunks(db, item, embedding_provider=provider, vector_store=backend)
    db.commit()
    db.refresh(item)
    return item


def normalize_url(url: str) -> str:
    """Validate that the URL uses a simple supported HTTP scheme."""
    candidate = url.strip()
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a full http:// or https:// URL.")

    return candidate


def extract_text_from_html(html: str) -> tuple[str, str]:
    """Extract a basic title and visible page text from fetched HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in ("script", "style", "noscript"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    raw_text = soup.get_text(separator="\n")
    cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    content = "\n".join(cleaned_lines)

    if not content:
        raise ValueError("This page did not contain readable text content.")

    title = page_title or derive_title(content)
    return title[:200], content


def fetch_url_content(url: str) -> tuple[str, str]:
    """Fetch a URL and return a simple extracted title and text body."""
    normalized_url = normalize_url(url)

    try:
        response = requests.get(
            normalized_url,
            headers=DEFAULT_REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.SSLError:
        try:
            response = requests.get(
                normalized_url,
                headers=DEFAULT_REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=False,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            raise ValueError("Could not reach that URL. Check the address and try again.") from error
    except requests.exceptions.Timeout as error:
        raise ValueError("The URL request timed out. Try another page.") from error
    except requests.exceptions.HTTPError as error:
        raise ValueError(f"The page returned HTTP {response.status_code}.") from error
    except requests.exceptions.RequestException as error:
        raise ValueError("Could not reach that URL. Check the address and try again.") from error

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        raise ValueError("Only basic HTML pages are supported right now.")

    return extract_text_from_html(response.text)


def create_url_item(db: Session, url: str) -> Item:
    """Fetch a URL, extract simple text, and store it as a library item."""
    normalized_url = normalize_url(url)
    title, content = fetch_url_content(normalized_url)
    provider = get_default_embedding_provider()
    backend = get_default_vector_store()
    backfill_missing_item_chunks(db, embedding_provider=provider, vector_store=backend)

    item = Item(
        item_type="url",
        source_url=normalized_url,
        title=title,
        content=content,
    )
    enrich_item(item, item_type="url", content=content, source_url=normalized_url)
    db.add(item)
    db.flush()
    sync_item_chunks(db, item, embedding_provider=provider, vector_store=backend)
    db.commit()
    db.refresh(item)
    return item


def normalize_pdf_filename(filename: str | None) -> str:
    """Keep a user-facing filename while rejecting missing or non-PDF uploads."""
    if not filename:
        raise ValueError("Choose a PDF file before uploading.")

    cleaned = Path(filename).name.strip()
    if not cleaned.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported right now.")

    return cleaned


def store_pdf_file(filename: str, file_bytes: bytes) -> Path:
    """Persist the uploaded PDF locally under a unique name."""
    PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = PDF_STORAGE_DIR / f"{uuid4().hex}-{filename}"
    stored_path.write_bytes(file_bytes)
    return stored_path


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from a text-based PDF using pypdf."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as error:
        raise ValueError("The uploaded file could not be read as a PDF.") from error

    page_text: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        cleaned = extracted.strip()
        if cleaned:
            page_text.append(cleaned)

    combined_text = "\n\n".join(page_text).strip()
    if not combined_text:
        raise ValueError("This PDF did not contain extractable text. Image-only PDFs are not supported yet.")

    return combined_text


def create_pdf_item(db: Session, filename: str, file_bytes: bytes) -> Item:
    """Save the original PDF locally, extract text, and create a library item."""
    normalized_filename = normalize_pdf_filename(filename)
    provider = get_default_embedding_provider()
    backend = get_default_vector_store()
    backfill_missing_item_chunks(db, embedding_provider=provider, vector_store=backend)

    if not file_bytes:
        raise ValueError("The uploaded PDF was empty.")

    try:
        stored_path = store_pdf_file(normalized_filename, file_bytes)
    except OSError as error:
        raise ValueError("The PDF could not be stored locally.") from error

    try:
        extracted_text = extract_text_from_pdf(stored_path)
    except ValueError:
        stored_path.unlink(missing_ok=True)
        raise

    item = Item(
        item_type="pdf",
        source_filename=normalized_filename,
        stored_file_path=str(stored_path),
        title=normalized_filename,
        content=extracted_text,
    )
    enrich_item(
        item,
        item_type="pdf",
        content=extracted_text,
        source_filename=normalized_filename,
    )
    db.add(item)
    db.flush()
    sync_item_chunks(db, item, embedding_provider=provider, vector_store=backend)
    db.commit()
    db.refresh(item)
    return item


def build_chunk_records(content: str) -> list[ChunkRecord]:
    """Create chunk records from one item's text content."""
    return [
        ChunkRecord(
            chunk_index=index,
            content=chunk_text,
            content_preview=build_preview(chunk_text, max_length=220),
            character_count=len(chunk_text),
        )
        for index, chunk_text in enumerate(split_text_into_chunks(content))
    ]


def sync_item_chunks(
    db: Session,
    item: Item,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStoreBackend | None = None,
) -> None:
    """Regenerate chunks and embeddings for a single item."""
    prepared_chunks = build_chunk_records(item.content)
    provider = embedding_provider or get_default_embedding_provider()
    backend = vector_store or get_default_vector_store()

    if not prepared_chunks:
        db.query(ItemChunk).filter(ItemChunk.item_id == item.id).delete()
        return

    vectors = provider.embed_texts([chunk.content for chunk in prepared_chunks])
    backend.replace_item_vectors(
        db,
        item_id=item.id,
        chunks=prepared_chunks,
        vectors=vectors,
        embedding_model=provider.model_name,
    )


def backfill_missing_item_chunks(
    db: Session,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStoreBackend | None = None,
) -> None:
    """Rebuild missing or stale chunk embeddings so one model is used consistently."""
    provider = embedding_provider or get_default_embedding_provider()
    backend = vector_store or get_default_vector_store()
    items = db.scalars(select(Item).order_by(Item.id.asc())).all()
    stale_items = [item for item in items if item_needs_chunk_rebuild(db, item, provider)]

    if not stale_items:
        return

    logger.warning(
        "Rebuilding chunk embeddings for %s items using model '%s'.",
        len(stale_items),
        provider.model_name,
    )

    for item in stale_items:
        sync_item_chunks(
            db,
            item,
            embedding_provider=provider,
            vector_store=backend,
        )

    db.commit()
    logger.info(
        "Finished rebuilding chunk embeddings for %s items using model '%s'.",
        len(stale_items),
        provider.model_name,
    )


def item_needs_chunk_rebuild(db: Session, item: Item, provider: EmbeddingProvider) -> bool:
    """Detect stale vectors so old hash embeddings never mix with the upgraded model."""
    existing_chunks = db.scalars(
        select(ItemChunk).where(ItemChunk.item_id == item.id).order_by(ItemChunk.chunk_index.asc())
    ).all()
    expected_chunk_count = len(build_chunk_records(item.content))

    if not existing_chunks:
        return expected_chunk_count > 0

    if len(existing_chunks) != expected_chunk_count:
        return True

    for chunk in existing_chunks:
        if chunk.embedding_model != provider.model_name:
            return True

        try:
            vector = json.loads(chunk.embedding_vector_json)
        except json.JSONDecodeError:
            return True

        if not isinstance(vector, list) or len(vector) != provider.vector_dimensions:
            return True

    return False


def semantic_search(
    db: Session,
    query: str,
    *,
    limit: int = SEMANTIC_RESULT_LIMIT,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStoreBackend | None = None,
) -> list[ChunkSearchMatch]:
    """Run chunk-level semantic retrieval across all indexed items."""
    provider = embedding_provider or get_default_embedding_provider()
    backend = vector_store or get_default_vector_store()

    backfill_missing_item_chunks(db, embedding_provider=provider, vector_store=backend)
    query_vector = provider.embed_text(query)
    return backend.search(db, query_vector=query_vector, limit=limit)


def list_related_items(
    db: Session,
    item_id: int,
    limit: int = RELATED_ITEM_LIMIT,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store: VectorStoreBackend | None = None,
) -> list[dict[str, object]]:
    """Find similar items by comparing the selected item's chunks to other item chunks."""
    provider = embedding_provider or get_default_embedding_provider()
    backend = vector_store or get_default_vector_store()
    backfill_missing_item_chunks(db, embedding_provider=provider, vector_store=backend)

    source_item = get_item(db, item_id)
    if source_item is None:
        raise ValueError("Item not found.")

    source_chunks = db.scalars(
        select(ItemChunk).where(ItemChunk.item_id == item_id).order_by(ItemChunk.chunk_index.asc())
    ).all()
    if not source_chunks:
        return []

    other_rows = db.execute(
        select(ItemChunk, Item)
        .join(Item, ItemChunk.item_id == Item.id)
        .where(ItemChunk.item_id != item_id)
        .order_by(Item.created_at.desc())
    ).all()

    best_matches: dict[int, dict[str, object]] = {}

    for source_chunk in source_chunks:
        source_vector = json.loads(source_chunk.embedding_vector_json)

        for related_chunk, related_item in other_rows:
            related_vector = json.loads(related_chunk.embedding_vector_json)
            score = cosine_similarity(source_vector, related_vector)
            if score <= 0:
                continue

            current_best = best_matches.get(related_item.id)
            if current_best is not None and score <= float(current_best["score"]):
                continue

            preview = related_chunk.content_preview or build_preview(related_chunk.content, max_length=160)
            best_matches[related_item.id] = {
                "item_id": related_item.id,
                "item_type": related_item.item_type,
                "title": related_item.title,
                "source_url": related_item.source_url,
                "source_filename": related_item.source_filename,
                "score": score,
                "reason": f"Top matching chunk: {preview}",
                "matching_chunk_preview": preview,
            }

    ranked_matches = sorted(
        best_matches.values(),
        key=lambda match: float(match["score"]),
        reverse=True,
    )
    return ranked_matches[:limit]


def list_items(db: Session, query: str | None = None) -> list[Item]:
    """Return newest items first, optionally filtered by a keyword."""
    statement = select(Item).order_by(Item.created_at.desc())

    if query:
        search_term = f"%{query.strip()}%"
        statement = (
            select(Item)
            .where(or_(Item.title.ilike(search_term), Item.content.ilike(search_term)))
            .order_by(Item.created_at.desc())
        )

    return list(db.scalars(statement))


def get_item(db: Session, item_id: int) -> Item | None:
    """Fetch a single item by its primary key."""
    return db.get(Item, item_id)


def count_chunks_for_item(db: Session, item_id: int) -> int:
    """Small helper for tests and future diagnostics."""
    return int(
        db.scalar(select(func.count()).select_from(ItemChunk).where(ItemChunk.item_id == item_id)) or 0
    )
