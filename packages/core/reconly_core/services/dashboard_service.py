"""Dashboard service for actionable user insights.

Provides metrics focused on user-valuable information rather than system telemetry.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from reconly_core.database.models import Digest, FeedRun


class DashboardService:
    """Service for computing dashboard insights."""

    def __init__(self, db: Session):
        """Initialize the dashboard service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_insights(self) -> dict:
        """Get actionable dashboard insights.

        Returns:
            Dictionary containing:
            - new_today: Count of digests created in last 24 hours
            - new_this_week: Count of digests created in last 7 days
            - total_digests: Total digest count
            - feeds_healthy: Count of feeds with no recent errors
            - feeds_failing: Count of feeds with recent errors
            - last_sync_at: Timestamp of most recent completed feed run (ISO format or None)
        """
        now = datetime.utcnow()
        today_start = now - timedelta(hours=24)
        week_start = now - timedelta(days=7)

        # Count digests created in last 24 hours
        new_today = self.db.query(func.count(Digest.id)).filter(
            Digest.created_at >= today_start
        ).scalar() or 0

        # Count digests created in last 7 days
        new_this_week = self.db.query(func.count(Digest.id)).filter(
            Digest.created_at >= week_start
        ).scalar() or 0

        # Total digest count
        total_digests = self.db.query(func.count(Digest.id)).scalar() or 0

        # Feed health: count feeds with recent successful vs failed runs
        # A feed is "healthy" if its most recent run was successful
        # A feed is "failing" if its most recent run failed
        feeds_healthy, feeds_failing = self._get_feed_health_counts()

        # Get timestamp of most recent completed feed run
        last_sync_at = self._get_last_sync_timestamp()

        # Get daily counts for sparkline (last 7 days)
        daily_counts = self._get_daily_digest_counts(7)

        # Get change from yesterday
        yesterday_start = now - timedelta(hours=48)
        yesterday_end = now - timedelta(hours=24)
        new_yesterday = self.db.query(func.count(Digest.id)).filter(
            Digest.created_at >= yesterday_start,
            Digest.created_at < yesterday_end
        ).scalar() or 0

        # Get change from last week
        last_week_start = now - timedelta(days=14)
        last_week_end = now - timedelta(days=7)
        new_last_week = self.db.query(func.count(Digest.id)).filter(
            Digest.created_at >= last_week_start,
            Digest.created_at < last_week_end
        ).scalar() or 0

        return {
            "new_today": new_today,
            "new_this_week": new_this_week,
            "total_digests": total_digests,
            "feeds_healthy": feeds_healthy,
            "feeds_failing": feeds_failing,
            "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
            "daily_counts": daily_counts,
            "change_today": new_today - new_yesterday,
            "change_week": new_this_week - new_last_week,
        }

    def _get_feed_health_counts(self) -> tuple[int, int]:
        """Count feeds with healthy vs failing status based on their most recent run.

        A feed is considered:
        - Healthy: Most recent run completed successfully (status='completed')
        - Failing: Most recent run failed (status='failed' or 'partial')

        Returns:
            Tuple of (feeds_healthy, feeds_failing)
        """
        # Subquery to get the most recent run for each feed
        latest_run_subquery = (
            self.db.query(
                FeedRun.feed_id,
                func.max(FeedRun.created_at).label("latest_created_at")
            )
            .group_by(FeedRun.feed_id)
            .subquery()
        )

        # Join to get the status of the most recent run for each feed
        latest_runs = (
            self.db.query(FeedRun.feed_id, FeedRun.status)
            .join(
                latest_run_subquery,
                and_(
                    FeedRun.feed_id == latest_run_subquery.c.feed_id,
                    FeedRun.created_at == latest_run_subquery.c.latest_created_at
                )
            )
            .all()
        )

        feeds_healthy = 0
        feeds_failing = 0

        for _, status in latest_runs:
            if status == "completed":
                feeds_healthy += 1
            elif status in ("failed", "partial"):
                feeds_failing += 1
            # Pending/running runs don't count toward either category

        return feeds_healthy, feeds_failing

    def _get_last_sync_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the most recent completed feed run.

        Returns:
            datetime of the most recent completed run, or None if no runs exist
        """
        last_run = (
            self.db.query(FeedRun.completed_at)
            .filter(
                FeedRun.status == "completed",
                FeedRun.completed_at.isnot(None)
            )
            .order_by(FeedRun.completed_at.desc())
            .first()
        )

        return last_run[0] if last_run else None

    def _get_daily_digest_counts(self, days: int = 7) -> list[int]:
        """Get digest counts per day for the last N days.

        Args:
            days: Number of days to look back (default 7)

        Returns:
            List of daily counts, oldest first (e.g., [5, 10, 8, 12, 3, 15, 7])
        """
        now = datetime.utcnow()
        counts = []

        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            count = self.db.query(func.count(Digest.id)).filter(
                Digest.created_at >= day_start,
                Digest.created_at < day_end
            ).scalar() or 0

            counts.append(count)

        return counts
