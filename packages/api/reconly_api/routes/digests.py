"""Digest API endpoints."""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import Response
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from reconly_core.exporters import get_exporter, list_exporters

from reconly_api.schemas.digest import (
    DigestCreate,
    DigestResponse,
    DigestList,
    DigestStats,
    BatchProcessRequest,
    BatchProcessResponse,
    DigestTagsUpdate,
)
from reconly_api.schemas.batch import BatchDeleteRequest, BatchDeleteResponse
from reconly_api.schemas.exporters import ExportByIdsRequest, ExportToPathRequest, ExportToPathResponse
from reconly_api.config import settings
from reconly_api.dependencies import get_db, limiter
from reconly_core.services.digest_service import DigestService, ProcessOptions
from reconly_core.services.batch_service import BatchService, BatchOptions

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=DigestResponse, status_code=201)
@limiter.limit("10/minute")  # Limit digest creation to 10 per minute
async def create_digest(
    request: Request,
    digest_request: DigestCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new digest from URL.

    - **url**: URL to fetch and summarize
    - **language**: Summary language (de/en)
    - **provider**: LLM provider (optional)
    - **model**: Model to use (optional)
    - **tags**: Tags for categorization
    - **save**: Whether to save to database
    """
    try:
        # Initialize service
        service = DigestService(database_url=settings.database_url)

        # Create process options (single-user OSS mode)
        options = ProcessOptions(
            language=digest_request.language,
            provider=digest_request.provider or settings.default_provider,
            model=digest_request.model or settings.default_model,
            save=digest_request.save,
            tags=digest_request.tags,
            user_id=None  # Single-user OSS mode
        )

        # Process URL
        result = service.process_url(digest_request.url, options)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        # For RSS feeds, return summary of processing
        if result.data and 'articles' in result.data:
            articles = result.data['articles']
            if not articles:
                raise HTTPException(status_code=404, detail="No articles found")

            # For RSS feeds, return metadata about processed articles
            # Users can then query individual digests via the list endpoint
            successful_articles = [a for a in articles if a.get('success', True)]

            return DigestResponse(
                url=digest_request.url,
                title=f"RSS Feed Processed: {len(successful_articles)} articles",
                summary=f"Successfully processed {len(successful_articles)} out of {len(articles)} articles from RSS feed.",
                source_type='rss',
                provider=digest_request.provider or settings.default_provider,
                language=digest_request.language,
                estimated_cost=sum(a.get('estimated_cost', 0) for a in successful_articles)
            )
        else:
            return DigestResponse(**result.data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=DigestList)
async def list_digests(
    feed_id: Optional[int] = Query(None, description="Filter by feed ID"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    search: Optional[str] = Query(None, description="Search in title, content, summary"),
    limit: int = Query(10, ge=1, le=100, description="Result limit"),
    db: Session = Depends(get_db)
):
    """
    List recent digests.

    - **feed_id**: Filter by feed ID
    - **source_id**: Filter by source ID
    - **tags**: Filter by comma-separated tags
    - **source_type**: Filter by source type (website/youtube/rss)
    - **search**: Search query (uses PostgreSQL full-text search)
    - **limit**: Maximum results (1-100)
    """
    try:
        from reconly_core.database.models import Digest, DigestTag, Tag, FeedRun

        # Build base query with eager loading
        query = db.query(Digest).options(joinedload(Digest.llm_usage_logs))

        if feed_id:
            # Filter by feed through feed_run
            query = query.join(FeedRun).filter(FeedRun.feed_id == feed_id)

        if source_id:
            query = query.filter(Digest.source_id == source_id)

        if source_type:
            query = query.filter(Digest.source_type == source_type)

        if tags:
            # Filter by tag through DigestTag
            tag_list = [t.strip() for t in tags.split(',')]
            query = query.join(DigestTag).join(Tag).filter(Tag.name.in_(tag_list))

        if search:
            # Use PostgreSQL full-text search with prefix matching for search-as-you-type
            # Split into words, add :* to last word for prefix matching
            words = search.strip().split()
            if words:
                # Escape special characters and build tsquery with prefix on last word
                safe_words = [w.replace("'", "''").replace('\\', '\\\\') for w in words if w]
                if len(safe_words) == 1:
                    tsquery_str = f"{safe_words[0]}:*"
                else:
                    # Join all but last with &, add :* to last word
                    tsquery_str = " & ".join(safe_words[:-1]) + f" & {safe_words[-1]}:*"

                fts_condition = text("""
                    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, ''))
                    @@ to_tsquery('english', :search_query)
                """)
                query = query.filter(fts_condition).params(search_query=tsquery_str)

        # Get total count before applying limit
        total_count = query.count()

        # Order by created_at descending and limit
        query = query.order_by(Digest.created_at.desc()).limit(limit)

        # Execute query
        digests_data = query.all()

        # Convert to response format
        digests = []
        for digest in digests_data:
            digest_dict = digest.to_dict()
            digests.append(DigestResponse(**digest_dict))

        return DigestList(total=total_count, digests=digests)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=DigestList)
async def search_digests(
    query: str = Query(..., description="Search query"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    limit: int = Query(10, ge=1, le=100, description="Result limit"),
    db: Session = Depends(get_db)
):
    """
    Search digests by full-text query.

    - **query**: Search query (searches title, content, summary)
    - **tags**: Filter by comma-separated tags
    - **source_type**: Filter by source type
    - **limit**: Maximum results
    """
    try:
        service = DigestService(database_url=settings.database_url)

        # Parse tags
        tag_list = [t.strip() for t in tags.split(',')] if tags else None

        # Search digests (single-user OSS mode)
        results = service.search_digests(
            query=query,
            tags=tag_list,
            source_type=source_type,
            limit=limit,
            user_id=None  # Single-user OSS mode
        )

        # Convert to response format
        digests = []
        for digest in results:
            digest_dict = digest.to_dict()
            digests.append(DigestResponse(**digest_dict))

        return DigestList(total=len(digests), digests=digests)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=DigestStats)
async def get_statistics(
    db: Session = Depends(get_db)
):
    """
    Get database statistics.

    Returns:
    - Total digests count
    - Total cost
    - Total tags
    - Distribution by source type
    """
    try:
        service = DigestService(database_url=settings.database_url)
        stats = service.get_statistics(user_id=None)  # Single-user OSS mode
        return DigestStats(**stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchProcessResponse)
@limiter.limit("5/hour")  # Limit batch processing to 5 per hour
async def batch_process(
    request: Request,
    batch_request: BatchProcessRequest,
    db: Session = Depends(get_db)
):
    """
    Process multiple sources from configuration.

    - **config_path**: Path to config file (optional)
    - **tags**: Filter sources by tags
    - **source_type**: Filter by source type
    - **save**: Save digests to database
    """
    try:
        # Initialize batch service
        batch_service = BatchService()

        # Create batch options (single-user OSS mode)
        options = BatchOptions(
            config_path=batch_request.config_path,
            tags=batch_request.tags,
            source_type=batch_request.source_type,
            save=batch_request.save,
            database_url=settings.database_url,
            show_progress=False,  # Disable progress for API
            user_id=None  # Single-user OSS mode
        )

        # Process batch
        result = batch_service.process_batch(options)

        return BatchProcessResponse(
            total_sources=result.total_sources,
            total_processed=result.total_processed,
            total_errors=result.total_errors,
            success_rate=result.success_rate,
            source_results=result.source_results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export", response_model=None)
async def export_digests(
    format: str = Query("json", description="Export format: json, csv, obsidian"),
    feed_id: Optional[int] = Query(None, description="Filter by feed ID"),
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search query"),
    db: Session = Depends(get_db)
):
    """
    Export digests in various formats.

    - **format**: Export format (json, csv, obsidian)
    - **feed_id**: Filter by feed ID
    - **source_id**: Filter by source ID
    - **tag**: Filter by tag
    - **search**: Search query
    """
    try:
        from reconly_core.database.models import Digest

        # Build query (single-user OSS mode - no user filtering)
        query = db.query(Digest)

        if feed_id:
            # Filter by feed through feed_run
            from reconly_core.database.models import FeedRun
            query = query.join(FeedRun).filter(FeedRun.feed_id == feed_id)

        if source_id:
            query = query.filter(Digest.source_id == source_id)

        if tag:
            # Filter by tag through DigestTag
            from reconly_core.database.models import DigestTag, Tag
            query = query.join(DigestTag).join(Tag).filter(Tag.name == tag)

        if search:
            # Search in title, content, and summary
            search_pattern = f"%{search}%"
            query = query.filter(
                (Digest.title.ilike(search_pattern)) |
                (Digest.content.ilike(search_pattern)) |
                (Digest.summary.ilike(search_pattern))
            )

        # Execute query
        digests = query.all()

        # Use exporter factory for format-specific export
        try:
            exporter = get_exporter(format)
        except ValueError:
            available = list_exporters()
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {format}. Available formats: {available}"
            )

        result = exporter.export(digests)

        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={result.filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export", response_model=None)
async def export_digests_by_ids(
    request: ExportByIdsRequest,
    db: Session = Depends(get_db)
):
    """
    Export specific digests by ID in various formats.

    - **ids**: List of digest IDs to export
    - **format**: Export format (json, csv, obsidian)
    """
    try:
        from reconly_core.database.models import Digest

        # Fetch digests by IDs
        digests = db.query(Digest).filter(Digest.id.in_(request.ids)).all()

        if not digests:
            raise HTTPException(status_code=404, detail="No digests found with provided IDs")

        # Use exporter factory for format-specific export
        try:
            exporter = get_exporter(request.format)
        except ValueError:
            available = list_exporters()
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {request.format}. Available formats: {available}"
            )

        result = exporter.export(digests)

        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={result.filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-to-path", response_model=ExportToPathResponse)
async def export_digests_to_path(
    request: ExportToPathRequest,
    db: Session = Depends(get_db)
):
    """
    Export digests directly to filesystem (e.g., Obsidian vault).

    - **format**: Export format (must support direct export, e.g., 'obsidian')
    - **path**: Custom target path (uses configured path if omitted)
    - **digest_ids**: Specific digest IDs to export (overrides filters)
    - **feed_id**: Filter by feed ID
    - **source_id**: Filter by source ID
    - **tag**: Filter by tag
    - **search**: Search query
    """
    import os
    from pathlib import Path

    try:
        from reconly_core.database.models import Digest

        # Get exporter
        try:
            exporter = get_exporter(request.format)
        except ValueError:
            available = list_exporters()
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {request.format}. Available: {available}"
            )

        # Check if exporter supports direct export
        schema = exporter.get_config_schema()
        if not schema.supports_direct_export:
            raise HTTPException(
                status_code=400,
                detail=f"Format '{request.format}' does not support direct file export"
            )

        # Determine target path
        target_path = request.path
        if not target_path:
            # Try to get from settings - different exporters use different key names
            from reconly_core.services.settings_service import SettingsService
            settings_service = SettingsService(db)

            # Obsidian uses vault_path, others use export_path
            if request.format == "obsidian":
                target_path = settings_service.get(f"export.{request.format}.vault_path")
            else:
                target_path = settings_service.get(f"export.{request.format}.export_path")

        if not target_path:
            path_setting = "vault_path" if request.format == "obsidian" else "export_path"
            raise HTTPException(
                status_code=400,
                detail=f"No target path provided and no default path configured. "
                       f"Set path in request or configure export.{request.format}.{path_setting} in settings."
            )

        # Validate path
        path_obj = Path(target_path)
        if not path_obj.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Target path does not exist: {target_path}"
            )
        if not path_obj.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Target path is not a directory: {target_path}"
            )
        if not os.access(target_path, os.W_OK):
            raise HTTPException(
                status_code=400,
                detail=f"Target path is not writable: {target_path}"
            )

        # Build digest query
        query = db.query(Digest)

        # If specific digest IDs provided, use those (overrides filters)
        if request.digest_ids:
            query = query.filter(Digest.id.in_(request.digest_ids))
        else:
            # Apply filters
            if request.feed_id:
                from reconly_core.database.models import FeedRun
                query = query.join(FeedRun).filter(FeedRun.feed_id == request.feed_id)

            if request.source_id:
                query = query.filter(Digest.source_id == request.source_id)

            if request.tag:
                from reconly_core.database.models import DigestTag, Tag
                query = query.join(DigestTag).join(Tag).filter(Tag.name == request.tag)

            if request.search:
                search_pattern = f"%{request.search}%"
                query = query.filter(
                    (Digest.title.ilike(search_pattern)) |
                    (Digest.content.ilike(search_pattern)) |
                    (Digest.summary.ilike(search_pattern))
                )

        digests = query.all()

        if not digests:
            return ExportToPathResponse(
                success=True,
                files_written=0,
                target_path=target_path,
                filenames=[],
                errors=[]
            )

        # Get exporter config from settings based on the config schema
        from reconly_core.services.settings_service import SettingsService
        settings_service = SettingsService(db)

        # Build config dict from exporter's config schema fields
        exporter_config = {}
        config_schema = exporter.get_config_schema()
        for field in config_schema.fields:
            # Skip the path field - we already have the target path
            if field.key in ("vault_path", "export_path"):
                continue
            try:
                value = settings_service.get(f"export.{request.format}.{field.key}")
                exporter_config[field.key] = value
            except KeyError:
                # Setting not in registry, use field default
                exporter_config[field.key] = field.default

        # Export to path
        result = exporter.export_to_path(digests, target_path, exporter_config)

        return ExportToPathResponse(
            success=result.success,
            files_written=result.files_written,
            target_path=result.target_path,
            filenames=result.filenames,
            errors=result.errors
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{digest_id}", response_model=DigestResponse)
async def get_digest(
    digest_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific digest by ID.

    - **digest_id**: Digest ID
    """
    try:
        from reconly_core.database.models import Digest

        # Get digest with eager loading of llm_usage_logs for token counts
        digest = db.query(Digest).options(
            joinedload(Digest.llm_usage_logs)
        ).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(
                status_code=404,
                detail=f"Digest with ID {digest_id} not found"
            )

        digest_dict = digest.to_dict()
        return DigestResponse(**digest_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{digest_id}/tags", response_model=DigestResponse)
async def update_digest_tags(
    digest_id: int,
    request: DigestTagsUpdate,
    db: Session = Depends(get_db)
):
    """
    Update tags for a specific digest.

    - **digest_id**: Digest ID
    - **tags**: List of tag names to set (replaces existing tags)
    """
    from reconly_core.database.models import Digest, Tag, DigestTag

    # Get digest
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(
            status_code=404,
            detail=f"Digest with ID {digest_id} not found"
        )

    # Remove existing tags
    db.query(DigestTag).filter(DigestTag.digest_id == digest_id).delete()

    # Add new tags
    for tag_name in request.tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue

        # Get or create tag
        tag = db.query(Tag).filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
            db.flush()

        # Create digest-tag link
        digest_tag = DigestTag(digest_id=digest_id, tag_id=tag.id)
        db.add(digest_tag)

    db.commit()

    # Expire the digest to clear relationship cache, then re-query with fresh data
    db.expire(digest)
    # Re-query to get fresh data with relationships loaded
    # Need to load DigestTag -> Tag for to_dict() which accesses tag.tag.name
    digest = db.query(Digest).options(
        joinedload(Digest.tags).joinedload(DigestTag.tag)
    ).filter(Digest.id == digest_id).first()

    return DigestResponse(**digest.to_dict())


@router.delete("/{digest_id}", status_code=204)
async def delete_digest(
    digest_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific digest by ID.

    - **digest_id**: Digest ID
    """
    from reconly_core.database.models import Digest

    # Get digest directly from injected session
    digest = db.query(Digest).filter(Digest.id == digest_id).first()

    if not digest:
        raise HTTPException(
            status_code=404,
            detail=f"Digest with ID {digest_id} not found"
        )

    db.delete(digest)
    db.commit()
    return None


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_digests(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """
    Delete multiple digests by ID.

    - **ids**: List of digest IDs to delete
    """
    from reconly_core.database.models import Digest

    deleted_count = 0
    failed_ids = []

    for digest_id in request.ids:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if digest:
            db.delete(digest)
            deleted_count += 1
        else:
            failed_ids.append(digest_id)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )
