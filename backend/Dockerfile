# --- Backend Dockerfile ---
# Multi-stage-ish simple build: slim Python base, install deps, copy code.
# Runs as a non-root user and exposes a healthcheck so Docker/Kubernetes
# can tell when the container is actually ready to serve traffic.

FROM python:3.11-slim

WORKDIR /app

# System deps needed by psycopg2 (Postgres driver) and faiss.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user (defense in depth for the K8s pod).
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -f http://localhost:8000/health/live || exit 1

# --workers 2: a small, sane default for a single pod; the real scaling
# lever is horizontal (more pods via the K8s HPA, see k8s/backend-hpa.yaml)
# rather than more workers per pod.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
