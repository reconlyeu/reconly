"""Feed run history API routes."""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from reconly_core.database.models import FeedRun, Digest, FeedSource
from reconly_api.dependencies import get_db
from reconly_api.schemas.feeds import FeedRunResponse, FeedRunDetailResponse
from reconly_api.schemas.digest import DigestResponse

router = APIRouter()


class FeedRunListResponse(BaseModel):
    """Response for feed run list with pagination."""
    items: List[FeedRunResponse]
    total: int


class FeedRunSourceStatus(BaseModel):
    """Status of a source in a feed run."""
    source_id: int
    source_name: str
    source_type: str
    source_url: Optional[str] = None
    status: str  # success, failed, pending
    error_message: Optional[str] = None


class FeedRunSourcesResponse(BaseModel):
    """Response for feed run sources status."""
    run_id: int
    sources: List[FeedRunSourceStatus]


def _build_feed_run_response(run: FeedRun) -> dict:
    """Build a FeedRunResponse dict from a FeedRun model with feed_name."""
    # Calculate duration if both timestamps are available
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    return {
        "id": run.id,
        "feed_id": run.feed_id,
        "feed_name": run.feed.name if run.feed else None,
        "triggered_by": run.triggered_by,
        "triggered_by_user_id": run.triggered_by_user_id,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "sources_total": run.sources_total,
        "sources_processed": run.sources_processed,
        "sources_failed": run.sources_failed,
        "items_processed": run.items_processed,
        "total_tokens_in": run.total_tokens_in,
        "total_tokens_out": run.total_tokens_out,
        "total_cost": run.total_cost,
        "error_log": run.error_log,
        "error_details": run.error_details,
        "trace_id": run.trace_id,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "created_at": run.created_at,
        "duration_seconds": duration_seconds,
    }


@router.get("", response_model=FeedRunListResponse)
async def list_feed_runs(
    feed_id: Optional[int] = Query(None, description="Filter by feed ID"),
    status: Optional[str] = Query(None, description="Filter by status (pending, running, completed, failed)"),
    from_date: Optional[datetime] = Query(None, description="Filter by start date (inclusive)"),
    to_date: Optional[datetime] = Query(None, description="Filter by end date (inclusive)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """
    List feed run history with optional filtering.

    Returns recent feed runs ordered by created_at (newest first).
    Supports filtering by feed_id, status, and date range.
    """
    query = db.query(FeedRun).options(joinedload(FeedRun.feed))

    if feed_id is not None:
        query = query.filter(FeedRun.feed_id == feed_id)

    if status:
        query = query.filter(FeedRun.status == status)

    if from_date:
        query = query.filter(FeedRun.created_at >= from_date)

    if to_date:
        query = query.filter(FeedRun.created_at <= to_date)

    # Get total count for pagination
    total = query.count()

    feed_runs = query.order_by(
        FeedRun.created_at.desc()
    ).limit(limit).offset(offset).all()

    items = [FeedRunResponse(**_build_feed_run_response(run)) for run in feed_runs]
    return FeedRunListResponse(items=items, total=total)


@router.get("/{run_id}", response_model=FeedRunDetailResponse)
async def get_feed_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details of a specific feed run.

    Returns comprehensive information about a single feed run including
    metrics, timing, status, feed name, and digest count.
    """
    feed_run = db.query(FeedRun).options(
        joinedload(FeedRun.feed)
    ).filter(FeedRun.id == run_id).first()

    if not feed_run:
        raise HTTPException(status_code=404, detail="Feed run not found")

    # Count digests created in this run
    digests_count = db.query(Digest).filter(Digest.feed_run_id == run_id).count()

    response_dict = _build_feed_run_response(feed_run)
    response_dict["digests_count"] = digests_count
    response_dict["duration_seconds"] = feed_run.duration_seconds

    return FeedRunDetailResponse(**response_dict)


@router.get("/{run_id}/sources", response_model=FeedRunSourcesResponse)
async def get_feed_run_sources(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Get per-source status for a specific feed run.

    Returns the status of each source that was processed during the run,
    including any error messages for failed sources.
    """
    # Get the feed run with its feed
    feed_run = db.query(FeedRun).options(
        joinedload(FeedRun.feed)
    ).filter(FeedRun.id == run_id).first()

    if not feed_run:
        raise HTTPException(status_code=404, detail="Feed run not found")

    # Get all sources for this feed
    feed_sources = db.query(FeedSource).options(
        joinedload(FeedSource.source)
    ).filter(
        FeedSource.feed_id == feed_run.feed_id,
        FeedSource.enabled == True
    ).all()

    # Parse error_details to identify failed sources
    failed_sources = {}
    if feed_run.error_details and isinstance(feed_run.error_details, dict):
        errors = feed_run.error_details.get("errors", [])
        for error in errors:
            source_id = error.get("source_id")
            if source_id:
                failed_sources[source_id] = error.get("message", "Unknown error")

    sources = []
    for fs in feed_sources:
        source = fs.source
        if source:
            status = "failed" if source.id in failed_sources else "success"
            sources.append(FeedRunSourceStatus(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                source_url=source.url,
                status=status,
                error_message=failed_sources.get(source.id)
            ))

    return FeedRunSourcesResponse(run_id=run_id, sources=sources)


@router.get("/{run_id}/digests", response_model=List[DigestResponse])
async def get_feed_run_digests(
    run_id: int,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """
    Get all digests created during a specific feed run.

    Returns a list of digests that were generated as part of this feed run,
    ordered by creation time (newest first).
    """
    # First check if the feed run exists
    feed_run = db.query(FeedRun).filter(FeedRun.id == run_id).first()
    if not feed_run:
        raise HTTPException(status_code=404, detail="Feed run not found")

    # Query digests for this feed run with eager loading of llm_usage_logs for token counts
    digests = db.query(Digest).options(
        joinedload(Digest.llm_usage_logs)
    ).filter(
        Digest.feed_run_id == run_id
    ).order_by(
        Digest.created_at.desc()
    ).limit(limit).offset(offset).all()

    return [DigestResponse(**digest.to_dict()) for digest in digests]
