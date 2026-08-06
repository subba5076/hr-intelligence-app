"""
Document listing + live upload.

GET  /api/documents         -- what's currently indexed (populated by
                                scripts/ingest_docs.py or an upload below).
POST /api/documents/upload  -- add a new HR document (.md/.txt/.pdf) to the
                                live FAISS index without restarting the app
                                or disrupting in-progress chats. See
                                app/rag/chain.py's `add_document()` for how
                                the incremental (non-blocking) indexing works.
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import DocumentMetadata
from app.rag import chain
from app.rag.vector_store import SUPPORTED_EXTENSIONS
from app.schemas.documents import DocumentInfo, UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

# Generous for a policy document (even a long one with images is rarely
# more than a few MB as text/PDF) -- mainly here to stop someone accidentally
# uploading a huge file and blocking the request thread for a long time.
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(DocumentMetadata).order_by(DocumentMetadata.title).all()
    return [
        DocumentInfo(
            filename=d.filename,
            title=d.title,
            chunk_count=d.chunk_count,
            ingested_at=d.ingested_at.isoformat(),
        )
        for d in docs
    ]


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'unknown'}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 15 MB).")

    # Persist the raw file into data/hr_docs/ alongside the sample docs, so
    # it survives container restarts and a full `ingest_docs.py` re-run
    # would pick it up too -- the upload isn't a separate, special path,
    # it's just a faster way to get a document into the same place.
    docs_dir = os.path.abspath(settings.hr_docs_dir)
    os.makedirs(docs_dir, exist_ok=True)
    dest_path = os.path.join(docs_dir, file.filename)
    with open(dest_path, "wb") as f:
        f.write(contents)

    try:
        chunk_count = chain.add_document(dest_path)
    except ValueError as exc:
        # e.g. a PDF with no extractable text (scanned image, no OCR here)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Failed to index uploaded document %s", file.filename)
        raise HTTPException(status_code=500, detail="Failed to index the uploaded document.") from None

    title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()

    existing = db.query(DocumentMetadata).filter(DocumentMetadata.filename == file.filename).first()
    if existing:
        existing.chunk_count = chunk_count
        existing.title = title
        existing.ingested_at = datetime.now(timezone.utc)
    else:
        db.add(DocumentMetadata(filename=file.filename, title=title, chunk_count=chunk_count))
    db.commit()

    logger.info("Indexed uploaded document %s (%d chunks)", file.filename, chunk_count)
    return UploadResponse(filename=file.filename, title=title, chunk_count=chunk_count)
