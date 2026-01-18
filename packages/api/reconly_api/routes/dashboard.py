"""Dashboard API routes."""
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from reconly_api.dependencies import get_db
from reconly_api.schemas.dashboard import DashboardInsights
from reconly_api.schemas.digest import DigestResponse, DigestList
from reconly_api.schemas.feeds import FeedResponse
from reconly_core.database.models import Digest, Feed, FeedRun, LLMUsageLog, Source
from reconly_core.services.dashboard_service import DashboardService

router = APIRouter()


class DigestTimeFilter(str, Enum):
    """Time filter options for dashboard digests."""
    TODAY = "today"
    WEEK = "week"
    ALL = "all"


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


@router.get("/insights", response_model=DashboardInsights)
async def get_dashboard_insights(db: Session = Depends(get_db)) -> DashboardInsights:
    """Get actionable dashboard insights.

    Returns user-valuable metrics including:
    - new_today: Count of digests created in last 24 hours
    - new_this_week: Count of digests created in last 7 days
    - total_digests: Total digest count
    - feeds_healthy: Count of feeds with no recent errors
    - feeds_failing: Count of feeds with recent errors
    - last_sync_at: Timestamp of most recent completed feed run
    """
    service = DashboardService(db)
    insights = service.get_insights()
    return DashboardInsights(**insights)


@router.get("/digests", response_model=DigestList)
async def get_dashboard_digests(
    since: DigestTimeFilter = Query(
        DigestTimeFilter.ALL,
        description="Time filter: 'today', 'week', or 'all'"
    ),
    limit: int = Query(8, ge=1, le=20, description="Maximum number of digests to return"),
    db: Session = Depends(get_db)
) -> DigestList:
    """Get recent digests for the dashboard with time filtering.

    - **since**: Time filter - 'today' (last 24h), 'week' (last 7 days), or 'all'
    - **limit**: Maximum number of digests (default 8, max 20)

    Returns digests ordered by creation date (newest first).
    """
    # Build base query with eager loading
    query = db.query(Digest).options(joinedload(Digest.llm_usage_logs))

    # Apply time filter
    now = datetime.utcnow()
    if since == DigestTimeFilter.TODAY:
        # Last 24 hours
        cutoff = now - timedelta(hours=24)
        query = query.filter(Digest.created_at >= cutoff)
    elif since == DigestTimeFilter.WEEK:
        # Last 7 days
        cutoff = now - timedelta(days=7)
        query = query.filter(Digest.created_at >= cutoff)
    # For 'all', no time filter needed

    # Get total count before applying limit
    total_count = query.count()

    # Order by created_at descending and apply limit
    query = query.order_by(Digest.created_at.desc()).limit(limit)

    # Execute query and convert to response format
    digests_data = query.all()
    digests = [DigestResponse(**digest.to_dict()) for digest in digests_data]

    return DigestList(total=total_count, digests=digests)


@router.get("/feeds", response_model=list[FeedResponse])
async def get_dashboard_feeds(
    since: DigestTimeFilter = Query(
        DigestTimeFilter.ALL,
        description="Time filter: 'today', 'week', or 'all'"
    ),
    limit: int = Query(6, ge=1, le=20, description="Maximum number of feeds to return"),
    db: Session = Depends(get_db)
) -> list[FeedResponse]:
    """Get recently run feeds for the dashboard with time filtering.

    - **since**: Time filter - 'today' (last 24h), 'week' (last 7 days), or 'all'
    - **limit**: Maximum number of feeds (default 6, max 20)

    Returns feeds ordered by last_run_at (most recently run first).
    Only includes feeds that have been run at least once.
    """
    from reconly_core.database.models import FeedSource

    # Build query for feeds that have been run
    query = db.query(Feed).options(
        joinedload(Feed.feed_sources).joinedload(FeedSource.source)
    ).filter(Feed.last_run_at.isnot(None))

    # Apply time filter
    now = datetime.utcnow()
    if since == DigestTimeFilter.TODAY:
        cutoff = now - timedelta(hours=24)
        query = query.filter(Feed.last_run_at >= cutoff)
    elif since == DigestTimeFilter.WEEK:
        cutoff = now - timedelta(days=7)
        query = query.filter(Feed.last_run_at >= cutoff)

    # Order by last_run_at descending and apply limit
    feeds = query.order_by(Feed.last_run_at.desc()).limit(limit).all()

    return [FeedResponse.model_validate(f) for f in feeds]
