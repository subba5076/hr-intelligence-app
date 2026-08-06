"""
FastAPI application entrypoint.

Run locally with:  uvicorn app.main:app --reload
Run in Docker with: see backend/Dockerfile (CMD)
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, documents, feedback, health
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.database import init_db

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HR Intelligence API",
    description="Conversational RAG API over HR policy, onboarding, and benefits documents.",
    version="1.0.0",
)

# Only allow the configured frontend origin(s) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Structured request logging with a request_id, so a single request can
    be traced through logs even across multiple pods in Kubernetes.
    """
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def on_startup():
    logger.info("Starting HR Intelligence API (env=%s)", settings.app_env)
    init_db()  # dev convenience; production schema changes go through Alembic


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(documents.router)
