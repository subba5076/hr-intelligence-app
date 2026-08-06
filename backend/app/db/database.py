"""
SQLAlchemy engine/session setup for PostgreSQL.

`get_db` is a FastAPI dependency: each request gets its own session, which
is closed automatically when the request finishes (even if it raises).
This avoids leaking connections under load, which matters once we're
running multiple replicas behind the Kubernetes HPA.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class every ORM model inherits from."""
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create tables if they don't exist yet.

    For a real production system you'd use Alembic migrations exclusively
    (see backend/alembic/) so schema changes are versioned. We still call
    this at startup for local/dev convenience so `docker compose up` works
    with zero manual steps.
    """
    from app.db import models  # noqa: F401 (ensures models are registered)
    Base.metadata.create_all(bind=engine)
