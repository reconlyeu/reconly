"""Digest-related schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class DigestCreate(BaseModel):
    """Schema for creating a new digest."""
    url: str = Field(..., description="URL to fetch and summarize")
    language: str = Field(default="de", description="Summary language (de/en)")
    provider: Optional[str] = Field(default=None, description="LLM provider (huggingface/anthropic)")
    model: Optional[str] = Field(default=None, description="Model to use")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")
    save: bool = Field(default=True, description="Save to database")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "url": "https://example.com/article",
            "language": "de",
            "provider": "anthropic",
            "tags": ["tech", "ai"],
            "save": True
        }
    })


class DigestSourceItemResponse(BaseModel):
    """Schema for digest source item (provenance tracking)."""
    id: int
    digest_id: int
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    item_url: str
    item_title: Optional[str] = None
    item_published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DigestResponse(BaseModel):
    """Schema for digest response."""
    id: Optional[int] = None
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    source_type: Optional[str] = None
    feed_url: Optional[str] = None
    feed_title: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    provider: Optional[str] = None
    language: Optional[str] = None
    estimated_cost: Optional[float] = None  # Enterprise only - excluded from OSS responses
    consolidated_count: int = Field(default=1, description="Number of items consolidated (1 for individual digests)")
    source_items: Optional[List[DigestSourceItemResponse]] = Field(
        default=None,
        description="Source items for consolidated digests (provenance tracking)"
    )
    tags: List[str] = []
    # Token usage from LLMUsageLog
    tokens_in: int = Field(default=0, description="Input tokens used for this digest")
    tokens_out: int = Field(default=0, description="Output tokens used for this digest")

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


class DigestList(BaseModel):
    """Schema for list of digests."""
    total: int
    digests: List[DigestResponse]


class DigestSearch(BaseModel):
    """Schema for digest search."""
    query: Optional[str] = Field(default=None, description="Search query")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    source_type: Optional[str] = Field(default=None, description="Filter by source type")
    limit: int = Field(default=10, ge=1, le=100, description="Result limit")


class DigestStats(BaseModel):
    """Schema for database statistics."""
    total_digests: int
    total_cost: float = 0.0  # Enterprise only - excluded from OSS responses
    total_tags: int
    by_source_type: dict

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


class BatchProcessRequest(BaseModel):
    """Schema for batch processing request."""
    config_path: Optional[str] = Field(default=None, description="Path to config file")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    source_type: Optional[str] = Field(default=None, description="Filter by source type")
    save: bool = Field(default=True, description="Save digests to database")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tags": ["tech", "news"],
            "save": True
        }
    })


class BatchProcessResponse(BaseModel):
    """Schema for batch processing response."""
    total_sources: int
    total_processed: int
    total_errors: int
    success_rate: float
    source_results: List[dict]


class DigestTagsUpdate(BaseModel):
    """Schema for updating digest tags."""
    tags: List[str] = Field(default=[], description="List of tag names to set")
