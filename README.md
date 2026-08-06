# AI-Powered HR Intelligence Application

A full-stack conversational RAG (Retrieval-Augmented Generation) app that lets employees ask
questions about HR policy, onboarding, and benefits in plain English, and get answers grounded
in your actual HR documents.

This project was built to match, line for line, the resume bullet points below -- every piece
of tech named there has real, working code behind it in this repo. See
[RESUME_MAPPING.md](./RESUME_MAPPING.md) for the exact file-by-file breakdown (useful if you
need to explain this project in an interview).

## What's actually running

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│   React +   │ HTTP │   FastAPI    │      │  PostgreSQL  │
│  TypeScript │ ───► │   backend    │ ───► │ (conversation │
│  (Vite)     │      │              │      │  history,    │
└─────────────┘      │  ┌────────┐  │      │  feedback)   │
                      │  │  RAG   │  │      └──────────────┘
                      │  │ chain  │  │
                      │  └───┬────┘  │
                      │      │       │
                      │  ┌───▼────┐  │      ┌──────────────┐
                      │  │ FAISS  │  │      │ OpenAI API   │
                      │  │ vector │  │ ───► │ (or free     │
                      │  │ index  │  │      │ local mock)  │
                      │  └────────┘  │      └──────────────┘
                      └──────────────┘
```

- **Frontend**: React 18 + TypeScript, built with Vite. Chat UI, conversation state, thumbs up/down feedback.
- **Backend**: FastAPI. REST endpoints for chat, feedback, and document status.
- **Database**: PostgreSQL. Stores conversations, messages, feedback ratings, and document-ingestion metadata.
- **RAG pipeline**: LangChain orchestration, FAISS for vector search, `sentence-transformers`
  (local, free, no API key) for embeddings, and a pluggable LLM layer:
  - `LLM_PROVIDER=openai` → real OpenAI API calls (`gpt-4o-mini` by default).
  - `LLM_PROVIDER=mock` → a free, local, template-based responder so the whole app runs
    end-to-end with **zero cost and zero API key**. This is the default.
- **Containers**: Dockerfiles for both services + `docker-compose.yml` for one-command local dev.
- **Kubernetes**: manifests for Azure Kubernetes Service (AKS) with a horizontal pod autoscaler.
- **CI/CD**: GitHub Actions workflow that tests, builds, and rolling-deploys on every push to `main`.

## Quick start (local, no cloud account needed)

**Prerequisites**: Python 3.11+, Node 20+, and either Docker, or a local PostgreSQL instance.

### Option A: Docker (easiest)

```bash
docker compose up --build
# in a second terminal, once the containers are up:
docker compose exec backend python scripts/ingest_docs.py
```

Open **http://localhost:5173** and start asking questions like "How much PTO do I get?"

### Option B: Run natively (no Docker)

```bash
# 1. Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Make sure DATABASE_URL in .env points at a running Postgres instance.
python scripts/ingest_docs.py        # builds the FAISS index from data/hr_docs
uvicorn app.main:app --reload        # http://localhost:8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

The app works immediately with `LLM_PROVIDER=mock` (the default) -- no API key or account needed.

For real, natural-language LLM answers **for free**, get a no-credit-card API key at
https://console.groq.com/keys, then set (in `backend/.env` if running natively, or in a root
`.env` next to `docker-compose.yml` if using Docker -- copy `.env.example` in each case):
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

To use paid OpenAI instead, get a key from platform.openai.com and set:
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

## What's in `data/hr_docs`

Five sample HR policy documents (onboarding guide, benefits summary, leave policy, code of
conduct, remote work policy) so the RAG pipeline has something to index out of the box.

## Uploading new documents from the UI

The sidebar has an **Upload** button (accepts `.md`, `.txt`, `.pdf`) for adding new HR documents
without touching the command line. When you upload a file:
1. It's saved into `data/hr_docs/` (same place the sample docs live).
2. It's chunked and embedded, and just those new chunks are added to the live FAISS index --
   the app does **not** re-process every document from scratch, so this is fast even with a
   large existing document set.
3. It's immediately searchable -- the very next question you ask can retrieve from it, no
   restart needed.
4. Any conversation already in progress is untouched -- uploading runs in the sidebar, chat runs
   in its own component with its own state (see `frontend/src/components/`), and the backend
   guards the shared index with a lock so a chat request and an upload can safely happen at the
   same time (see the comments in `backend/app/rag/chain.py`).

Re-uploading a file with the same name updates its entry rather than duplicating it. You can
still use `python scripts/ingest_docs.py` for bulk/offline ingestion (e.g. re-indexing everything
from scratch) -- the upload button is the fast path for adding one document at a time.

