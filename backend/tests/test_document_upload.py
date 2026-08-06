"""
Tests for POST /api/documents/upload -- the live document upload flow.

Like tests/conftest.py's stub for the chat RAG chain, `add_document` is
stubbed here rather than exercising the real FAISS/embedding pipeline
(that's covered separately by the manual vector_store smoke test in
app/rag/vector_store.py's docstring workflow) -- these tests focus on the
HTTP/validation/DB-upsert behavior of the endpoint itself.
"""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _stub_add_document(monkeypatch):
    from app.rag import chain as chain_mod

    monkeypatch.setattr(chain_mod, "add_document", lambda filepath: 3)
    yield


def test_upload_rejects_unsupported_file_type():
    with TestClient(app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("policy.docx", io.BytesIO(b"fake content"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_empty_file():
    with TestClient(app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("policy.md", io.BytesIO(b""), "text/markdown")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


def test_upload_indexes_and_appears_in_document_list(tmp_path, monkeypatch):
    from app.core import config as config_mod

    # Point HR_DOCS_DIR at a scratch directory so the test doesn't write
    # into the real data/hr_docs/ folder.
    monkeypatch.setattr(config_mod.settings, "hr_docs_dir", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("new_policy.md", io.BytesIO(b"# New Policy\nSome content here."), "text/markdown")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filename"] == "new_policy.md"
        assert body["chunk_count"] == 3
        assert body["title"] == "New Policy"

        # File actually landed on disk...
        assert (tmp_path / "new_policy.md").exists()

        # ...and shows up in the document list the sidebar reads.
        docs = client.get("/api/documents").json()
        assert any(d["filename"] == "new_policy.md" for d in docs)


def test_reuploading_same_filename_updates_existing_row(tmp_path, monkeypatch):
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "hr_docs_dir", str(tmp_path))

    with TestClient(app) as client:
        for _ in range(2):
            response = client.post(
                "/api/documents/upload",
                files={"file": ("policy.txt", io.BytesIO(b"Updated content."), "text/plain")},
            )
            assert response.status_code == 200

        docs = client.get("/api/documents").json()
        matches = [d for d in docs if d["filename"] == "policy.txt"]
        assert len(matches) == 1  # upsert, not a duplicate row
