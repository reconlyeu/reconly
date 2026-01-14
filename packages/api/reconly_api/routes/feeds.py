"""Feed management API routes."""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from datetime import datetime
from croniter import croniter

from reconly_core.database.models import Feed, FeedSource
from reconly_api.dependencies import get_db, limiter
from reconly_api.schemas.feeds import FeedCreate, FeedUpdate, FeedResponse
from reconly_api.schemas.batch import BatchDeleteRequest, BatchDeleteResponse
from reconly_api.tasks.feed_tasks import run_feed_task

logger = logging.getLogger(__name__)
router = APIRouter()


def _sync_feed_schedule(feed_id: int, feed_name: str, cron_expr: Optional[str], enabled: bool) -> None:
    """Sync a feed's schedule with the scheduler."""
    try:
        from reconly_api.scheduler import update_feed_schedule
        update_feed_schedule(feed_id, feed_name, cron_expr, enabled)
    except Exception as e:
        logger.warning(f"Failed to sync feed schedule: {e}")


def _remove_feed_schedule(feed_id: int) -> None:
    """Remove a feed from the scheduler."""
    try:
        from reconly_api.scheduler import remove_feed_schedule
        remove_feed_schedule(feed_id)
    except Exception as e:
        logger.warning(f"Failed to remove feed schedule: {e}")


@router.get("", response_model=List[FeedResponse])
async def list_feeds(
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all feeds."""
    from sqlalchemy.orm import joinedload

    query = db.query(Feed).options(
        joinedload(Feed.feed_sources).joinedload(FeedSource.source)
    )
    if enabled_only:
        query = query.filter(Feed.schedule_enabled == True)

    feeds = query.order_by(Feed.created_at.desc()).all()
    return [FeedResponse.model_validate(f) for f in feeds]


@router.post("", response_model=FeedResponse, status_code=201)
@limiter.limit("10/minute")
async def create_feed(
    request: Request,
    feed: FeedCreate,
    db: Session = Depends(get_db)
):
    """Create a new feed.

    Rate limited to 10 requests per minute per IP.
    """
    db_feed = Feed(
        name=feed.name,
        description=feed.description,
        schedule_cron=feed.schedule_cron,
        schedule_enabled=feed.schedule_enabled,
        prompt_template_id=feed.prompt_template_id,
        report_template_id=feed.report_template_id,
        model_provider=feed.model_provider,
        model_name=feed.model_name,
        output_config=feed.output_config,
    )

    # Calculate next_run_at if schedule is enabled
    if feed.schedule_enabled and feed.schedule_cron:
        try:
            cron = croniter(feed.schedule_cron, datetime.utcnow())
            db_feed.next_run_at = cron.get_next(datetime)
        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid cron expression: {e}")

    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)

    # Add sources
    if feed.source_ids:
        for priority, source_id in enumerate(feed.source_ids):
            feed_source = FeedSource(
                feed_id=db_feed.id,
                source_id=source_id,
                priority=priority,
                enabled=True
            )
            db.add(feed_source)
        db.commit()

    db.refresh(db_feed)

    # Sync with scheduler
    _sync_feed_schedule(db_feed.id, db_feed.name, db_feed.schedule_cron, db_feed.schedule_enabled)

    return FeedResponse.model_validate(db_feed)


@router.get("/{feed_id}", response_model=FeedResponse)
async def get_feed(
    feed_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific feed."""
    feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return FeedResponse.model_validate(feed)


@router.put("/{feed_id}", response_model=FeedResponse)
async def update_feed(
    feed_id: int,
    feed_update: FeedUpdate,
    db: Session = Depends(get_db)
):
    """Update a feed."""
    from sqlalchemy.orm import joinedload

    db_feed = db.query(Feed).options(
        joinedload(Feed.feed_sources)
    ).filter(Feed.id == feed_id).first()
    if not db_feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    update_data = feed_update.model_dump(exclude_unset=True)
    logger.info(f"Feed update received: {update_data}")

    # Handle source_ids separately
    source_ids = update_data.pop('source_ids', None)
    logger.info(f"source_ids extracted: {source_ids}")

    for key, value in update_data.items():
        setattr(db_feed, key, value)

    # Recalculate next_run_at if schedule changed
    if 'schedule_cron' in update_data or 'schedule_enabled' in update_data:
        if db_feed.schedule_enabled and db_feed.schedule_cron:
            try:
                cron = croniter(db_feed.schedule_cron, datetime.utcnow())
                db_feed.next_run_at = cron.get_next(datetime)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid cron expression: {e}")

    # Update sources if provided
    if source_ids is not None:
        # Delete existing feed sources
        db.query(FeedSource).filter(FeedSource.feed_id == feed_id).delete()

        # Add new feed sources
        for priority, source_id in enumerate(source_ids):
            feed_source = FeedSource(
                feed_id=feed_id,
                source_id=source_id,
                priority=priority,
                enabled=True
            )
            db.add(feed_source)

    db.commit()
    db.refresh(db_feed)

    # Sync with scheduler
    _sync_feed_schedule(db_feed.id, db_feed.name, db_feed.schedule_cron, db_feed.schedule_enabled)

    return FeedResponse.model_validate(db_feed)


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(
    feed_id: int,
    db: Session = Depends(get_db)
):
    """Delete a feed."""
    feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    db.delete(feed)
    db.commit()

    # Remove from scheduler
    _remove_feed_schedule(feed_id)

    return None


@router.post("/{feed_id}/run")
async def run_feed(
    feed_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger a manual feed run."""
    feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    # Trigger async task
    background_tasks.add_task(run_feed_task, feed_id, "manual", None)

    return {"message": "Feed run started", "feed_id": feed_id}


@router.get("/{feed_id}/runs")
async def get_feed_runs(
    feed_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get run history for a feed."""
    from reconly_core.database.models import FeedRun

    feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    runs = db.query(FeedRun).filter(
        FeedRun.feed_id == feed_id
    ).order_by(FeedRun.created_at.desc()).limit(limit).all()

    return runs


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_feeds(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple feeds by ID."""
    deleted_count = 0
    deleted_ids = []
    failed_ids = []

    for feed_id in request.ids:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        if feed:
            db.delete(feed)
            deleted_count += 1
            deleted_ids.append(feed_id)
        else:
            failed_ids.append(feed_id)

    db.commit()

    # Remove from scheduler
    for feed_id in deleted_ids:
        _remove_feed_schedule(feed_id)

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )
