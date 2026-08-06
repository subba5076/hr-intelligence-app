"""
Centralized application configuration.

We use pydantic-settings so every config value is:
  1) typed and validated at startup (fail fast if something is missing/wrong)
  2) overridable via environment variables (12-factor app style), which is
     exactly how Docker/Kubernetes inject config in the deployed version.

Nothing else in the codebase should call os.environ directly -- import
`settings` from here instead, so there is a single source of truth.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    # Comma-separated list of origins allowed to call the API (CORS).
    allowed_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql://hrapp:hrapp_password@localhost:5432/hrapp"

    # --- LLM provider ---
    # "openai" = real OpenAI API calls (needs openai_api_key, paid).
    # "groq"   = free-tier hosted LLM calls via Groq (needs groq_api_key,
    #            no credit card required at console.groq.com). Groq exposes
    #            an OpenAI-compatible endpoint, so this reuses ChatOpenAI
    #            with a different base_url -- see app/rag/llm_provider.py.
    # "mock"   = free local template-based responder, used when no API key
    #            is configured at all, so the app still runs end-to-end.
    llm_provider: str = "mock"
    openai_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # --- RAG / vector index ---
    hr_docs_dir: str = "../data/hr_docs"
    faiss_index_dir: str = "./storage/faiss_index"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # How many chunks to retrieve per question.
    retrieval_top_k: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached so we parse the environment once per process, not on every
    request. FastAPI's dependency injection can still use this as a
    dependency (`Depends(get_settings)`) for testability.
    """
    return Settings()


# Convenience singleton for modules that don't need DI (e.g. scripts).
settings = get_settings()
