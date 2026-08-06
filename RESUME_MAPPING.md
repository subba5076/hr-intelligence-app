# Resume → Code Mapping

Your resume line, and exactly what in this repo backs it up. Use this to prep for interview
questions -- every claim below points at a real file you can open and explain.

---

### "Built and deployed a full-stack AI application that solves a real HR problem."

The whole repo. Frontend: `frontend/`. Backend: `backend/`. The "real HR problem" is answering
employee questions about policy/onboarding/benefits without them having to search through PDFs
or wait on an HR rep -- see `data/hr_docs/` for the source documents and `app/rag/chain.py` for
how a question becomes a grounded answer.

### "React and TypeScript frontend with a FastAPI REST backend"

- Frontend: `frontend/src/` -- React 18 function components, typed throughout
  (`frontend/src/types/index.ts`), built with Vite (`frontend/vite.config.ts`).
- Backend: `backend/app/main.py` -- FastAPI app; REST endpoints in `backend/app/api/routes/`
  (`chat.py`, `feedback.py`, `documents.py`, `health.py`).

### "enabling employees to query HR policies, onboarding information, and benefits documentation through a conversational LLM interface"

- `frontend/src/components/ChatWindow.tsx` -- the conversational UI, keeps message history and
  a `conversation_id` so multi-turn chats work.
- `backend/app/api/routes/chat.py` -- `POST /api/chat`, the endpoint the UI talks to.
- `data/hr_docs/` -- the actual policy/onboarding/benefits documents being queried (sample docs
  included; swap in real ones and re-run `scripts/ingest_docs.py`).

### "PostgreSQL stores conversation history, document metadata, and user feedback for continuous quality improvement"

All in `backend/app/db/models.py`:
- `Conversation` / `Message` -- conversation history.
- `DocumentMetadata` -- which HR docs are indexed and when (populated by `scripts/ingest_docs.py`).
- `Feedback` -- thumbs up/down per answer, aggregated in `GET /api/feedback/summary`
  (`backend/app/api/routes/feedback.py`) into a satisfaction rate. That's the "continuous
  quality improvement" loop: you can see which answers employees found unhelpful.

### "Implemented a LangChain RAG pipeline over HR policy documents using FAISS vector indexing and the OpenAI API for grounded, accurate responses"

- `backend/app/rag/vector_store.py` -- loads/chunks documents (`RecursiveCharacterTextSplitter`),
  builds and queries the FAISS index.
- `backend/app/rag/embeddings.py` -- the embedding model (local `sentence-transformers`, free;
  swappable for OpenAI embeddings, see the comment in that file).
- `backend/app/rag/llm_provider.py` -- `OpenAIProvider` is the real OpenAI integration
  (`gpt-4o-mini` via `langchain-openai`'s `ChatOpenAI`), constrained by a system prompt to only
  answer from retrieved context ("grounded" = it can't make policy up).
- `backend/app/rag/chain.py` -- the retrieval → generation orchestration LangChain is doing here.

*Why there's also a `MockProvider` and a `GroqProvider`:* `MockProvider` is a free, local,
deterministic fallback (same file, `llm_provider.py`) so the app runs with zero API cost during
development/demos. `GroqProvider` is a *real* hosted LLM call via Groq's free tier (no credit
card) -- Groq exposes an OpenAI-compatible endpoint, so it reuses the same `ChatOpenAI` client
class as `OpenAIProvider`, just pointed at a different `base_url`. Switching between all three is
a one-line env var change (`LLM_PROVIDER=openai|groq|mock`) -- nothing else in the app changes,
because all three implement the same `LLMProvider` interface. This is worth mentioning in an
interview: it shows you designed for swappable providers rather than hard-wiring one vendor's SDK
throughout the codebase.

### Bonus, beyond the original resume bullets: live document upload with incremental indexing

Not on the resume, but worth knowing how to talk about if asked "how would someone actually add
a new policy document to this?" -- `frontend/src/components/Sidebar.tsx` has an upload button,
backed by `POST /api/documents/upload` (`backend/app/api/routes/documents.py`), which chunks and
embeds *only* the newly uploaded file and appends it to the live FAISS index
(`backend/app/rag/chain.py`'s `add_document()`) rather than re-processing the whole document set.
A `threading.Lock` guards the shared in-memory index so a chat request and an upload can safely
overlap without corrupting it or blocking the chat for long. Good interview talking points here:
why incremental indexing instead of a full rebuild (speed), why a lock instead of a queue for
this scale (simplicity, no infra needed), and the explicit tradeoff called out in the README --
this in-memory approach works for one process but needs a shared vector store to scale across
multiple Kubernetes replicas.

### "Containerized the full application stack with Docker"

`backend/Dockerfile`, `frontend/Dockerfile` (multi-stage: Node build → nginx serve),
`docker-compose.yml` for local orchestration (Postgres + backend + frontend).

### "orchestrated on Azure Kubernetes Service (AKS) with horizontal pod autoscaling to handle concurrent user load"

`k8s/` directory:
- `backend-deployment.yaml`, `frontend-deployment.yaml` -- rolling-update Deployments.
- `backend-hpa.yaml` -- the HPA: scales the backend 2→10 pods on 70% CPU utilization, with a
  5-minute scale-down stabilization window to avoid flapping under bursty load.
- `ingress.yaml` -- routes external traffic to frontend/backend Services.
- `configmap.yaml` / `secret.yaml.example` -- config/secrets split (never put secrets in the ConfigMap).

### "CI/CD via GitHub Actions covers automated tests, container builds, and rolling deployment on every push to main"

`.github/workflows/ci-cd.yml`:
- `backend-test` job -- runs the pytest suite against a real Postgres service container.
- `frontend-build` job -- TypeScript type-check + Vite production build.
- `build-and-deploy` job (only on push to `main`, only after both test jobs pass) -- builds and
  pushes both Docker images to Azure Container Registry, applies the `k8s/` manifests, then does
  `kubectl set image` + `kubectl rollout status` for a rolling deploy with zero downtime
  (`maxUnavailable: 0` in the Deployments).

### "Git feature branching, pull request reviews, environment-specific configuration, health check endpoints, and structured logging"

- Environment-specific config: `backend/app/core/config.py` (pydantic-settings, reads from env
  vars / `.env`), `k8s/configmap.yaml` for the K8s environment.
- Health check endpoints: `backend/app/api/routes/health.py` -- `/health/live` (process up?) and
  `/health/ready` (can it reach Postgres?), wired into the K8s liveness/readiness probes in
  `backend-deployment.yaml`.
- Structured logging: `backend/app/core/logging_config.py` -- JSON log lines with a
  `request_id` per request (added in `backend/app/main.py`'s middleware), so a single request
  can be traced through logs across multiple pods.
- Feature branching / PR reviews: process, not code -- but the CI workflow triggers on
  `pull_request` too (see `on:` in `ci-cd.yml`), so tests gate every PR before merge.

### "Measured impact via response accuracy, query resolution rate, and user satisfaction scores collected through the PostgreSQL feedback store"

- User satisfaction: `GET /api/feedback/summary` computes `positive_ratings / total_ratings`
  directly from the `Feedback` table.
- Query resolution rate / response accuracy: the `Message.sources` field (JSON-encoded list of
  which HR document chunks were used) lets you audit *why* an answer was given, and cross-
  reference low-rated answers against what was actually retrieved -- the foundation for
  measuring whether poor answers are a retrieval problem (wrong chunks found) or a generation
  problem (right chunks, bad answer).
