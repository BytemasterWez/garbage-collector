from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crud
from .embeddings import get_default_embedding_provider
from .goals_store import load_goals
from .models import ItemChunk
from .retrieval import cosine_similarity

GOAL_MATCH_THRESHOLD = 0.72
GOAL_WEAK_MATCH_THRESHOLD = 0.45


def run_goal_alignment(db: Session, item_id: int) -> dict[str, Any]:
    """Compare one stored item against the local goal list using current corpus signals."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise ValueError("Item not found.")

    goals = load_goals()
    item_chunks = db.scalars(
        select(ItemChunk).where(ItemChunk.item_id == item_id).order_by(ItemChunk.chunk_index.asc())
    ).all()
    metadata = crud.parse_metadata_json(item)
    entities = crud.parse_entities_json(item)
    related = crud.list_related_items(db, item_id, limit=3)
    provider = get_default_embedding_provider()

    item_text = item.content.lower()
    item_vector = provider.embed_text(item.content)
    related_text = " ".join(
        f"{related_item['title']} {related_item['matching_chunk_preview']}" for related_item in related
    ).lower()
    entity_text = " ".join(
        entities["people"] + entities["organizations"] + entities["places"] + entities["dates"]
    ).lower()

    matches: list[dict[str, Any]] = []

    for goal in goals:
        goal_text = build_goal_text(goal["name"], goal["description"])
        goal_vector = provider.embed_text(goal_text)
        item_similarity = cosine_similarity(item_vector, goal_vector)
        best_chunk, chunk_similarity = find_best_matching_chunk(item_chunks, goal_vector)
        keyword_boost = compute_keyword_boost(item_text, entity_text, related_text, goal)
        combined_score = min(1.0, (item_similarity * 0.42) + (chunk_similarity * 0.4) + keyword_boost)

        if best_chunk is None:
            continue

        evidence = {
            "evidence_type": "chunk",
            "source_id": f"gc:chunk:{best_chunk.id}",
            "source_item_id": f"gc:item:{item.id}",
            "snippet": best_chunk.content_preview or crud.build_preview(best_chunk.content, max_length=220),
            "relevance": round(chunk_similarity, 3),
            "confidence": round(min(1.0, 0.45 + (chunk_similarity * 0.4) + (keyword_boost * 0.2)), 3),
            "observed_at": item.updated_at.astimezone(UTC).isoformat(),
            "provenance": {
                "source_system": "garbage-collector",
                "item_id": item.id,
                "chunk_id": best_chunk.id,
                "embedding_model": best_chunk.embedding_model,
            },
        }

        matches.append(
            {
                "goal": goal,
                "score": round(combined_score, 3),
                "item_similarity": round(item_similarity, 3),
                "chunk_similarity": round(chunk_similarity, 3),
                "keyword_boost": round(keyword_boost, 3),
                "evidence": evidence,
            }
        )

    matches.sort(key=lambda match: match["score"], reverse=True)
    top_matches = matches[:3]

    if top_matches:
        strongest_score = float(top_matches[0]["score"])
        classification = classify_score(strongest_score)
        evidence = [match["evidence"] for match in top_matches]
        score = strongest_score
    else:
        classification = "no_match"
        evidence = []
        score = 0.0

    confidence = compute_confidence(
        evidence=evidence,
        related_count=len(related),
        entity_count=sum(len(values) for values in entities.values()),
        metadata=metadata,
        score=score,
    )

    matched_targets = [
        {
            "target_id": match["goal"]["id"],
            "label": match["goal"]["name"],
            "strength": match["score"],
        }
        for match in top_matches
        if match["score"] >= GOAL_WEAK_MATCH_THRESHOLD
    ]

    result = {
        "contract_version": "kernel.v1",
        "engine_name": "goal_alignment",
        "subject": {
            "subject_type": "item",
            "subject_id": f"gc:item:{item.id}",
        },
        "summary": build_summary(classification, matched_targets),
        "classification": classification,
        "score": round(score, 3),
        "confidence": confidence,
        "rationale": build_rationale(classification, top_matches, related),
        "evidence": evidence,
        "signals": {
            "relevance": round(score, 3),
            "novelty": compute_novelty_signal(related),
            "actionability": compute_actionability_signal(item_text, metadata, matched_targets),
            "recurrence": compute_recurrence_signal(related),
        },
        "outputs": {
            "matched_targets": matched_targets,
            "recommended_action": recommend_action(classification, confidence),
            "tags": build_tags(matched_targets),
        },
        "provenance": {
            "generated_at": utc_now(),
            "source_system": "garbage-collector",
            "engine_version": "goal_alignment.v1",
        },
    }
    return result


def build_goal_text(name: str, description: str) -> str:
    return "\n".join(part.strip() for part in [name, description] if part.strip())


def find_best_matching_chunk(item_chunks: list[ItemChunk], goal_vector: list[float]) -> tuple[ItemChunk | None, float]:
    best_chunk: ItemChunk | None = None
    best_score = 0.0

    for chunk in item_chunks:
        chunk_vector = json.loads(chunk.embedding_vector_json)
        similarity = cosine_similarity(goal_vector, chunk_vector)
        if similarity > best_score:
            best_chunk = chunk
            best_score = similarity

    return best_chunk, best_score


def compute_keyword_boost(
    item_text: str, entity_text: str, related_text: str, goal: dict[str, str]
) -> float:
    goal_terms = tokenize(f"{goal['name']} {goal['description']}")
    if not goal_terms:
        return 0.0

    direct_hits = sum(1 for term in goal_terms if term in item_text)
    entity_hits = sum(1 for term in goal_terms if term in entity_text)
    related_hits = sum(1 for term in goal_terms if term in related_text)
    boost = (direct_hits * 0.1) + (entity_hits * 0.03) + (related_hits * 0.02)
    return min(0.4, boost)


def classify_score(score: float) -> str:
    if score >= GOAL_MATCH_THRESHOLD:
        return "match"
    if score >= GOAL_WEAK_MATCH_THRESHOLD:
        return "weak_match"
    return "no_match"


def compute_confidence(
    *,
    evidence: list[dict[str, Any]],
    related_count: int,
    entity_count: int,
    metadata: dict[str, Any],
    score: float,
) -> float:
    provenance_coverage = (
        sum(1 for record in evidence if record.get("provenance")) / len(evidence) if evidence else 0.0
    )
    evidence_depth = min(1.0, len(evidence) / 3)
    structure_signal = 0.0
    if metadata.get("word_count", 0) >= 40:
        structure_signal += 0.1
    if entity_count > 0:
        structure_signal += 0.08
    if related_count > 0:
        structure_signal += 0.08

    confidence = (evidence_depth * 0.32) + (provenance_coverage * 0.28) + (score * 0.18) + structure_signal
    return round(min(0.98, confidence), 3)


def compute_novelty_signal(related: list[dict[str, object]]) -> float:
    if not related:
        return 0.82

    avg_related_score = sum(float(item["score"]) for item in related) / len(related)
    return round(max(0.05, min(0.95, 1.0 - avg_related_score)), 3)


def compute_actionability_signal(
    item_text: str, metadata: dict[str, Any], matched_targets: list[dict[str, Any]]
) -> float:
    action_terms = {"plan", "compare", "build", "pilot", "service", "move", "income", "automation"}
    hits = sum(1 for term in action_terms if term in item_text)
    signal = min(0.7, hits * 0.09)
    if metadata.get("word_count", 0) >= 30:
        signal += 0.1
    if matched_targets:
        signal += 0.1
    return round(min(0.95, signal), 3)


def compute_recurrence_signal(related: list[dict[str, object]]) -> float:
    if not related:
        return 0.12

    strongest_related = max(float(item["score"]) for item in related)
    return round(min(0.95, strongest_related), 3)


def build_summary(classification: str, matched_targets: list[dict[str, Any]]) -> str:
    if not matched_targets:
        return "This item does not show strong alignment with the current local goals."

    top_target = matched_targets[0]["label"]
    if classification == "match":
        return f"Strong alignment with the '{top_target}' goal."
    if classification == "weak_match":
        return f"Possible alignment with the '{top_target}' goal, but the evidence is weaker."
    return f"No strong goal alignment was found for '{top_target}'."


def build_rationale(
    classification: str, top_matches: list[dict[str, Any]], related: list[dict[str, object]]
) -> str:
    if not top_matches:
        return "The current item did not produce enough grounded similarity or keyword evidence to support a goal match."

    strongest = top_matches[0]
    goal_name = strongest["goal"]["name"]
    if classification == "match":
        return (
            f"The strongest grounded signal aligns with '{goal_name}', supported by a high-scoring chunk match "
            f"and reinforcing corpus terms."
        )
    if classification == "weak_match":
        return (
            f"The item shows some grounded overlap with '{goal_name}', but the strongest evidence remains partial "
            f"and should be reviewed rather than trusted automatically."
        )
    return (
        f"The item produced only weak overlap with '{goal_name}', and the current evidence is not strong enough "
        f"to justify a positive alignment."
    )


def recommend_action(classification: str, confidence: float) -> str:
    if classification == "match" and confidence >= 0.55:
        return "review"
    if classification == "weak_match":
        return "hold"
    return "ignore"


def build_tags(matched_targets: list[dict[str, Any]]) -> list[str]:
    tags = ["goal-alignment"]
    for target in matched_targets:
        tags.append(target["target_id"].replace(":", "-"))
    return tags


def tokenize(value: str) -> list[str]:
    return [part.strip(".,:;()[]{}!?\"'").lower() for part in value.split() if len(part.strip()) >= 4]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
