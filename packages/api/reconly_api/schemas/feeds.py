"""Feed schemas for API."""
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from datetime import datetime


# Valid digest modes
DigestMode = Literal['individual', 'per_source', 'all_sources']


class ExporterConfig(BaseModel):
    """Configuration for a single exporter in per-feed auto-export.

    Attributes:
        enabled: Whether this exporter should run after feed completion
        path: Optional path override (uses global settings if not specified)
    """
    enabled: bool = False
    path: Optional[str] = None


class ExportConfig(BaseModel):
    """Configuration for per-feed auto-export settings.

    Maps exporter names to their configuration.
    Example: {"obsidian": {"enabled": true, "path": "/custom/vault"}}
    """
    # Use extra='allow' to accept any exporter name as key
    model_config = ConfigDict(extra='allow')

    @field_validator('*', mode='before')
    @classmethod
    def validate_exporter_config(cls, v):
        """Ensure each exporter config has the expected structure."""
        if isinstance(v, dict):
            return ExporterConfig(**v)
        return v


class FeedBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    digest_mode: DigestMode = Field(
        default='individual',
        description="Digest consolidation mode: 'individual' (one per item), 'per_source' (one per source), 'all_sources' (single briefing)"
    )
    schedule_cron: Optional[str] = None
    schedule_enabled: bool = True
    prompt_template_id: Optional[int] = None
    report_template_id: Optional[int] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    output_config: Optional[Dict[str, Any]] = None


class FeedCreate(FeedBase):
    source_ids: Optional[List[int]] = []


class FeedUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    digest_mode: Optional[DigestMode] = None
    schedule_cron: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    prompt_template_id: Optional[int] = None
    report_template_id: Optional[int] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    output_config: Optional[Dict[str, Any]] = None
    source_ids: Optional[List[int]] = None


class FeedSourceResponse(BaseModel):
    feed_id: int
    source_id: int
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    enabled: bool
    priority: int

    @model_validator(mode='before')
    @classmethod
    def extract_source_info(cls, data):
        """Extract source name and type from nested source relationship."""
        if hasattr(data, 'source') and data.source:
            return {
                'feed_id': data.feed_id,
                'source_id': data.source_id,
                'source_name': data.source.name,
                'source_type': data.source.type,
                'enabled': data.enabled,
                'priority': data.priority,
            }
        return data

    model_config = ConfigDict(from_attributes=True)


class FeedResponse(FeedBase):
    id: int
    user_id: Optional[int] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    feed_sources: List[FeedSourceResponse] = Field(default=[])

    model_config = ConfigDict(from_attributes=True)


class SourceError(BaseModel):
    """Error information for a specific source."""
    source_id: int
    source_name: Optional[str] = None
    error_type: str  # FetchError, ParseError, SummarizeError, SaveError
    message: str
    timestamp: datetime


class ErrorDetails(BaseModel):
    """Structured error details for a feed run."""
    errors: List[SourceError] = []
    summary: Optional[str] = None


class FeedRunResponse(BaseModel):
    id: int
    feed_id: int
    feed_name: Optional[str] = None  # Included via join with Feed table
    triggered_by: str
    triggered_by_user_id: Optional[int] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sources_total: int
    sources_processed: int
    sources_failed: int
    items_processed: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float = 0.0  # Enterprise only - excluded from OSS responses
    error_log: Optional[str] = None
    error_details: Optional[ErrorDetails] = None  # Structured error information
    trace_id: Optional[str] = None  # UUID for log correlation
    llm_provider: Optional[str] = None  # LLM provider used (anthropic, openai, etc.)
    llm_model: Optional[str] = None  # LLM model used (claude-3-5-sonnet, gpt-4, etc.)
    created_at: datetime
    duration_seconds: Optional[float] = None  # Calculated duration

    model_config = ConfigDict(from_attributes=True)

    def model_dump(self, **kwargs):
        """Customize serialization to exclude cost fields in OSS edition."""
        from reconly_core.edition import is_enterprise
        from reconly_api.schemas.edition import OSS_EXCLUDED_FIELDS

        # If not enterprise, exclude cost fields
        if not is_enterprise():
            exclude = kwargs.get('exclude') or set()
            if isinstance(exclude, set):
                exclude = exclude | OSS_EXCLUDED_FIELDS
            else:
                exclude = set(exclude) | OSS_EXCLUDED_FIELDS
            kwargs['exclude'] = exclude

        return super().model_dump(**kwargs)


class FeedRunDetailResponse(FeedRunResponse):
    """Extended feed run response with additional details."""
    digests_count: int = 0
    duration_seconds: Optional[float] = None
