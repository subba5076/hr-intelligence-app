"""
End-to-end test of the conversational API against a real (SQLite/Postgres)
database: chat -> conversation persists -> feedback -> summary metrics.

This is the test that proves the pieces described in the resume actually
fit together: "PostgreSQL stores conversation history, document metadata,
and user feedback."
"""
from fastapi.testclient import TestClient

from app.main import app


def test_chat_creates_conversation_and_persists_messages():
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"question": "How much PTO do I get?"})
        assert response.status_code == 200

        body = response.json()
        assert body["answer"].startswith("Mock answer")
        assert len(body["sources"]) == 1

        conversation_id = body["conversation_id"]

        # Second turn in the same thread.
        response2 = client.post(
            "/api/chat", json={"question": "And parental leave?", "conversation_id": conversation_id}
        )
        assert response2.status_code == 200
        assert response2.json()["conversation_id"] == conversation_id

        history = client.get(f"/api/conversations/{conversation_id}")
        assert history.status_code == 200
        assert len(history.json()["messages"]) == 4  # 2 user + 2 assistant turns


def test_feedback_updates_satisfaction_summary():
    with TestClient(app) as client:
        chat_response = client.post("/api/chat", json={"question": "What's the parental leave policy?"})
        message_id = chat_response.json()["message_id"]

        feedback_response = client.post("/api/feedback", json={"message_id": message_id, "rating": 1})
        assert feedback_response.status_code == 200

        summary = client.get("/api/feedback/summary").json()
        assert summary["total_ratings"] >= 1
        assert summary["satisfaction_rate"] is not None


def test_feedback_for_unknown_message_returns_404():
    with TestClient(app) as client:
        response = client.post("/api/feedback", json={"message_id": "does-not-exist", "rating": 1})
        assert response.status_code == 404
