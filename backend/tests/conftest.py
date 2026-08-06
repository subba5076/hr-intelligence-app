"""
Shared pytest fixtures.

Tests run against SQLite by default (fast, zero setup) unless DATABASE_URL
is already set in the environment (that's what CI does -- see
.github/workflows/ci-cd.yml -- to also exercise the real Postgres dialect
before every deploy). Because app/db/models.py stores IDs as plain
36-char strings rather than Postgres's native UUID type, the schema is
identical on both, so behavior doesn't change between the two.
"""
import os

# Must be set BEFORE importing anything from `app`, since app.core.config
# reads the environment once at import time.
# Uses /tmp rather than a path inside the project folder: this repo lives
# under a cloud-synced folder (OneDrive/Dropbox/Google Drive) on many
# machines, and SQLite's file-locking doesn't work reliably on those --
# you'd see intermittent "database is locked" or I/O errors. /tmp is a
# real local filesystem, so the test DB is safe there. (Postgres itself
# is unaffected by this since it's a separate service reached over TCP,
# not a locked local file.)
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/hrapp_test.db")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")

import pytest


@pytest.fixture(autouse=True)
def _stub_rag_chain(monkeypatch):
    """
    Every test gets the RAG chain stubbed out by default, so tests focus on
    API/DB wiring rather than requiring the real FAISS index + embedding
    model to be built first. Tests that specifically want to exercise the
    real RAG pipeline (see test_rag_pipeline.py) opt out explicitly.
    """
    import app.rag.chain as chain_mod

    def fake_answer_question(question: str) -> dict:
        return {
            "answer": f"Mock answer for: {question}",
            "sources": [{"filename": "benefits_summary.md", "snippet": "PTO accrues at 15 days/year..."}],
        }

    monkeypatch.setattr(chain_mod, "answer_question", fake_answer_question)
    yield
