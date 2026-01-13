"""Dashboard API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from reconly_core.database.models import Source, Feed, Digest, LLMUsageLog
from reconly_api.dependencies import get_db

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Count entities
    sources_count = db.query(func.count(Source.id)).scalar() or 0
    feeds_count = db.query(func.count(Feed.id)).scalar() or 0
    digests_count = db.query(func.count(Digest.id)).scalar() or 0

    # Token usage today
    tokens_today = db.query(
        func.sum(LLMUsageLog.tokens_in + LLMUsageLog.tokens_out)
    ).filter(
        LLMUsageLog.timestamp >= today
    ).scalar() or 0

    # Token usage this week
    tokens_week = db.query(
        func.sum(LLMUsageLog.tokens_in + LLMUsageLog.tokens_out)
    ).filter(
        LLMUsageLog.timestamp >= week_ago
    ).scalar() or 0

    # Success rate (last week)
    from reconly_core.database.models import FeedRun
    total_runs = db.query(func.count(FeedRun.id)).filter(
        FeedRun.created_at >= week_ago
    ).scalar() or 0

    successful_runs = db.query(func.count(FeedRun.id)).filter(
        FeedRun.created_at >= week_ago,
        FeedRun.status == 'completed'
    ).scalar() or 0

    success_rate = round((successful_runs / total_runs * 100), 1) if total_runs > 0 else 0

    return {
        "sources_count": sources_count,
        "feeds_count": feeds_count,
        "digests_count": digests_count,
        "tokens_today": tokens_today,
        "tokens_week": tokens_week,
        "success_rate": success_rate,
    }
