#!/usr/bin/env python
"""
CLI: build the FAISS index from data/hr_docs and record metadata in Postgres.

Run this whenever HR documents change:
    cd backend && python scripts/ingest_docs.py

This is deliberately a separate offline step rather than something that
runs on every API request -- re-embedding documents is comparatively slow
and should happen on a controlled schedule (or a CI/CD step), not on the
hot path of answering a user's question.
"""
import os
import sys

# Allow running this script directly (`python scripts/ingest_docs.py`)
# without needing the package installed.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.database import SessionLocal, init_db
from app.db.models import DocumentMetadata
from app.rag.vector_store import build_index, load_and_split_documents

configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", settings.hr_docs_dir))
    index_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", settings.faiss_index_dir))

    logger.info("Ingesting HR documents from %s", docs_dir)
    num_docs, num_chunks = build_index(docs_dir, index_dir)

    # Record what we ingested in Postgres so the app (and you) can see
    # what's currently indexed, and detect when the index goes stale.
    init_db()
    db = SessionLocal()
    try:
        db.query(DocumentMetadata).delete()  # simple demo strategy: replace on each ingest
        chunks_by_file: dict[str, int] = {}
        for doc in load_and_split_documents(docs_dir):
            fname = doc.metadata["filename"]
            chunks_by_file[fname] = chunks_by_file.get(fname, 0) + 1

        for filename, chunk_count in chunks_by_file.items():
            title = filename.replace("_", " ").replace(".md", "").title()
            db.add(DocumentMetadata(filename=filename, title=title, chunk_count=chunk_count))
        db.commit()
    finally:
        db.close()

    print(f"\nDone. Indexed {num_docs} documents into {num_chunks} chunks.")
    print(f"FAISS index saved to: {index_dir}")


if __name__ == "__main__":
    main()
