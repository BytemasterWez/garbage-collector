from dataclasses import dataclass

from sqlalchemy.orm import Session

from .chat_adapter import (
    ChatAdapter,
    ChatAdapterError,
    ChatAdapterNotConfiguredError,
    get_default_chat_adapter,
)
from .crud import semantic_search
from .retrieval import ChunkSearchMatch

DEFAULT_CHAT_RETRIEVAL_LIMIT = 5


@dataclass
class GroundedSource:
    """Retrieved source chunk prepared for prompting and UI citations."""

    source_id: str
    item_id: int
    item_type: str
    item_title: str
    source_url: str | None
    source_filename: str | None
    chunk_id: int
    chunk_index: int
    chunk_text: str
    score: float


@dataclass
class GroundedChatAnswer:
    """Final grounded chat response returned by the backend."""

    answer: str
    citations: list[GroundedSource]


def answer_question(
    db: Session,
    question: str,
    *,
    retrieval_limit: int = DEFAULT_CHAT_RETRIEVAL_LIMIT,
    chat_adapter: ChatAdapter | None = None,
) -> GroundedChatAnswer:
    """Answer one question using only retrieved chunks as grounding."""
    matches = semantic_search(db, question, limit=retrieval_limit)
    if not matches:
        return GroundedChatAnswer(
            answer="I could not find enough grounded material in your saved items to answer that question.",
            citations=[],
        )

    adapter = chat_adapter or get_default_chat_adapter()
    sources = build_grounded_sources(matches)
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(question, sources)
    completion = adapter.answer(system_prompt=system_prompt, user_prompt=user_prompt)
    citations = resolve_citations(completion.citation_ids, sources)

    if not citations:
        return GroundedChatAnswer(
            answer="I could not produce a grounded answer from the retrieved material.",
            citations=[],
        )

    return GroundedChatAnswer(answer=completion.answer, citations=citations)


def build_grounded_sources(matches: list[ChunkSearchMatch]) -> list[GroundedSource]:
    """Assign stable source ids so the model can only cite retrieved chunks."""
    sources: list[GroundedSource] = []

    for index, match in enumerate(matches, start=1):
        sources.append(
            GroundedSource(
                source_id=f"S{index}",
                item_id=match.item.id,
                item_type=match.item.item_type,
                item_title=match.item.title,
                source_url=match.item.source_url,
                source_filename=match.item.source_filename,
                chunk_id=match.chunk.id,
                chunk_index=match.chunk.chunk_index,
                chunk_text=match.chunk.content,
                score=match.score,
            )
        )

    return sources


def build_system_prompt() -> str:
    """Tell the model to stay grounded and return strict JSON."""
    return (
        "You are a grounded retrieval assistant. "
        "Answer using only the provided source chunks. "
        "If the sources are insufficient, say so plainly. "
        "Do not use outside knowledge. "
        "Return strict JSON with this shape: "
        '{"answer": "string", "citation_ids": ["S1", "S2"]}. '
        "Only cite source ids that were provided."
    )


def build_user_prompt(question: str, sources: list[GroundedSource]) -> str:
    """Build a readable grounded prompt with source ids and source text."""
    source_blocks = []

    for source in sources:
        source_blocks.append(
            "\n".join(
                [
                    f"{source.source_id}",
                    f"Item title: {source.item_title}",
                    f"Item type: {source.item_type}",
                    f"Chunk index: {source.chunk_index}",
                    f"Score: {source.score:.4f}",
                    f"Chunk text: {source.chunk_text}",
                ]
            )
        )

    return "\n\n".join(
        [
            f"Question: {question.strip()}",
            "Use only the following retrieved sources:",
            "\n\n".join(source_blocks),
        ]
    )


def resolve_citations(citation_ids: list[str], sources: list[GroundedSource]) -> list[GroundedSource]:
    """Keep only citations that refer to real retrieved chunks."""
    source_map = {source.source_id: source for source in sources}
    ordered: list[GroundedSource] = []
    seen: set[str] = set()

    for citation_id in citation_ids:
        if citation_id in seen or citation_id not in source_map:
            continue
        ordered.append(source_map[citation_id])
        seen.add(citation_id)

    return ordered
