# Kernel Contract v1

## Purpose

`kernel.v1` is the shared result shape for Phase 8 analysis engines in Garbage Collector.

It is designed to stay:

- small
- explicit
- portable
- evidence-based
- compatible with Arbiter judgment mapping
- consumable by Jigsaw later without redesign

Goal Alignment is the first reference engine using this contract.

## Frozen JSON Example

```json
{
  "contract_version": "kernel.v1",
  "engine_name": "goal_alignment",
  "subject": {
    "subject_type": "item",
    "subject_id": "gc:item:123"
  },
  "summary": "Strong alignment with the user's remote income goal.",
  "classification": "match",
  "score": 0.84,
  "confidence": 0.78,
  "rationale": "The item discusses automation workflows, client delivery, and repeatable systems tied to remote income generation.",
  "evidence": [
    {
      "evidence_type": "chunk",
      "source_id": "gc:chunk:456",
      "source_item_id": "gc:item:123",
      "snippet": "Build repeatable workflow automation services for remote clients...",
      "relevance": 0.87,
      "confidence": 0.82,
      "observed_at": "2026-03-13T12:00:00Z",
      "provenance": {
        "source_system": "garbage-collector"
      }
    }
  ],
  "signals": {
    "relevance": 0.84,
    "novelty": 0.31,
    "actionability": 0.76,
    "recurrence": 0.44
  },
  "outputs": {
    "matched_targets": [
      {
        "target_id": "goal:remote-income",
        "label": "Remote income",
        "strength": 0.84
      }
    ],
    "recommended_action": "review",
    "tags": [
      "goal-match",
      "remote-income",
      "workflow-automation"
    ]
  },
  "provenance": {
    "generated_at": "2026-03-13T12:00:00Z",
    "source_system": "garbage-collector",
    "engine_version": "goal_alignment.v1"
  }
}
```

## Field Definitions

### `contract_version`

Stable contract identifier. For this phase it must be `kernel.v1`.

### `engine_name`

Stable engine identifier such as `goal_alignment`.

### `subject`

The object being evaluated.

- `subject_type`: generic type label such as `item`
- `subject_id`: stable identifier such as `gc:item:123`

### `summary`

Short operator-facing top line for the judgment.

### `classification`

Categorical result label for the engine.

For the first Goal Alignment engine, allowed values are:

- `match`
- `weak_match`
- `no_match`

### `score`

Normalized result strength from `0.0` to `1.0`.

This measures how strong the match or judgment is.

### `confidence`

Normalized confidence from `0.0` to `1.0`.

This measures how confident the engine is in its own assessment.

`score` and `confidence` must not be treated as the same thing.

### `rationale`

Short grounded explanation for why the engine produced the result.

### `evidence`

List of grounded supporting records used by the engine.

Each evidence object should include:

- `evidence_type`
- `source_id`
- `source_item_id`
- `snippet`
- `relevance`
- `confidence`
- `observed_at`
- `provenance`

Required additional evidence fields for `kernel.v1`:

- `observed_at`: timestamp used for recency-aware downstream mapping
- `confidence`: evidence-level confidence estimate
- `provenance`: source-system and origin metadata

### `signals`

Reusable normalized primitives for later composition and judgment.

Initial signal set:

- `relevance`
- `novelty`
- `actionability`
- `recurrence`

### `outputs`

Engine-specific payload area.

For Goal Alignment this may include:

- `matched_targets`
- `recommended_action`
- `tags`

Initial allowed `outputs.recommended_action` values:

- `review`
- `hold`
- `ignore`

### `provenance`

Top-level generation metadata for auditability.

Should include:

- `generated_at`
- `source_system`
- `engine_version`

## Mapping Notes

### Arbiter Compatibility

`kernel.v1` is not Arbiter's public request schema, but it maps cleanly into it.

Typical mappings:

- `subject.subject_id` -> `candidate_id`
- `summary` -> `summary`
- `score` -> `evidence.fit_score`
- evidence count / unique evidence sources -> `evidence.source_count`
- newest `evidence[*].observed_at` -> `evidence.freshness_days`
- `confidence` -> Arbiter confidence input or supporting judgment context
- `rationale` -> `reason_summary` or supporting judgment context
- `outputs.recommended_action` -> downstream action recommendation

### Jigsaw Consumption

Jigsaw can consume `kernel.v1` outputs without changing its architecture because the contract already carries:

- explicit subject identity
- classification
- score
- confidence
- grounded evidence
- rationale
- reusable signals
- provenance

That makes `kernel.v1` suitable as a portable engine result shape rather than a Garbage-Collector-only format.

## Scope Note

This contract is frozen for the first Phase 8 engine pass.

Do not broaden it before Goal Alignment is implemented and evaluated against this shape.
