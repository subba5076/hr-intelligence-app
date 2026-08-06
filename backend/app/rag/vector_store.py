"""
FAISS vector index: build it from documents, save it to disk, load it back,
and run similarity search at query time.

FAISS (Facebook AI Similarity Search) is an in-process vector index -- no
separate database server to run, which keeps the demo simple. For a much
larger document set you'd swap this for a managed vector DB (pgvector,
Pinecone, Azure AI Search), but the LangChain interface (`similarity_search`)
would stay the same, so `chain.py` wouldn't need to change.
"""
import logging
import os

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

# Tuned for HR policy docs: big enough chunks to keep a policy's context
# together, with overlap so we don't split a rule from its explanation.
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)

SUPPORTED_EXTENSIONS = (".md", ".txt", ".pdf")


def _read_file_text(path: str) -> str:
    """
    Extract plain text from a document, regardless of format. Markdown/text
    files are read directly; PDFs (common for real HR policy exports) are
    parsed with pypdf. Used by both the bulk ingestion script and the
    single-file upload endpoint, so both paths behave identically.
    """
    if path.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_documents_from_file(path: str) -> list[Document]:
    """Read + chunk a single document. Used for incrementally adding one
    newly-uploaded file to the index without re-processing everything else."""
    filename = os.path.basename(path)
    text = _read_file_text(path)
    chunks = _SPLITTER.split_text(text)
    documents = [
        Document(page_content=chunk, metadata={"filename": filename, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    logger.info("Split %s into %d chunks", filename, len(chunks))
    return documents


def load_and_split_documents(docs_dir: str) -> list[Document]:
    """Read every supported file in docs_dir and split into overlapping chunks."""
    documents: list[Document] = []
    for filename in sorted(os.listdir(docs_dir)):
        if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
            continue
        documents.extend(build_documents_from_file(os.path.join(docs_dir, filename)))
    return documents


def build_index(docs_dir: str, index_dir: str) -> tuple[int, int]:
    """
    Build a fresh FAISS index from all documents in docs_dir and persist it
    to index_dir. Returns (num_documents, num_chunks).
    """
    documents = load_and_split_documents(docs_dir)
    if not documents:
        raise ValueError(f"No .md/.txt documents found in {docs_dir}")

    store = FAISS.from_documents(documents, get_embeddings())
    os.makedirs(index_dir, exist_ok=True)
    store.save_local(index_dir)

    num_docs = len({d.metadata["filename"] for d in documents})
    logger.info("Built FAISS index: %d documents, %d chunks -> %s", num_docs, len(documents), index_dir)
    return num_docs, len(documents)


def load_index(index_dir: str) -> FAISS:
    """Load a previously built FAISS index from disk."""
    if not os.path.isdir(index_dir):
        raise FileNotFoundError(
            f"No FAISS index found at {index_dir}. Run `python scripts/ingest_docs.py` first."
        )
    # allow_dangerous_deserialization=True is safe here because we only ever
    # load an index *we* built and saved (not one from an untrusted source).
    return FAISS.load_local(index_dir, get_embeddings(), allow_dangerous_deserialization=True)


def similarity_search(store: FAISS, query: str, k: int | None = None) -> list[Document]:
    return store.similarity_search(query, k=k or settings.retrieval_top_k)
