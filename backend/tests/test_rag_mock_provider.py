"""
Unit test for the free, local MockProvider fallback (app/rag/llm_provider.py).

Doesn't need FAISS or an embedding model -- it just checks that, given a
retrieved chunk, the mock responder extracts the sentences that actually
answer the question rather than returning something irrelevant.
"""
from langchain_core.documents import Document

from app.rag.llm_provider import MockProvider

PTO_CHUNK = """## Paid Time Off
- Full-time employees accrue 15 days of PTO per year in years 1-3, increasing to 20 days in years 4+.
- 10 paid company holidays per year, published annually on the HR portal calendar.
- PTO is accrued monthly and can be carried over up to a maximum of 5 unused days into the next calendar year."""


def test_mock_provider_grounds_answer_in_retrieved_chunk():
    doc = Document(page_content=PTO_CHUNK, metadata={"filename": "benefits_summary.md"})

    answer = MockProvider().generate("How much PTO do I get per year?", [doc])

    assert "15 days" in answer
    assert "benefits_summary.md" in answer  # cites its source


def test_mock_provider_handles_no_retrieved_docs():
    answer = MockProvider().generate("How much PTO do I get?", [])
    assert "contact hr" in answer.lower()
