"""In-process scheduler using APScheduler.

This scheduler runs feed schedules automatically based on cron expressions.
It uses the local timezone by default (configurable via SCHEDULER_TIMEZONE).
No external dependencies like Redis or Celery required.
"""
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from reconly_api.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None
_scheduler_timezone: Optional[str] = None


def get_scheduler() -> Optional[BackgroundScheduler]:
    """Get the global scheduler instance."""
    return _scheduler


def _run_feed(feed_id: int, feed_name: str) -> None:
    """Execute a scheduled feed run.

    This runs in a thread pool to avoid blocking the scheduler.
    """
    from reconly_core.services.feed_service import FeedService, FeedRunOptions

    logger.info(f"Scheduler triggering feed: {feed_name} (ID: {feed_id})")

    try:
        service = FeedService(database_url=settings.database_url)

        options = FeedRunOptions(
            triggered_by="schedule",
            enable_fallback=True,
            show_progress=False,
        )

        result = service.run_feed(feed_id, options)

        logger.info(
            f"Scheduled feed completed: {feed_name} - "
            f"status={result.status}, items={result.items_processed}"
        )

    except Exception as e:
        logger.error(f"Scheduled feed failed: {feed_name} (ID: {feed_id}) - {e}", exc_info=True)


def _parse_cron_expression(cron_expr: str) -> dict:
    """Parse a 5-field cron expression into APScheduler CronTrigger kwargs.

    Format: minute hour day_of_month month day_of_week
    Example: "0 9 * * *" -> daily at 9:00 AM
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr} (expected 5 fields)")

    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def init_scheduler() -> BackgroundScheduler:
    """Initialize the APScheduler background scheduler.

    Call this on application startup.
    """
    global _scheduler, _scheduler_timezone

    if _scheduler is not None:
        logger.warning("Scheduler already initialized")
        return _scheduler

    # Determine timezone
    timezone = settings.scheduler_timezone or "local"
    if timezone == "local":
        import tzlocal
        try:
            timezone = str(tzlocal.get_localzone())
        except Exception:
            timezone = "UTC"
            logger.warning("Could not detect local timezone, using UTC")

    _scheduler_timezone = timezone
    logger.info(f"Initializing scheduler with timezone: {timezone}")

    # Configure scheduler
    jobstores = {
        "default": MemoryJobStore()
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=3)
    }
    job_defaults = {
        "coalesce": True,  # Combine missed runs into one
        "max_instances": 1,  # Don't run same feed concurrently
        "misfire_grace_time": 60 * 60,  # 1 hour grace for missed jobs
    }

    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=timezone,
    )

    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler and load all feed schedules."""
    global _scheduler

    if _scheduler is None:
        init_scheduler()

    if _scheduler.running:
        logger.warning("Scheduler already running")
        return

    # Start the scheduler FIRST, then load jobs
    # This ensures proper next_run_time calculation
    _scheduler.start()
    logger.info("Scheduler started")

    # Load all scheduled feeds (now that scheduler is running)
    sync_all_feed_schedules()

    # Log all scheduled jobs with their next run times
    _log_scheduled_jobs()


def _log_scheduled_jobs() -> None:
    """Log all scheduled feed jobs with their next run times."""
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    jobs = [j for j in _scheduler.get_jobs() if j.id.startswith("feed_")]
    if not jobs:
        logger.info("No feeds scheduled")
        return

    logger.info(f"Scheduled feeds ({len(jobs)}):")
    for job in jobs:
        next_run = getattr(job, 'next_run_time', None)
        if next_run:
            logger.info(f"  - {job.name}: next run at {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            logger.info(f"  - {job.name}: (no next run time)")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")


