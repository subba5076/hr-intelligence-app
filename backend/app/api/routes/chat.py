"""
The conversational endpoint: this is what the resume calls "enabling
employees to query HR policies, onboarding information, and benefits
documentation through a conversational LLM interface."

POST /api/chat:
  1. Look up (or create) the conversation in Postgres.
  2. Store the user's message.
  3. Run the RAG chain (retrieve relevant HR doc chunks + generate answer).
  4. Store the assistant's answer (with its sources) so it shows up in
     conversation history and can later be rated via /api/feedback.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation, Message

# Imported as a module (not `from app.rag.chain import answer_question`) so
# that tests can monkeypatch `chain.answer_question` and have this route
# actually pick up the replacement -- patching a name that's already been
# imported directly into this module's namespace wouldn't be visible here.
from app.rag import chain
from app.schemas.chat import ChatRequest, ChatResponse, SourceChunk

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Reuse an existing conversation thread, or start a new one.
    conversation = None
    if request.conversation_id:
        conversation = db.get(Conversation, request.conversation_id)
    if conversation is None:
        conversation = Conversation(user_id=request.user_id)
        db.add(conversation)
        db.flush()  # assigns conversation.id without committing yet

    user_message = Message(conversation_id=conversation.id, role="user", content=request.question)
    db.add(user_message)

    try:
        result = chain.answer_question(request.question)
    except FileNotFoundError as exc:
        # Most common cause: nobody has run `python scripts/ingest_docs.py` yet.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        logger.exception("RAG pipeline failed")
        raise HTTPException(status_code=500, detail="Failed to generate an answer.") from None

    import json
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        sources=json.dumps(result["sources"]),
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=result["answer"],
        sources=[SourceChunk(**s) for s in result["sources"]],
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conversation.id,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in conversation.messages
        ],
    }
