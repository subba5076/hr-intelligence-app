"""
The RAG (Retrieval-Augmented Generation) chain: the piece that turns a raw
employee question into a grounded answer.

Flow: question -> embed -> FAISS similarity search -> top-k chunks ->
LLM (OpenAI, Groq, or mock) generates an answer constrained to those chunks
-> return answer + sources.

Loading the FAISS index from disk is somewhat expensive, so we do it once
per process (module-level singleton) rather than per request. That same
singleton is what makes live document uploads possible without restarting
the app: app/api/routes/documents.py calls `add_document()` below, which
mutates this in-memory index directly (and persists it to disk), so the
very next chat question can retrieve from the newly uploaded document --
no reload, no dropped connections, existing conversations untouched.
"""
import logging
import threading

from app.core.config import settings
from app.rag.llm_provider import LLMProvider, get_llm_provider
from app.rag.vector_store import build_documents_from_file, load_index, similarity_search

logger = logging.getLogger(__name__)

_vector_store = None
_llm_provider: LLMProvider | None = None

# Guards every read of *and* write to `_vector_store`. FAISS's in-memory
# index isn't safe for a search to run concurrently with an add -- FastAPI
# serves sync endpoints from a thread pool, so two requests (one chat, one
# upload) really can land at the same time. The critical sections below are
# kept short (no LLM calls inside the lock) so this never becomes a
# bottleneck for normal chat traffic.
_lock = threading.Lock()


def _get_llm() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = get_llm_provider()
    return _llm_provider


def answer_question(question: str) -> dict:
    """
    Returns:
        {
          "answer": str,
          "sources": [{"filename": str, "snippet": str}, ...]
        }
    """
    global _vector_store
    with _lock:
        if _vector_store is None:
            _vector_store = load_index(settings.faiss_index_dir)  # raises FileNotFoundError if none built yet
        docs = similarity_search(_vector_store, question)
    logger.info("Retrieved %d chunks for question: %r", len(docs), question)

    # Deliberately outside the lock: the LLM call is the slow part (up to a
    # few seconds for a real API), and it doesn't touch the vector store, so
    # holding the lock here would block uploads and other chats for no reason.
    llm = _get_llm()
    answer = llm.generate(question, docs)

    sources = [
        {"filename": doc.metadata.get("filename", "unknown"), "snippet": doc.page_content[:200]}
        for doc in docs
    ]
    return {"answer": answer, "sources": sources}


def add_document(filepath: str) -> int:
    """
    Incrementally add one newly-uploaded file to the live index: chunk it,
    embed just those chunks, append them to the existing FAISS index (or
    create a fresh one if nothing's been indexed yet), and persist to disk.

    Deliberately does NOT re-embed the whole document set -- that's what
    makes this fast enough to run inline in an HTTP request instead of
    needing a background job queue. Returns the number of chunks added.
    """
    global _vector_store
    documents = build_documents_from_file(filepath)
    if not documents:
        raise ValueError(f"No extractable text found in {filepath}")

    with _lock:
        if _vector_store is None:
            try:
                _vector_store = load_index(settings.faiss_index_dir)
            except FileNotFoundError:
                _vector_store = None  # nothing indexed yet anywhere -- bootstrap below

        if _vector_store is None:
            from app.rag.embeddings import get_embeddings
            from langchain_community.vectorstores import FAISS

            _vector_store = FAISS.from_documents(documents, get_embeddings())
        else:
            _vector_store.add_documents(documents)

        _vector_store.save_local(settings.faiss_index_dir)

    logger.info("Added %s to the live index (%d chunks)", filepath, len(documents))
    return len(documents)
