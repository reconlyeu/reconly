"""Feed bundle API routes for marketplace export/import."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload

from reconly_core.database.models import Feed, FeedSource
from reconly_core.marketplace import (
    FeedBundleExporter,
    FeedBundleImporter,
    BundleValidator,
)
from reconly_api.dependencies import get_db
from reconly_api.config import settings
from reconly_api.schemas.bundles import (
    BundleExportRequest,
    BundleExportResponse,
    BundleValidateRequest,
    BundleValidateResponse,
    BundlePreviewRequest,
    BundlePreviewResponse,
    BundleImportRequest,
    BundleImportResponse,
    FeedPreview,
    SourcesPreview,
    SourcePreview,
    TemplatePreview,
    SchedulePreview,
)

router = APIRouter()


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@router.post("/feeds/{feed_id}/export", response_model=BundleExportResponse)
async def export_feed_bundle(
    feed_id: int,
    request: BundleExportRequest,
    db: Session = Depends(get_db),
):
    """Export a feed as a portable JSON bundle.

    Creates a bundle containing the feed's sources, templates, and configuration
    that can be shared and imported elsewhere.
    """
    # Load feed with all relationships
    feed = db.query(Feed).options(
        joinedload(Feed.feed_sources).joinedload(FeedSource.source),
        joinedload(Feed.prompt_template),
        joinedload(Feed.report_template),
    ).filter(Feed.id == feed_id).first()

    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    if not feed.feed_sources:
        raise HTTPException(
            status_code=400,
            detail="Feed has no sources. Add at least one source before exporting."
        )

    # Create exporter with author info from settings
    exporter = FeedBundleExporter(
        author_name=settings.author_name,
        author_github=settings.author_github,
        author_email=settings.author_email,
    )

    # Export bundle
    bundle_dict = exporter.export_feed_to_dict(
        feed,
        version=request.version,
        category=request.category,
        tags=request.tags,
        min_reconly_version=request.min_reconly_version,
        required_features=request.required_features,
        license_name=request.license,
        homepage=request.homepage,
        repository=request.repository,
    )

    # Generate filename
    bundle_id = bundle_dict["bundle"]["id"]
    version = bundle_dict["bundle"]["version"]
    filename = f"{bundle_id}-{version}.json"

    return BundleExportResponse(
        success=True,
        bundle=bundle_dict,
        filename=filename,
    )


# ============================================================================
# VALIDATE ENDPOINTS
# ============================================================================

@router.post("/bundles/validate", response_model=BundleValidateResponse)
async def validate_bundle(
    request: BundleValidateRequest,
):
    """Validate a bundle without importing it.

    Checks schema compliance, required fields, and format correctness.
    """
    validator = BundleValidator()
    result = validator.validate(request.bundle)

    return BundleValidateResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
    )


# ============================================================================
# PREVIEW ENDPOINTS
# ============================================================================

@router.post("/bundles/preview", response_model=BundlePreviewResponse)
async def preview_bundle_import(
    request: BundlePreviewRequest,
    db: Session = Depends(get_db),
):
    """Preview what would be created by importing a bundle.

    Shows which entities would be created, which already exist,
    and any potential conflicts.
    """
    importer = FeedBundleImporter(db)
    preview = importer.preview_import(request.bundle)

    if not preview.get("valid"):
        return BundlePreviewResponse(
            valid=False,
            errors=preview.get("errors", []),
            warnings=preview.get("warnings", []),
        )

    # Convert raw preview to typed response
    feed_data = preview.get("feed", {})
    sources_data = preview.get("sources", {})

    return BundlePreviewResponse(
        valid=True,
        errors=preview.get("errors", []),
        warnings=preview.get("warnings", []),
        feed=FeedPreview(
            name=feed_data.get("name", ""),
            id=feed_data.get("id", ""),
            version=feed_data.get("version", ""),
            description=feed_data.get("description"),
            already_exists=feed_data.get("already_exists", False),
        ),
        sources=SourcesPreview(
            total=sources_data.get("total", 0),
            new=[SourcePreview(**s) for s in sources_data.get("new", [])],
            existing=[SourcePreview(**s) for s in sources_data.get("existing", [])],
        ),
        prompt_template=TemplatePreview(
            included=preview.get("prompt_template", {}).get("included", False),
            name=preview.get("prompt_template", {}).get("name"),
        ),
        report_template=TemplatePreview(
            included=preview.get("report_template", {}).get("included", False),
            name=preview.get("report_template", {}).get("name"),
        ),
        schedule=SchedulePreview(
            included=preview.get("schedule", {}).get("included", False),
            cron=preview.get("schedule", {}).get("cron"),
        ),
    )


# ============================================================================
# IMPORT ENDPOINTS
# ============================================================================

@router.post("/bundles/import", response_model=BundleImportResponse, status_code=201)
async def import_bundle(
    request: BundleImportRequest,
    db: Session = Depends(get_db),
):
    """Import a bundle to create a new feed with sources and templates.

    Creates all necessary entities (feed, sources, templates) from the bundle.
    Optionally reuses existing sources with the same URL.
    """
    importer = FeedBundleImporter(db)
    result = importer.import_bundle(
        request.bundle,
        user_id=None,  # OSS mode - no user association
        validate_first=True,
        skip_duplicate_sources=request.skip_duplicate_sources,
    )

    if not result.success:
        # Return 400 for validation/business errors
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Bundle import failed",
                "errors": result.errors,
                "warnings": result.warnings,
            }
        )

    return BundleImportResponse(
        success=True,
        feed_id=result.feed_id,
        feed_name=result.feed_name,
        sources_created=result.sources_created,
        prompt_template_id=result.prompt_template_id,
        report_template_id=result.report_template_id,
        errors=result.errors,
        warnings=result.warnings,
    )


# ============================================================================
# SCHEMA ENDPOINT
# ============================================================================

@router.get("/bundles/schema")
async def get_bundle_schema():
    """Get the JSON schema for feed bundles.

    Returns the schema definition for v1.0 bundles, useful for
    validation and documentation.
    """
    from reconly_core.marketplace import BUNDLE_SCHEMA_V1
    return BUNDLE_SCHEMA_V1
