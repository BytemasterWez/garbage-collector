import json
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .db import PDF_STORAGE_DIR
from .models import Item

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": "GarbageCollector/0.2 (+http://localhost)"
}
REQUEST_TIMEOUT_SECONDS = 10

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
    item = Item(item_type="pasted_text", title=derive_title(content), content=content)
    enrich_item(item, item_type="pasted_text", content=content)
    db.add(item)
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

    item = Item(
        item_type="url",
        source_url=normalized_url,
        title=title,
        content=content,
    )
    enrich_item(item, item_type="url", content=content, source_url=normalized_url)
    db.add(item)
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
    db.commit()
    db.refresh(item)
    return item


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
