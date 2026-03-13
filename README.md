# Garbage Collector

Garbage Collector is a localhost web app for saving pasted text into a small personal library.

## Thin slice

This first slice intentionally includes only:

- pasted text ingestion
- URL ingestion
- PDF ingestion
- local storage with SQLite
- library/list view
- item detail view
- keyword search

This slice intentionally excludes desktop packaging, embeddings, semantic search, chat, OCR-heavy PDF handling, and images.

## Current Verified Status

Thin-slice phase 3 is complete for pasted text, narrow URL ingestion, and narrow PDF ingestion.

Verified working:

- backend starts locally and serves the API
- frontend starts locally through Vite
- create item works from the browser UI
- URL save works for basic HTML pages
- URL save has been verified against simple static pages including `http://example.com` and `https://example.com`
- PDF upload works for text-based PDFs
- PDF upload has been verified with multiple text-based sample PDFs
- library refreshes after create
- the newly created item auto-selects
- the detail panel updates for the selected item
- URL-backed items show their source URL in detail view
- PDF-backed items show their original filename in detail view
- keyword search filters the library
- search works across `pasted_text`, `url`, and `pdf` item types
- backend-down failures show a readable message
- malformed URLs return a readable validation error
- unreachable URLs return a readable fetch error
- unreadable or textless PDFs return readable extraction errors
- repeated PDF uploads with the same original filename are stored under unique local file paths
- missing items return a readable `Item not found.` error
- the live browser app loads without obvious console/runtime errors in normal use

Verified on 2026-03-13 with a live FastAPI server, a live Vite dev server, real browser interaction, backend tests, a small varied URL check, and multiple text-based PDF uploads.

Not built yet:

- image ingestion
- embeddings or semantic search
- chat or analysis features
- desktop packaging

Current URL ingestion limits:

- only simple HTTP/HTTPS HTML pages are supported
- JavaScript-heavy pages are not supported yet
- some real sites may still fail depending on redirects, blocking rules, or environment-specific SSL/network behavior

Current PDF ingestion limits:

- only text-based PDFs are supported
- image-only PDFs are not supported yet
- OCR is not included
- tables and layout reconstruction are not included
- some PDFs may extract imperfectly depending on how text is encoded inside the file
- blank or effectively textless PDFs return a readable extraction error instead of being stored as usable content

## Product Direction Note

This repository is currently building the core engine and a thin localhost web shell first.

The intended later product direction is a desktop-style drag-and-drop experience with a stronger personality layer. That future direction may include:

- a central drag-and-drop target
- a "trash man" or garbage can visual identity
- simple ingest animations on drop
- occasional speech-bubble notifications for meaningful findings
- nudges tied to detected patterns, recurring themes, or user-defined interests and goals

This is a design-direction reference only.

Do not implement that layer yet. For now, keep building the core engine and basic UI, and preserve the architecture so a richer interaction layer can be added later without rewriting the backend.

## SSL Fallback Note

The backend currently retries URL fetches once without certificate verification only when the initial request fails with an SSL certificate verification error on this local machine.

This is a temporary environment-specific accommodation, not the intended long-term trust model. It is deliberately narrow and should be revisited before treating remote fetches as production-grade.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite, Uvicorn
- Frontend: React, TypeScript, Vite

## Run the backend

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will run on `http://127.0.0.1:8000`.

## Run the frontend

Install Node.js first if it is not already available, then run:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

The web app will run on `http://127.0.0.1:5173`.

## Minimal Backend Tests

Run the thin-slice API tests with:

```powershell
cd backend
python -m pytest
```
