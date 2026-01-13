"""Pydantic schemas for feed bundle API endpoints."""
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# EXPORT SCHEMAS
# ============================================================================

class BundleExportRequest(BaseModel):
    """Request schema for exporting a feed as a bundle."""
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")
    category: Optional[Literal["news", "finance", "tech", "science", "entertainment", "sports", "business", "other"]] = None
    tags: Optional[list[str]] = Field(default=None, max_length=10)
    min_reconly_version: Optional[str] = Field(default=None, pattern=r"^\d+\.\d+\.\d+$")
    required_features: Optional[list[str]] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None


class BundleExportResponse(BaseModel):
    """Response schema for bundle export."""
    success: bool
    bundle: dict  # The full bundle JSON
    filename: str  # Suggested filename


# ============================================================================
# VALIDATE SCHEMAS
# ============================================================================

class BundleValidateRequest(BaseModel):
    """Request schema for validating a bundle."""
    bundle: dict  # Raw bundle JSON to validate


class BundleValidateResponse(BaseModel):
    """Response schema for bundle validation."""
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ============================================================================
# PREVIEW SCHEMAS
# ============================================================================

class SourcePreview(BaseModel):
    """Preview of a source to be created/reused."""
    name: str
    url: str
    type: Optional[str] = None
    existing_id: Optional[int] = None


class FeedPreview(BaseModel):
    """Preview of the feed to be created."""
    name: str
    id: str  # slug
    version: str
    description: Optional[str] = None
    already_exists: bool


class TemplatePreview(BaseModel):
    """Preview of a template to be created."""
    included: bool
    name: Optional[str] = None


class SchedulePreview(BaseModel):
    """Preview of schedule configuration."""
    included: bool
    cron: Optional[str] = None


class SourcesPreview(BaseModel):
    """Preview of sources to be created/reused."""
    total: int
    new: list[SourcePreview]
    existing: list[SourcePreview]


class BundlePreviewRequest(BaseModel):
    """Request schema for previewing bundle import."""
    bundle: dict  # Raw bundle JSON to preview


class BundlePreviewResponse(BaseModel):
    """Response schema for bundle import preview."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    feed: Optional[FeedPreview] = None
    sources: Optional[SourcesPreview] = None
    prompt_template: Optional[TemplatePreview] = None
    report_template: Optional[TemplatePreview] = None
    schedule: Optional[SchedulePreview] = None


# ============================================================================
# IMPORT SCHEMAS
# ============================================================================

class BundleImportRequest(BaseModel):
    """Request schema for importing a bundle."""
    bundle: dict  # Raw bundle JSON to import
    skip_duplicate_sources: bool = Field(
        default=True,
        description="If True, reuse existing sources with the same URL"
    )


class BundleImportResponse(BaseModel):
    """Response schema for bundle import."""
    success: bool
    feed_id: Optional[int] = None
    feed_name: Optional[str] = None
    sources_created: int = 0
    prompt_template_id: Optional[int] = None
    report_template_id: Optional[int] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
