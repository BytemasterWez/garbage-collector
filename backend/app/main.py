from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, schemas
from .db import ensure_schema, get_db


# Create or upgrade the local SQLite schema automatically for this small app.
ensure_schema()

app = FastAPI(title="Garbage Collector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_item_detail(item) -> schemas.ItemDetail:
    """Create the parsed item-detail response shared by create and read routes."""
    return schemas.ItemDetail(
        id=item.id,
        item_type=item.item_type,
        source_url=item.source_url,
        source_filename=item.source_filename,
        title=item.title,
        content=item.content,
        metadata=schemas.ItemMetadata.model_validate(crud.parse_metadata_json(item)),
        entities=schemas.ItemEntities.model_validate(crud.parse_entities_json(item)),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@app.get("/api/health", response_model=schemas.HealthResponse)
def health_check() -> schemas.HealthResponse:
    """Simple route to confirm the backend is running."""
    return schemas.HealthResponse(status="ok")


@app.get("/api/items", response_model=list[schemas.ItemSummary])
def read_items(
    q: str | None = Query(default=None, description="Keyword search over title and content"),
    db: Session = Depends(get_db),
) -> list[schemas.ItemSummary]:
    """Return the library list, newest first."""
    items = crud.list_items(db, q)
    return [
        schemas.ItemSummary(
            id=item.id,
            item_type=item.item_type,
            source_url=item.source_url,
            source_filename=item.source_filename,
            title=item.title,
            preview=crud.build_preview(item.content),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@app.post("/api/items", response_model=schemas.ItemDetail, status_code=201)
def create_item(payload: schemas.ItemCreate, db: Session = Depends(get_db)) -> schemas.ItemDetail:
    """Save pasted text into local storage."""
    item = crud.create_item(db, payload.content)
    return build_item_detail(item)


@app.post("/api/items/from-url", response_model=schemas.ItemDetail, status_code=201)
def create_url_item(
    payload: schemas.UrlItemCreate, db: Session = Depends(get_db)
) -> schemas.ItemDetail:
    """Fetch a simple HTML page and store the extracted content locally."""
    try:
        item = crud.create_url_item(db, payload.url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return build_item_detail(item)


@app.post("/api/items/from-pdf", response_model=schemas.ItemDetail, status_code=201)
async def create_pdf_item(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> schemas.ItemDetail:
    """Store an uploaded PDF locally and extract text from text-based pages."""
    try:
        file_bytes = await file.read()
        item = crud.create_pdf_item(db, file.filename, file_bytes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return build_item_detail(item)


@app.get("/api/items/{item_id}", response_model=schemas.ItemDetail)
def read_item(item_id: int, db: Session = Depends(get_db)) -> schemas.ItemDetail:
    """Return one item for the detail view."""
    item = crud.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return build_item_detail(item)


@app.post("/api/retrieval/search", response_model=list[schemas.SemanticSearchResult])
def semantic_search(
    payload: schemas.SemanticSearchRequest, db: Session = Depends(get_db)
) -> list[schemas.SemanticSearchResult]:
    """Return ranked chunk matches using the local retrieval layer."""
    matches = crud.semantic_search(db, payload.query, limit=payload.limit)
    return [
        schemas.SemanticSearchResult(
            item_id=match.item.id,
            item_type=match.item.item_type,
            item_title=match.item.title,
            source_url=match.item.source_url,
            source_filename=match.item.source_filename,
            chunk_id=match.chunk.id,
            chunk_index=match.chunk.chunk_index,
            chunk_text=match.chunk.content,
            score=round(match.score, 4),
        )
        for match in matches
    ]
