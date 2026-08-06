"""
LLM provider abstraction.

The resume bullet says "the OpenAI API for grounded, accurate responses",
and OpenAIProvider below is that real implementation. But requiring an
API key just to run/demo the project is a bad experience, so there are two
free fallbacks:
  - GroqProvider: a real hosted LLM call, just via Groq's free tier
    (no credit card required) instead of paid OpenAI.
  - MockProvider: a fully local, deterministic, template-based responder
    that uses the *same* retrieved document chunks with no network call
    at all.

Everything above this file (the RAG chain, the API routes) only depends
on the `LLMProvider` interface, so switching providers is a one-line
config change (LLM_PROVIDER=openai|groq|mock in .env) -- no other code changes.
"""
import logging
import re
from abc import ABC, abstractmethod

from langchain_core.documents import Document

from app.core.config import settings

logger = logging.getLogger(__name__)

# Shared system prompt for every real (non-mock) LLM provider: constrains
# the model to only answer from the retrieved HR policy excerpts, which is
# what makes the answer "grounded" rather than the model improvising policy.
_SYSTEM_PROMPT = (
    "You are an internal HR assistant. Answer the employee's question using ONLY "
    "the HR policy excerpts provided below. If the answer isn't in the excerpts, "
    "say you don't have that information and suggest contacting HR. Be concise and "
    "cite which policy document(s) you used."
)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, question: str, context_docs: list[Document]) -> str:
        """Given a question and retrieved context chunks, produce an answer."""
        raise NotImplementedError


class _ChatModelProvider(LLMProvider):
    """
    Shared logic for any provider backed by a LangChain chat model
    (`self._llm`). OpenAIProvider and GroqProvider both just construct a
    different underlying `ChatOpenAI` client (different API key/base URL/
    model) and inherit this `generate()` unchanged -- Groq deliberately
    exposes an OpenAI-compatible API, so the same client class works for
    both, only the endpoint differs.
    """

    _llm = None  # set by subclasses in __init__

    def generate(self, question: str, context_docs: list[Document]) -> str:
        context = "\n\n".join(
            f"[Source: {doc.metadata.get('filename')}]\n{doc.page_content}" for doc in context_docs
        )
        response = self._llm.invoke(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", f"HR policy excerpts:\n{context}\n\nQuestion: {question}"),
            ]
        )
        return response.content


class OpenAIProvider(_ChatModelProvider):
    """Real implementation: calls the OpenAI API via LangChain's ChatOpenAI. Paid."""

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Add it to backend/.env, or set LLM_PROVIDER=mock/groq to run for free."
            )
        self._llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.2,  # low temperature: we want grounded, consistent policy answers
        )


class GroqProvider(_ChatModelProvider):
    """
    Real LLM calls via Groq's free tier (console.groq.com, no credit card).

    Groq hosts open-weight models (Llama, GPT-OSS, etc.) behind an
    OpenAI-compatible endpoint, so this reuses LangChain's ChatOpenAI
    client pointed at Groq's base_url instead of pulling in a separate
    SDK/dependency.
    """

    def __init__(self) -> None:
        from langchain_openai import ChatOpenAI

        if not settings.groq_api_key:
            raise ValueError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set. Get a free key (no credit "
                "card) at https://console.groq.com/keys and add it to backend/.env, or set "
                "LLM_PROVIDER=mock to run without any API key."
            )
        self._llm = ChatOpenAI(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.2,
        )


class MockProvider(LLMProvider):
    """
    Free, local, zero-dependency fallback.

    It doesn't "understand" language the way a real LLM does -- it extracts
    the most relevant sentences from the retrieved chunks (the same chunks
    a real LLM would be grounded on) and stitches them into an answer. This
    keeps the full RAG pipeline (retrieval -> grounded answer -> stored
    conversation) genuinely working end-to-end without any paid API.
    """

    def generate(self, question: str, context_docs: list[Document]) -> str:
        if not context_docs:
            return (
                "I couldn't find anything in the HR policy documents that answers this. "
                "Please contact HR directly."
            )

        question_words = {w.lower() for w in re.findall(r"\w+", question) if len(w) > 3}

        # Score every candidate sentence by how many distinct question
        # keywords it contains, then keep the best-scoring ones. Ranking
        # (rather than taking sentences in document order) matters because
        # the top FAISS match isn't always the sentence that best answers
        # the question -- often a later sentence in that same chunk is.
        scored: list[tuple[int, str]] = []
        for doc in context_docs:
            # Strip markdown heading markers ("## Paid Time Off" -> "Paid Time Off")
            # so headings don't show up mid-sentence in the final answer.
            cleaned = re.sub(r"^#+\s*", "", doc.page_content, flags=re.MULTILINE)
            for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
                sentence = sentence.strip().replace("\n", " ")
                if len(sentence) < 15:
                    continue  # skip stray headings/fragments with no punctuation
                overlap = question_words & {w.lower() for w in re.findall(r"\w+", sentence)}
                if overlap:
                    scored.append((len(overlap), sentence))

        if not scored:
            # Fall back to the first chunk verbatim rather than returning nothing.
            fallback = context_docs[0].page_content.strip().split("\n")[0]
            scored = [(0, fallback)]

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_sentences = [s for _, s in scored[:3]]

        answer = " ".join(top_sentences)
        sources = ", ".join(sorted({doc.metadata.get("filename", "unknown") for doc in context_docs}))
        return (
            f"{answer}\n\n(Based on: {sources}. Running in local mock mode -- "
            "set LLM_PROVIDER=openai for full LLM answers.)"
        )


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        logger.info("Using OpenAIProvider")
        return OpenAIProvider()
    if settings.llm_provider == "groq":
        logger.info("Using GroqProvider (free tier, model=%s)", settings.groq_model)
        return GroqProvider()
    logger.info("Using MockProvider (free, local, no API key required)")
    return MockProvider()
