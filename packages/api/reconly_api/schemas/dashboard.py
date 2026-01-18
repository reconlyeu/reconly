"""Dashboard API schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class DashboardInsights(BaseModel):
    """Response schema for dashboard insights endpoint.

    Provides actionable, user-valuable metrics for the dashboard.
    """

    new_today: int = Field(
        ...,
        description="Count of digests created in the last 24 hours",
        ge=0
    )
    new_this_week: int = Field(
        ...,
        description="Count of digests created in the last 7 days",
        ge=0
    )
    total_digests: int = Field(
        ...,
        description="Total number of digests",
        ge=0
    )
    feeds_healthy: int = Field(
        ...,
        description="Count of feeds with no recent errors (last run was successful)",
        ge=0
    )
    feeds_failing: int = Field(
        ...,
        description="Count of feeds with recent errors (last run failed)",
        ge=0
    )
    last_sync_at: Optional[str] = Field(
        None,
        description="ISO timestamp of the most recent completed feed run, or null if none"
    )
    daily_counts: list[int] = Field(
        ...,
        description="Digest counts per day for last 7 days (oldest first), for sparkline"
    )
    change_today: int = Field(
        ...,
        description="Change in today's count compared to yesterday (can be negative)"
    )
    change_week: int = Field(
        ...,
        description="Change in this week's count compared to last week (can be negative)"
    )
