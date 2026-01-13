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
    triggered_by_user_id: Optional[int] = None
) -> dict:
    """
    Run a specific feed.

    Args:
        feed_id: Feed ID to run
        triggered_by: How the run was triggered (schedule, manual, api)
        triggered_by_user_id: User who triggered (if manual/api)

    Returns:
        Run result dictionary
    """
    from reconly_core.services.feed_service import FeedService, FeedRunOptions

    try:
        service = FeedService(database_url=settings.database_url)

        options = FeedRunOptions(
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
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
        return {
            "success": False,
            "feed_id": feed_id,
            "error": str(e),
        }