**One limitation worth knowing**: this in-memory-index approach works cleanly for a single
backend process (which is what local dev and `docker-compose` both run). If you later deploy to
Kubernetes with multiple pods/replicas (see `k8s/backend-deployment.yaml`, `replicas: 2`), an
upload updates the index on disk and in the pod that received the request, but *other* replicas
keep serving from their own in-memory copy until they restart or you add a mechanism to broadcast
the update. For a real multi-replica production setup, the next step would be a shared vector
store (e.g. pgvector or a managed vector DB) instead of a per-pod FAISS file -- worth mentioning
if this comes up in an interview as "here's what I'd change to make it horizontally scalable."

## Project layout

```
backend/
  app/
    main.py              FastAPI app, middleware, router wiring
    core/config.py        typed settings (env vars)
    db/models.py           SQLAlchemy models (conversations, messages, feedback, doc metadata)
    api/routes/            chat.py, feedback.py, documents.py, health.py
    rag/
      embeddings.py         local sentence-transformers embedding model
      vector_store.py       FAISS build/save/load/search
      llm_provider.py       OpenAI + free local mock LLM, behind one interface
      chain.py               ties retrieval + generation together
  scripts/ingest_docs.py   CLI: builds the FAISS index + records metadata in Postgres
  tests/                    pytest suite (7 tests, see "What's been verified" below)
frontend/
  src/
    components/            ChatWindow, MessageBubble, Sidebar
    api/client.ts           typed fetch wrapper for the backend
data/hr_docs/               sample HR policy documents (swap in your own)
k8s/                         Kubernetes manifests for AKS
.github/workflows/ci-cd.yml  GitHub Actions pipeline
docker-compose.yml           local dev stack (Postgres + backend + frontend)
```

## What's been verified vs. what you should verify yourself

I ran this project in a sandboxed environment while building it, so here's exactly what was
tested and what wasn't (be upfront about this rather than claim more than is true):

**Verified (actually ran, with passing results):**
- All 7 backend pytest tests pass, including a full chat → conversation persistence → feedback →
  satisfaction-summary flow against a real SQL database.
- The FAISS build/save/load/similarity-search pipeline (`vector_store.py`) runs correctly end to end.
- The free `MockProvider` LLM fallback correctly grounds its answers in retrieved document text.
- The frontend (`npm run build`) compiles with zero TypeScript errors and produces a working Vite bundle.
- All Python and LangChain imports resolve against the pinned `requirements.txt` versions.

**Not run in the sandbox (verify on your own machine):**
- The real `sentence-transformers` embedding model download + inference (needs PyTorch, a few
  hundred MB download -- the sandbox's network didn't allow pulling it, but this is a completely
  standard, widely-used library with no expected issues).
- A real OpenAI API call (needs your API key).
- `docker compose up` end-to-end (the sandbox has no Docker daemon).
- Deployment to a real Azure Kubernetes cluster (needs your Azure account -- see below).

**One environment-specific gotcha found and worth knowing:** this project folder lives under
OneDrive-synced Desktop. OneDrive's file-locking breaks SQLite and can break `npm install`
(you may see `ENOTEMPTY` errors) if it tries to write many files while a sync is in progress. If
you hit that:
- Pause OneDrive syncing temporarily, or
- Delete `frontend/node_modules` (safe -- it's gitignored) and re-run `npm install`.
Postgres itself is unaffected since it's a separate service, not a local file.

## Deploying to Azure AKS (real deployment)

The `k8s/` manifests and `.github/workflows/ci-cd.yml` are ready to use, but actually stand up
an AKS cluster requires your Azure subscription and will incur cloud costs. When you're ready,
we'll go through this together step by step:
1. Create a resource group, Azure Container Registry (ACR), and AKS cluster (`az group create`,
   `az acr create`, `az aks create`).
2. Push the Docker images to ACR.
3. Add the GitHub repo secrets listed at the top of `.github/workflows/ci-cd.yml`.
4. Apply the `k8s/` manifests and set up `k8s/secret.yaml` from the `.example` template.
5. Push to `main` and watch the pipeline deploy.

Just say the word when you want to start this and have your Azure account ready.

## How to talk about this in an interview

See [RESUME_MAPPING.md](./RESUME_MAPPING.md) -- it maps every resume line to the specific files
that implement it, so you can speak to the real design decisions (e.g. why FAISS instead of a
hosted vector DB, why the LLM provider is pluggable, how the HPA scaling actually works).
