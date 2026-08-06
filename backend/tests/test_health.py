"""
Basic smoke tests. Run with: pytest (from backend/, with dependencies installed).

These intentionally don't need a real Postgres or FAISS index -- they
check that the app boots and the liveness endpoint responds, which is
exactly what CI runs on every push (see .github/workflows/ci-cd.yml).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_loads():
    # If any route has a broken schema, this will fail -- cheap sanity check.
    response = client.get("/openapi.json")
    assert response.status_code == 200
