"""
Health check endpoints.

Kubernetes uses these to decide whether a pod is alive (liveness) and
ready to receive traffic (readiness) -- see k8s/backend-deployment.yaml.
A bad readiness probe here would cause AKS to keep routing traffic to a
pod that can't reach the database, so we actually check the DB connection
rather than just returning 200 unconditionally.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness():
    """Is the process up at all? Always returns ok if the app is running."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    """Is the app ready to serve traffic (i.e. can it reach Postgres)?"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001 - deliberately broad for a health check
        return {"status": "error", "database": str(exc)}
