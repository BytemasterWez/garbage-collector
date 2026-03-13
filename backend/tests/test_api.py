import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app import grounded_chat
from app.chat_adapter import ChatCompletionResult
from app.db import Base, ensure_schema_for_engine, get_db
from app.main import app


class FakeEmbeddingProvider:
    """Fast deterministic provider so tests stay local and do not download models."""

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    vector_dimensions = 384

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        keywords = ("louisiana", "insurance", "property", "remote", "workflow", "automation", "flood")

        for text in texts:
            lowered = text.lower()
            vector = [0.0] * self.vector_dimensions
            for index, keyword in enumerate(keywords):
                vector[index] = float(lowered.count(keyword))

            magnitude = sum(value * value for value in vector) ** 0.5
            if magnitude:
                vector = [value / magnitude for value in vector]

            vectors.append(vector)

        return vectors


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests fast by replacing the real sentence-transformer provider."""
    monkeypatch.setattr(crud, "get_default_embedding_provider", lambda: FakeEmbeddingProvider())


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


def open_test_db() -> tuple[Session, Iterator[Session]]:
    """Open the temporary test database session from the dependency override."""
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    return db, generator


def test_create_item_returns_saved_payload(client: TestClient) -> None:
    response = client.post("/api/items", json={"content": "Budget ideas\n\nCompare side hustles."})

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Budget ideas"
    assert payload["content"] == "Budget ideas\n\nCompare side hustles."
    assert payload["id"] > 0
    assert payload["metadata"]["item_type"] == "pasted_text"
    assert payload["metadata"]["word_count"] == 5
    assert payload["entities"]["people"] == []
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
              <p>Useful extracted paragraph for OpenAI Inc in Louisiana on 2026-03-13.</p>
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
    assert "Useful extracted paragraph" in payload["content"]
    assert payload["metadata"]["hostname"] == "example.com"
    assert payload["entities"]["organizations"] == ["OpenAI Inc"]
    assert payload["entities"]["places"] == ["Louisiana"]
    assert payload["entities"]["dates"] == ["2026-03-13"]


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
    assert payload["metadata"]["source_filename"] == "sample.pdf"


def test_create_pdf_item_returns_readable_error_for_invalid_pdf(client: TestClient) -> None:
    response = client.post(
        "/api/items/from-pdf",
        files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file could not be read as a PDF."}


def test_schema_upgrade_adds_phase_4_columns_for_existing_database(tmp_path: Path) -> None:
    """Verify a pre-upgrade SQLite file gains the newer thin-slice columns safely."""
    database_path = tmp_path / "legacy_garbage_collector.db"
    legacy_engine = create_engine(
        f"sqlite:///{database_path}", connect_args={"check_same_thread": False}
    )

    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )

    ensure_schema_for_engine(legacy_engine)

    inspector = inspect(legacy_engine)
    columns = {column["name"] for column in inspector.get_columns("items")}

    assert "item_type" in columns
    assert "source_url" in columns
    assert "source_filename" in columns
    assert "stored_file_path" in columns
    assert "metadata_json" in columns
    assert "entities_json" in columns


def test_create_flows_generate_chunk_rows_for_retrieval(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class MockResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = "<html><head><title>Chunked URL</title></head><body><p>Remote income systems note.</p></body></html>"

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(crud.requests, "get", lambda url, headers, timeout: MockResponse())

    pasted_item = create_item(client, "Chunked note\n\nLouisiana property insurance planning.")

    url_response = client.post("/api/items/from-url", json={"url": "https://example.com/chunk"})
    assert url_response.status_code == 201

    pdf_bytes = build_text_pdf_bytes(["Chunked PDF", "Remote income planning for Louisiana."])
    pdf_response = client.post(
        "/api/items/from-pdf",
        files={"file": ("chunked.pdf", pdf_bytes, "application/pdf")},
    )
    assert pdf_response.status_code == 201

    db, generator = open_test_db()
    try:
        assert crud.count_chunks_for_item(db, pasted_item["id"]) > 0
        assert crud.count_chunks_for_item(db, url_response.json()["id"]) > 0
        assert crud.count_chunks_for_item(db, pdf_response.json()["id"]) > 0
    finally:
        generator.close()


def test_semantic_search_returns_ranked_chunk_matches(client: TestClient) -> None:
    create_item(client, "Louisiana property insurance\n\nCompare insurers and flood policy notes.")
    create_item(client, "Remote income systems\n\nBuild better workflow automation.")

    response = client.post(
        "/api/retrieval/search",
        json={"query": "property insurance in Louisiana", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert payload[0]["item_title"] == "Louisiana property insurance"
    assert payload[0]["item_type"] == "pasted_text"
    assert "chunk_text" in payload[0]
    assert payload[0]["score"] > 0


def test_semantic_search_backfills_chunks_for_existing_items_without_index(client: TestClient) -> None:
    db, generator = open_test_db()
    try:
        legacy_item = crud.create_item(db, "Legacy retrieval note\n\nLouisiana taxes and insurance.")
        db.query(crud.ItemChunk).filter(crud.ItemChunk.item_id == legacy_item.id).delete()
        db.commit()
        assert crud.count_chunks_for_item(db, legacy_item.id) == 0
    finally:
        generator.close()

    response = client.post(
        "/api/retrieval/search",
        json={"query": "Louisiana insurance", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(match["item_id"] == legacy_item.id for match in payload)

    db, generator = open_test_db()
    try:
        assert crud.count_chunks_for_item(db, legacy_item.id) > 0
    finally:
        generator.close()


def test_chat_returns_readable_error_when_model_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_item(client, "Grounded note\n\nLouisiana insurance planning.")

    def missing_adapter():
        raise grounded_chat.ChatAdapterNotConfiguredError(
            "No chat model is configured. Set GC_LLM_MODEL and restart the backend."
        )

    monkeypatch.setattr(grounded_chat, "get_default_chat_adapter", missing_adapter)

    response = client.post("/api/chat/answer", json={"question": "What does this say about Louisiana?"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "No chat model is configured. Set GC_LLM_MODEL and restart the backend."
    }


def test_chat_returns_grounded_no_answer_when_no_chunks_match(client: TestClient) -> None:
    response = client.post("/api/chat/answer", json={"question": "Tell me about orbital mechanics."})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "I could not find enough grounded material in your saved items to answer that question.",
        "citations": [],
    }


def test_chat_returns_answer_and_citations_from_retrieved_chunks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_item(client, "Louisiana property insurance\n\nFlood policy notes and insurer comparisons.")

    class FakeChatAdapter:
        model_name = "fake-grounded-model"

        def answer(self, *, system_prompt: str, user_prompt: str) -> ChatCompletionResult:
            assert "Louisiana property insurance" in user_prompt
            assert '"citation_ids": ["S1", "S2"]' in system_prompt
            return ChatCompletionResult(
                answer="The saved material focuses on Louisiana property insurance and flood policy comparisons.",
                citation_ids=["S1"],
            )

    monkeypatch.setattr(grounded_chat, "get_default_chat_adapter", lambda: FakeChatAdapter())

    response = client.post(
        "/api/chat/answer",
        json={"question": "What does the saved material say about Louisiana property insurance?", "retrieval_limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Louisiana property insurance" in payload["answer"]
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["source_id"] == "S1"
    assert payload["citations"][0]["item_title"] == "Louisiana property insurance"


def test_related_items_returns_ranked_similar_items_without_self_match(client: TestClient) -> None:
    selected = create_item(
        client,
        "Louisiana property insurance\n\nFlood policy notes and insurer comparisons.",
    )
    strongest_match = create_item(
        client,
        "Louisiana flood insurance\n\nCompare policy costs and insurer coverage.",
    )
    create_item(client, "Remote workflow systems\n\nAutomation ideas for consulting projects.")

    response = client.get(f"/api/items/{selected['id']}/related")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert all(match["item_id"] != selected["id"] for match in payload)
    assert payload[0]["item_id"] == strongest_match["id"]
    assert payload[0]["score"] > 0
    assert payload[0]["reason"].startswith("Top matching chunk:")
    assert payload[0]["matching_chunk_preview"]


def test_related_items_returns_readable_missing_item_error(client: TestClient) -> None:
    response = client.get("/api/items/999999/related")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found."}


def test_semantic_search_rebuilds_stale_hash_embeddings_before_search(client: TestClient) -> None:
    item = create_item(client, "Louisiana property insurance\n\nFlood policy notes and insurer comparisons.")

    db, generator = open_test_db()
    try:
        chunk = db.query(crud.ItemChunk).filter(crud.ItemChunk.item_id == item["id"]).first()
        assert chunk is not None
        chunk.embedding_model = "local-hash-v1"
        chunk.embedding_vector_json = json.dumps([0.1, 0.2, 0.3])
        db.commit()
    finally:
        generator.close()

    response = client.post(
        "/api/retrieval/search",
        json={"query": "property insurance in Louisiana", "limit": 5},
    )

    assert response.status_code == 200

    db, generator = open_test_db()
    try:
        repaired_chunks = db.query(crud.ItemChunk).filter(crud.ItemChunk.item_id == item["id"]).all()
        assert repaired_chunks
        assert all(chunk.embedding_model == "sentence-transformers/all-MiniLM-L6-v2" for chunk in repaired_chunks)
        assert all(len(json.loads(chunk.embedding_vector_json)) == 384 for chunk in repaired_chunks)
    finally:
        generator.close()


def test_create_item_repairs_stale_embeddings_before_adding_new_vectors(client: TestClient) -> None:
    older_item = create_item(client, "Louisiana flood insurance\n\nExisting saved material.")

    db, generator = open_test_db()
    try:
        chunk = db.query(crud.ItemChunk).filter(crud.ItemChunk.item_id == older_item["id"]).first()
        assert chunk is not None
        chunk.embedding_model = "local-hash-v1"
        chunk.embedding_vector_json = json.dumps([0.1, 0.2, 0.3])
        db.commit()
    finally:
        generator.close()

    newer_item = create_item(client, "Louisiana property insurance\n\nNew material after the upgrade.")

    db, generator = open_test_db()
    try:
        all_chunks = db.query(crud.ItemChunk).filter(crud.ItemChunk.item_id.in_([older_item["id"], newer_item["id"]])).all()
        assert all_chunks
        assert all(chunk.embedding_model == "sentence-transformers/all-MiniLM-L6-v2" for chunk in all_chunks)
        assert all(len(json.loads(chunk.embedding_vector_json)) == 384 for chunk in all_chunks)
    finally:
        generator.close()
