# Integration Surfaces

## Purpose

This document describes the public integration surfaces exposed by Garbage Collector as a memory substrate.

Garbage Collector is designed to remain independently usable. External systems should integrate through documented retrieval and storage surfaces rather than hidden coupling.

## Retrieval Interface

### HTTP retrieval surface

Current endpoint:

- `POST /api/retrieval/search`

Request shape:

- `query: str`
- `limit: int`

Response fields currently include:

| Field | Meaning | Required |
| --- | --- | --- |
| `item_id` | parent item identifier | yes |
| `item_type` | stored item type | yes |
| `item_title` | item title | yes |
| `source_url` | source URL when present | no |
| `source_filename` | source filename when present | no |
| `chunk_id` | retrieved chunk identifier | yes |
| `chunk_index` | chunk index within item | yes |
| `chunk_text` | chunk content | yes |
| `score` | retrieval score | yes |

### Direct storage fallback

Local integrations may also read from the existing SQLite schema:

- `items`
- `item_chunks`

This is a local development or infrastructure shortcut, not the preferred canonical integration path.

## Trace Persistence Options

### Existing generic item-ingest surface

Current endpoint:

- `POST /api/items`

This supports storing text content, including externally generated traces, but it is generic and not trace-specific.

### Direct SQLite insertion

Local integrations may store explicit trace rows in the existing `items` table.

This is acceptable for local development and prototyping, but it is not yet a first-class public trace API.

## Current Limitation For Case-Oriented Memory

Garbage Collector currently stores:

- documents
- notes
- URLs
- PDFs
- chunks

It does **not** yet expose a first-class case/outcome memory model for:

- prior adjudicated cases
- stable decision outcomes
- typed trace persistence with dedicated query surfaces

External systems such as Jigsaw may still use Garbage Collector as memory context, but they must map:

- retrieved items -> memory cases
- stored traces -> generic or typed stored items

## Recommended Integration Pattern

Recommended:

1. external system submits a retrieval query
2. Garbage Collector returns matching chunks or items
3. external system maps those results into its own memory contract
4. external system persists final traces through an explicit storage surface

Not recommended:

- embedding capability-layer logic inside Garbage Collector
- embedding judgment logic inside Garbage Collector
- relying on undocumented table assumptions as the long-term contract

## Proven Now

- Garbage Collector exposes usable retrieval surfaces
- it can serve as a practical memory substrate for external systems
- integration can happen without merging repos

## Not Yet Proven

- first-class prior-case retrieval with typed outcomes
- dedicated trace APIs for external decision systems
- finalized cross-repo persistence contracts
