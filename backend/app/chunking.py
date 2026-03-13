import re

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MIN_CHUNK_LENGTH = 80


def normalize_text_for_chunking(text: str) -> str:
    """Collapse noisy whitespace so chunk boundaries stay predictable."""
    return re.sub(r"\s+", " ", text).strip()


def split_text_into_chunks(text: str) -> list[str]:
    """Split extracted item text into small overlapping windows for retrieval."""
    normalized = normalize_text_for_chunking(text)
    if not normalized:
        return []

    if len(normalized) <= CHUNK_SIZE:
        return [normalized]

    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        target_end = min(start + CHUNK_SIZE, len(normalized))
        end = target_end

        if target_end < len(normalized):
            boundary = normalized.rfind(" ", start + max(1, CHUNK_SIZE - 200), target_end)
            if boundary > start:
                end = boundary

        chunk = normalized[start:end].strip()
        if chunk and (len(chunk) >= MIN_CHUNK_LENGTH or not chunks):
            chunks.append(chunk)

        if end >= len(normalized):
            break

        next_start = max(0, end - CHUNK_OVERLAP)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks
