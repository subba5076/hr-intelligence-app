"""
Embedding model used to turn text chunks into vectors for FAISS.

We deliberately use a small local sentence-transformers model
(all-MiniLM-L6-v2, ~80MB) instead of OpenAI's embeddings API. Two reasons:
  1. It works with zero API key / zero cost, so the RAG pipeline is fully
     functional even before you have an OpenAI account.
  2. Embeddings are cheap to compute locally and don't benefit much from a
     bigger model for a small HR document set -- the LLM (see
     llm_provider.py) is where a hosted model actually earns its keep.

If you later want OpenAI embeddings instead, swap the return value below
for `OpenAIEmbeddings(api_key=settings.openai_api_key)` from
`langchain_openai` -- nothing else in the RAG pipeline needs to change,
since everything downstream just calls `.embed_query()` / `.embed_documents()`.
"""
from functools import lru_cache

from langchain_community.embeddings import HuggingFaceEmbeddings

from app.core.config import settings


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    # Cached so the model is loaded into memory once per process, not once
    # per request (loading it repeatedly would be slow).
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)
