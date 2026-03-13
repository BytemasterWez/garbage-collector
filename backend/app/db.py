from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Keep the SQLite database in the backend folder so it is easy to find locally.
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "garbage_collector.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
STORAGE_DIR = BASE_DIR / "storage"
PDF_STORAGE_DIR = STORAGE_DIR / "pdfs"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


# `check_same_thread=False` is the normal SQLite setting for FastAPI apps.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_schema_for_engine(target_engine: Engine) -> None:
    """Create tables and add missing SQLite columns for small local upgrades."""
    from .models import Item  # Import here to avoid circular imports during module load.

    Base.metadata.create_all(bind=target_engine)

    inspector = inspect(target_engine)
    if "items" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("items")}
    statements: list[str] = []

    if "item_type" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'pasted_text'")

    if "source_url" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN source_url TEXT")

    if "source_filename" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN source_filename TEXT")

    if "stored_file_path" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN stored_file_path TEXT")

    if "metadata_json" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN metadata_json TEXT")

    if "entities_json" not in existing_columns:
        statements.append("ALTER TABLE items ADD COLUMN entities_json TEXT")

    if not statements:
        return

    PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    with target_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_schema() -> None:
    """Create tables and add missing SQLite columns for the app database."""
    ensure_schema_for_engine(engine)


def get_db():
    """Yield a database session per request and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
