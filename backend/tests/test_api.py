from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Run API tests against a temporary SQLite database file."""
    database_path = tmp_path / "test_garbage_collector.db"
    engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def create_item(client: TestClient, content: str) -> dict:
    """Helper to keep the test cases short and readable."""
    response = client.post("/api/items", json={"content": content})
    assert response.status_code == 201
    return response.json()


def test_create_item_returns_saved_payload(client: TestClient) -> None:
    response = client.post("/api/items", json={"content": "Budget ideas\n\nCompare side hustles."})

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Budget ideas"
    assert payload["content"] == "Budget ideas\n\nCompare side hustles."
    assert payload["id"] > 0


def test_list_items_returns_newest_first(client: TestClient) -> None:
    older_item = create_item(client, "Older item\n\nSaved first.")
    newer_item = create_item(client, "Newer item\n\nSaved second.")

    response = client.get("/api/items")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload[:2]] == [newer_item["id"], older_item["id"]]


def test_get_item_by_id_returns_full_content(client: TestClient) -> None:
    item = create_item(client, "Detail target\n\nFull note body.")

    response = client.get(f"/api/items/{item['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == item["id"]
    assert payload["content"] == "Detail target\n\nFull note body."


def test_search_returns_keyword_matches(client: TestClient) -> None:
    first_match = create_item(client, "Louisiana property\n\nHouse research notes.")
    matching_item = create_item(client, "Remote income\n\nLouisiana tax angle.")
    create_item(client, "Travel plans\n\nNothing related here.")

    response = client.get("/api/items", params={"q": "Louisiana"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [matching_item["id"], first_match["id"]]


def test_missing_item_returns_readable_error(client: TestClient) -> None:
    response = client.get("/api/items/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found."}


def test_create_url_item_fetches_and_stores_page_content(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MockResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = """
        <html>
          <head><title>Example Article</title></head>
          <body>
            <main>
              <h1>Example Article</h1>
              <p>Useful extracted paragraph.</p>
            </main>
          </body>
        </html>
        """

        def raise_for_status(self) -> None:
            return None

    def mock_get(url: str, headers: dict, timeout: int) -> MockResponse:
        assert url == "https://example.com/article"
        assert headers == crud.DEFAULT_REQUEST_HEADERS
        assert timeout == crud.REQUEST_TIMEOUT_SECONDS
        return MockResponse()

    monkeypatch.setattr(crud.requests, "get", mock_get)

    response = client.post("/api/items/from-url", json={"url": "https://example.com/article"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["item_type"] == "url"
    assert payload["source_url"] == "https://example.com/article"
    assert payload["title"] == "Example Article"
    assert "Useful extracted paragraph." in payload["content"]


def test_create_url_item_returns_readable_error_for_unreachable_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def mock_get(url: str, headers: dict, timeout: int) -> None:
        raise crud.requests.exceptions.ConnectionError("network down")

    monkeypatch.setattr(crud.requests, "get", mock_get)

    response = client.post("/api/items/from-url", json={"url": "https://example.com/article"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Could not reach that URL. Check the address and try again."
    }


def build_text_pdf_bytes(lines: list[str]) -> bytes:
    """Create a simple text PDF in memory for upload tests."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    y_position = 760
    for line in lines:
        pdf.drawString(72, y_position, line)
        y_position -= 20
    pdf.save()
    return buffer.getvalue()


def test_create_pdf_item_saves_text_based_pdf(client: TestClient) -> None:
    pdf_bytes = build_text_pdf_bytes(["Sample PDF Title", "Extracted PDF body text."])

    response = client.post(
        "/api/items/from-pdf",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["item_type"] == "pdf"
    assert payload["source_filename"] == "sample.pdf"
    assert payload["title"] == "sample.pdf"
    assert "Sample PDF Title" in payload["content"]
    assert "Extracted PDF body text." in payload["content"]


def test_create_pdf_item_returns_readable_error_for_invalid_pdf(client: TestClient) -> None:
    response = client.post(
        "/api/items/from-pdf",
        files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file could not be read as a PDF."}
