"""
Feedback endpoint: thumbs up / down on an assistant answer.

This is what powers the "measured impact via response accuracy, query
resolution rate, and user satisfaction scores" line on the resume -- every
rating lands in the `feedback` table (app/db/models.py) and can be
aggregated into a satisfaction/resolution-rate metric (see
GET /api/feedback/summary below).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Feedback, Message
from app.schemas.chat import FeedbackRequest

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback")
def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    message = db.get(Message, request.message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    existing = db.query(Feedback).filter(Feedback.message_id == request.message_id).first()
    if existing:
        existing.rating = request.rating
        existing.comment = request.comment
    else:
        db.add(Feedback(message_id=request.message_id, rating=request.rating, comment=request.comment))
    db.commit()
    return {"status": "recorded"}


@router.get("/feedback/summary")
def feedback_summary(db: Session = Depends(get_db)):
    """Simple satisfaction metric: % of ratings that were positive."""
    total = db.query(func.count(Feedback.id)).scalar() or 0
    positive = db.query(func.count(Feedback.id)).filter(Feedback.rating == 1).scalar() or 0
    satisfaction_rate = round(positive / total, 3) if total else None
    return {"total_ratings": total, "positive_ratings": positive, "satisfaction_rate": satisfaction_rate}
