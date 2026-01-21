"""Pydantic schemas for agent-related API responses."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from reconly_api.schemas.edition import OSS_EXCLUDED_FIELDS
from reconly_core.edition import is_enterprise


class AgentRunResponse(BaseModel):
    """Response model for an agent run."""

    id: int
    source_id: int
    source_name: str | None = None
    prompt: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    iterations: int
    tool_calls: list[dict] | None = None
    sources_consulted: list[str] | None = None
    result_title: str | None = None
    result_content: str | None = None
    tokens_in: int
    tokens_out: int
    estimated_cost: float = 0.0  # Enterprise only - excluded from OSS responses
    error_log: str | None = None
    trace_id: str | None = None
    created_at: datetime
    duration_seconds: float | None = None

    # Research strategy fields (populated from extra_data JSON)
    research_strategy: str = "simple"  # simple, comprehensive, or deep
    subtopics: list[str] | None = None  # Generated subtopics (comprehensive/deep)
    research_plan: str | None = None  # Generated research plan
    report_format: str | None = None  # Citation format used (e.g., "apa", "ieee")
    source_count: int | None = None  # Number of sources consulted

    model_config = ConfigDict(from_attributes=True)

    def model_dump(self, **kwargs):
        """Customize serialization to exclude cost fields in OSS edition."""
        # If not enterprise, exclude cost fields
        if not is_enterprise():
            exclude = kwargs.get('exclude') or set()
            if isinstance(exclude, set):
                exclude = exclude | OSS_EXCLUDED_FIELDS
            else:
                exclude = set(exclude) | OSS_EXCLUDED_FIELDS
            kwargs['exclude'] = exclude

        return super().model_dump(**kwargs)


class AgentRunListResponse(BaseModel):
    """Response for agent run list with pagination."""

    items: list[AgentRunResponse]
    total: int


class StrategyInfoResponse(BaseModel):
    """Information about a research strategy."""

    available: bool
    description: str
    estimated_duration_seconds: int | None = None
    requires_api_key: bool = False


class AgentCapabilitiesResponse(BaseModel):
    """Response describing available agent research capabilities.

    Example response:
    ```json
    {
      "strategies": {
        "simple": {"available": true, "description": "Quick research (~30s)"},
        "comprehensive": {"available": true, "description": "Deep research (~3min)"},
        "deep": {"available": false, "description": "Exhaustive analysis (~5min)"}
      },
      "gpt_researcher_installed": true,
      "search_providers": ["duckduckgo", "searxng", "tavily"],
      "configured_search_provider": "duckduckgo"
    }
    ```
    """

    strategies: dict[str, StrategyInfoResponse]
    gpt_researcher_installed: bool
    search_providers: list[str]
    configured_search_provider: str | None = None
