"""
Pydantic request/response schemas for the chat API.

Kept separate from the ORM models (app/db/models.py) on purpose: the
"shape of the API" and the "shape of the database" are allowed to drift
independently as the app evolves.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    # Client-generated id so a user can continue an existing conversation
    # thread; if omitted, a new conversation is created.
    conversation_id: str | None = None
    # Placeholder for a real identity system (SSO/JWT). Defaults to a demo
    # user so the app is usable without wiring up auth.
    user_id: str = "demo-user"


class SourceChunk(BaseModel):
    filename: str
    snippet: str


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[SourceChunk]


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1, description="-1 = not helpful, +1 = helpful")
    comment: str | None = None
