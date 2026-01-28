"""Feed processing tasks.

Simple task functions for running feeds. These can be called directly
or via FastAPI BackgroundTasks for async execution.
"""
import logging
from typing import Optional

from reconly_api.config import settings

logger = logging.getLogger(__name__)


def run_feed_task(
    feed_id: int,
    triggered_by: str = "manual",
    triggered_by_user_id: Optional[int] = None,
    feed_run_id: Optional[int] = None
) -> dict:
    """
    Run a specific feed.

    Args:
        feed_id: Feed ID to run
        triggered_by: How the run was triggered (schedule, manual, api)
        triggered_by_user_id: User who triggered (if manual/api)
        feed_run_id: Existing FeedRun ID to update (if created synchronously)

    Returns:
        Run result dictionary
    """
    from reconly_core.services.feed_service import FeedService, FeedRunOptions

    try:
        service = FeedService(database_url=settings.database_url)

        options = FeedRunOptions(
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
            feed_run_id=feed_run_id,
            enable_fallback=True,
            show_progress=False,
        )

        result = service.run_feed(feed_id, options)

        return {
            "success": True,
            "feed_run_id": result.feed_run_id,
            "feed_id": result.feed_id,
            "feed_name": result.feed_name,
            "status": result.status,
            "sources_processed": result.sources_processed,
            "sources_failed": result.sources_failed,
            "items_processed": result.items_processed,
            "total_cost": result.total_cost,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
        }

    except Exception as e:
        logger.error(f"Failed to run feed {feed_id}: {e}", exc_info=True)

        # Update FeedRun status to 'failed' if we have a feed_run_id
        # This ensures the run doesn't stay stuck in 'running' status
        if feed_run_id:
            try:
                from datetime import datetime
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                from reconly_core.database.models import FeedRun

                engine = create_engine(settings.database_url)
                Session = sessionmaker(bind=engine)
                session = Session()
                try:
                    feed_run = session.query(FeedRun).filter(FeedRun.id == feed_run_id).first()
                    if feed_run and feed_run.status == "running":
                        feed_run.status = "failed"
                        feed_run.completed_at = datetime.utcnow()
                        feed_run.error_log = str(e)
                        session.commit()
                        logger.info(f"Updated FeedRun {feed_run_id} status to 'failed'")
                finally:
                    session.close()
            except Exception as db_error:
                logger.error(f"Failed to update FeedRun {feed_run_id} status: {db_error}")

        return {
            "success": False,
            "feed_id": feed_id,
            "error": str(e),
        }
