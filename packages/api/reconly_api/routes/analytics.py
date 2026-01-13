"""Analytics API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from reconly_core.database.models import LLMUsageLog, FeedRun, Feed, Digest
from reconly_api.dependencies import get_db

router = APIRouter()


def parse_period(period: str) -> datetime:
    """Parse period string to datetime."""
    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 7)
    return datetime.utcnow() - timedelta(days=days)


@router.get("/summary")
async def get_analytics_summary(
    period: str = "7d",
    db: Session = Depends(get_db)
):
    """Get analytics summary."""
    since = parse_period(period)

    # Token totals
    token_stats = db.query(
        func.sum(LLMUsageLog.tokens_in).label('total_tokens_in'),
        func.sum(LLMUsageLog.tokens_out).label('total_tokens_out'),
        func.count(LLMUsageLog.id).label('total_requests'),
    ).filter(LLMUsageLog.timestamp >= since).first()

    # Success rate
    total_runs = db.query(func.count(FeedRun.id)).filter(
        FeedRun.created_at >= since
    ).scalar() or 0

    successful_runs = db.query(func.count(FeedRun.id)).filter(
        FeedRun.created_at >= since,
        FeedRun.status == 'completed'
    ).scalar() or 0

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    # Total digests
    total_digests = db.query(func.count(Digest.id)).filter(
        Digest.created_at >= since
    ).scalar() or 0

    return {
        "total_tokens_in": token_stats.total_tokens_in or 0,
        "total_tokens_out": token_stats.total_tokens_out or 0,
        "success_rate": round(success_rate, 2),
        "total_runs": total_runs,
        "total_digests": total_digests,
    }


@router.get("/tokens-by-provider")
async def get_tokens_by_provider(
    period: str = "7d",
    db: Session = Depends(get_db)
):
    """Get token usage by provider with model breakdown."""
    since = parse_period(period)

    # Get provider-level aggregates
    provider_results = db.query(
        LLMUsageLog.provider,
        func.sum(LLMUsageLog.tokens_in).label('tokens_in'),
        func.sum(LLMUsageLog.tokens_out).label('tokens_out'),
    ).filter(
        LLMUsageLog.timestamp >= since
    ).group_by(
        LLMUsageLog.provider
    ).all()

    total_tokens = sum((r.tokens_in or 0) + (r.tokens_out or 0) for r in provider_results)

    # Get model-level breakdown for each provider
    model_results = db.query(
        LLMUsageLog.provider,
        LLMUsageLog.model,
        func.sum(LLMUsageLog.tokens_in).label('tokens_in'),
        func.sum(LLMUsageLog.tokens_out).label('tokens_out'),
    ).filter(
        LLMUsageLog.timestamp >= since
    ).group_by(
        LLMUsageLog.provider,
        LLMUsageLog.model
    ).all()

    # Build provider -> models mapping
    provider_models = {}
    for r in model_results:
        if r.provider not in provider_models:
            provider_models[r.provider] = []
        model_tokens = (r.tokens_in or 0) + (r.tokens_out or 0)
        provider_models[r.provider].append({
            "model": r.model,
            "tokens_in": r.tokens_in or 0,
            "tokens_out": r.tokens_out or 0,
            "total_tokens": model_tokens,
        })

    # Calculate percentages for models within each provider
    for provider, models in provider_models.items():
        provider_total = sum(m["total_tokens"] for m in models)
        for model in models:
            model["percentage"] = round((model["total_tokens"] / provider_total * 100), 1) if provider_total > 0 else 0
        # Sort models by total tokens descending
        models.sort(key=lambda m: m["total_tokens"], reverse=True)

    # Build response
    response = []
    for r in provider_results:
        provider_tokens = (r.tokens_in or 0) + (r.tokens_out or 0)
        response.append({
            "provider": r.provider,
            "tokens_in": r.tokens_in or 0,
            "tokens_out": r.tokens_out or 0,
            "total_tokens": provider_tokens,
            "percentage": round((provider_tokens / total_tokens * 100), 1) if total_tokens > 0 else 0,
            "models": provider_models.get(r.provider, [])
        })

    # Sort by total tokens descending
    response.sort(key=lambda p: p["total_tokens"], reverse=True)

    return response


@router.get("/tokens-by-feed")
async def get_tokens_by_feed(
    period: str = "7d",
    db: Session = Depends(get_db)
):
    """Get token usage by feed."""
    since = parse_period(period)

    results = db.query(
        FeedRun.feed_id,
        Feed.name.label('feed_name'),
        func.count(FeedRun.id).label('run_count'),
        func.sum(FeedRun.items_processed).label('digest_count'),
        func.sum(FeedRun.total_tokens_in).label('tokens_in'),
        func.sum(FeedRun.total_tokens_out).label('tokens_out'),
    ).join(
        Feed, FeedRun.feed_id == Feed.id
    ).filter(
        FeedRun.created_at >= since
    ).group_by(
        FeedRun.feed_id, Feed.name
    ).all()

    return [
        {
            "feed_id": r.feed_id,
            "feed_name": r.feed_name,
            "run_count": r.run_count or 0,
            "digest_count": r.digest_count or 0,
            "tokens_in": r.tokens_in or 0,
            "tokens_out": r.tokens_out or 0,
        }
        for r in results
    ]


@router.get("/usage")
async def get_usage_over_time(
    period: str = "7d",
    db: Session = Depends(get_db)
):
    """Get usage over time."""
    since = parse_period(period)

    results = db.query(
        func.date(LLMUsageLog.timestamp).label('date'),
        func.sum(LLMUsageLog.tokens_in).label('tokens_in'),
        func.sum(LLMUsageLog.tokens_out).label('tokens_out'),
    ).filter(
        LLMUsageLog.timestamp >= since
    ).group_by(
        func.date(LLMUsageLog.timestamp)
    ).order_by(
        func.date(LLMUsageLog.timestamp)
    ).all()

    return [
        {
            "date": str(r.date),
            "tokens_in": r.tokens_in or 0,
            "tokens_out": r.tokens_out or 0,
        }
        for r in results
    ]
