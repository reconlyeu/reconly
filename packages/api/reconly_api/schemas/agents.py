"""Pydantic schemas for agent-related API responses."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from reconly_core.edition import is_enterprise
from reconly_api.schemas.edition import OSS_EXCLUDED_FIELDS


class AgentRunResponse(BaseModel):
    """Response model for an agent run."""
    id: int
    source_id: int
    source_name: Optional[str] = None
    prompt: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    iterations: int
    tool_calls: Optional[List[dict]] = None
    sources_consulted: Optional[List[str]] = None
    result_title: Optional[str] = None
    result_content: Optional[str] = None
    tokens_in: int
    tokens_out: int
    estimated_cost: float = 0.0  # Enterprise only - excluded from OSS responses
    error_log: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime
    duration_seconds: Optional[float] = None

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
    items: List[AgentRunResponse]
    total: int