def sync_all_feed_schedules() -> int:
    """Load/reload all feed schedules from the database.

    Returns the number of schedules loaded.
    """
    global _scheduler

    if _scheduler is None:
        logger.warning("Scheduler not initialized")
        return 0

    from reconly_core.database.models import Feed
    from reconly_core.database.crud import DigestDB

    try:
        db = DigestDB(database_url=settings.database_url)

        # Get all enabled scheduled feeds
        feeds = db.session.query(Feed).filter(
            Feed.schedule_enabled == True,
            Feed.schedule_cron != None,
        ).all()

        # Remove all existing feed jobs
        existing_jobs = [j for j in _scheduler.get_jobs() if j.id.startswith("feed_")]
        for job in existing_jobs:
            job.remove()

        # Add jobs for each feed
        count = 0
        for feed in feeds:
            try:
                add_feed_schedule(feed.id, feed.name, feed.schedule_cron)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to schedule feed {feed.id}: {e}")

        logger.info(f"Loaded {count} feed schedules")
        return count

    except Exception as e:
        logger.error(f"Failed to sync feed schedules: {e}", exc_info=True)
        return 0


def add_feed_schedule(feed_id: int, feed_name: str, cron_expression: str) -> bool:
    """Add or update a feed schedule.

    Args:
        feed_id: The feed ID
        feed_name: The feed name (for logging)
        cron_expression: 5-field cron expression

    Returns:
        True if successfully scheduled
    """
    global _scheduler, _scheduler_timezone

    if _scheduler is None:
        logger.warning("Scheduler not initialized, cannot add feed schedule")
        return False

    job_id = f"feed_{feed_id}"

    try:
        # Parse cron expression
        cron_kwargs = _parse_cron_expression(cron_expression)
        # Pass timezone to ensure correct next_run_time calculation
        trigger = CronTrigger(**cron_kwargs, timezone=_scheduler_timezone)

        # Remove existing job if any
        existing = _scheduler.get_job(job_id)
        if existing:
            existing.remove()

        # Add new job
        _scheduler.add_job(
            _run_feed,
            trigger=trigger,
            args=[feed_id, feed_name],
            id=job_id,
            name=f"Feed: {feed_name}",
            replace_existing=True,
        )

        # Log next run time (only available after scheduler is running)
        if _scheduler.running:
            job = _scheduler.get_job(job_id)
            if job:
                next_run = getattr(job, 'next_run_time', None)
                if next_run:
                    logger.info(
                        f"Scheduled feed '{feed_name}' (ID: {feed_id}) - "
                        f"cron: {cron_expression}, next run: {next_run}"
                    )
                else:
                    logger.info(
                        f"Scheduled feed '{feed_name}' (ID: {feed_id}) - "
                        f"cron: {cron_expression}"
                    )

        return True

    except Exception as e:
        logger.error(f"Failed to schedule feed {feed_id}: {e}")
        return False


def remove_feed_schedule(feed_id: int) -> bool:
    """Remove a feed from the schedule.

    Args:
        feed_id: The feed ID

    Returns:
        True if removed, False if not found
    """
    global _scheduler

    if _scheduler is None:
        return False

    job_id = f"feed_{feed_id}"
    job = _scheduler.get_job(job_id)

    if job:
        job.remove()
        logger.info(f"Removed feed schedule: {job_id}")
        return True

    return False


def update_feed_schedule(feed_id: int, feed_name: str, cron_expression: Optional[str], enabled: bool) -> None:
    """Update a feed's schedule (called when feed is created/updated).

    Args:
        feed_id: The feed ID
        feed_name: The feed name
        cron_expression: New cron expression (or None)
        enabled: Whether scheduling is enabled
    """
    if enabled and cron_expression:
        add_feed_schedule(feed_id, feed_name, cron_expression)
    else:
        remove_feed_schedule(feed_id)


def get_scheduled_feeds_info() -> list[dict]:
    """Get info about all scheduled feed jobs.

    Returns list of dicts with job info for debugging/display.
    """
    global _scheduler

    if _scheduler is None:
        return []

    result = []
    for job in _scheduler.get_jobs():
        if job.id.startswith("feed_"):
            result.append({
                "job_id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

    return result
