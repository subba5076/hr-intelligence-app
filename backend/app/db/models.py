"""
ORM models.

Everything the resume bullet "PostgreSQL stores conversation history,
document metadata, and user feedback for continuous quality improvement"
refers to lives in this file.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# IDs are stored as plain 36-char strings (str(uuid.uuid4())) rather than
# Postgres's native UUID column type. This is a deliberate portability
# choice: the schema works identically against Postgres (production/K8s),
# SQLite (quick local tests), or any other SQLAlchemy-supported database,
# with no behavior difference -- Postgres just stores it as varchar(36).
_UUID_COL = String(36)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    """One chat session for one employee."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_uuid)
    # In a real deployment this would be a foreign key to an employee/SSO
    # identity table. Kept as a plain string here to avoid needing a full
    # auth system for the demo.
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """A single turn (user question or assistant answer) in a conversation."""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)

    # For assistant messages: which document chunks were retrieved to
    # ground the answer, stored as a JSON-encoded string of source names.
    # Lets us show "Sources:" in the UI and audit answer quality later.
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    feedback: Mapped["Feedback | None"] = relationship(back_populates="message", uselist=False)


class Feedback(Base):
    """
    Thumbs up/down (+ optional comment) on an assistant answer.

    This is the "user feedback scores collected through the PostgreSQL
    feedback store" from the resume -- it's what turns query resolution
    rate and satisfaction into a measurable, trackable metric over time.
    """
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)  # +1 (helpful) or -1 (not helpful)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    message: Mapped["Message"] = relationship(back_populates="feedback")


class DocumentMetadata(Base):
    """
    Metadata about each HR document that has been ingested into the FAISS
    index. The actual vectors live in FAISS (see app/rag/vector_store.py);
    Postgres just tracks *what* was indexed and *when*, so we know if the
    index is stale relative to the source documents.
    """
    __tablename__ = "document_metadata"

    id: Mapped[str] = mapped_column(_UUID_COL, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500))
    chunk_count: Mapped[int] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
