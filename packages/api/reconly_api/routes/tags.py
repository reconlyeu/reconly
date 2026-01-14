"""Tag API endpoints."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from reconly_api.dependencies import get_db
from reconly_api.schemas.tag import (
    TagResponse,
    TagListResponse,
    TagSuggestion,
    TagSuggestionsResponse,
    TagDeleteResponse,
    TagBulkDeleteResponse,
)
from reconly_core.database.models import Tag, DigestTag

router = APIRouter()


@router.get("", response_model=TagListResponse)
async def list_tags(
    db: Session = Depends(get_db),
):
    """
    List all tags with their digest counts.

    Returns tags sorted by digest count (most used first).
    """
    # Query tags with digest counts using a subquery
    digest_count_subq = (
        db.query(DigestTag.tag_id, func.count(DigestTag.digest_id).label("count"))
        .group_by(DigestTag.tag_id)
        .subquery()
    )

    results = (
        db.query(Tag, func.coalesce(digest_count_subq.c.count, 0).label("digest_count"))
        .outerjoin(digest_count_subq, Tag.id == digest_count_subq.c.tag_id)
        .order_by(func.coalesce(digest_count_subq.c.count, 0).desc(), Tag.name)
        .all()
    )

    tags = [
        TagResponse(
            id=tag.id,
            name=tag.name,
            digest_count=digest_count,
        )
        for tag, digest_count in results
    ]

    return TagListResponse(tags=tags, total=len(tags))


@router.get("/suggestions", response_model=TagSuggestionsResponse)
async def get_tag_suggestions(
    q: str = Query("", description="Query string for autocomplete"),
    limit: int = Query(10, ge=1, le=50, description="Maximum suggestions to return"),
    db: Session = Depends(get_db),
):
    """
    Get tag suggestions for autocomplete.

    - **q**: Query string to match against tag names (case-insensitive prefix match)
    - **limit**: Maximum number of suggestions to return

    Returns tags sorted by digest count (most relevant first).
    """
    # Query tags matching the prefix with digest counts
    digest_count_subq = (
        db.query(DigestTag.tag_id, func.count(DigestTag.digest_id).label("count"))
        .group_by(DigestTag.tag_id)
        .subquery()
    )

    query = (
        db.query(Tag, func.coalesce(digest_count_subq.c.count, 0).label("digest_count"))
        .outerjoin(digest_count_subq, Tag.id == digest_count_subq.c.tag_id)
    )

    # Apply prefix filter if query is provided
    if q:
        query = query.filter(Tag.name.ilike(f"{q}%"))

    results = (
        query.order_by(
            func.coalesce(digest_count_subq.c.count, 0).desc(),
            Tag.name,
        )
        .limit(limit)
        .all()
    )

    suggestions = [
        TagSuggestion(
            name=tag.name,
            digest_count=digest_count,
        )
        for tag, digest_count in results
    ]

    return TagSuggestionsResponse(suggestions=suggestions)


@router.delete("/unused", response_model=TagBulkDeleteResponse)
async def delete_unused_tags(
    db: Session = Depends(get_db),
):
    """
    Delete all tags that are not associated with any digests.

    Returns the count and names of deleted tags.
    """
    # Find tags with no digest associations
    used_tag_ids = db.query(DigestTag.tag_id).distinct().scalar_subquery()
    unused_tags = db.query(Tag).filter(~Tag.id.in_(used_tag_ids)).all()

    deleted_names = [tag.name for tag in unused_tags]
    deleted_count = len(unused_tags)

    # Delete the unused tags
    for tag in unused_tags:
        db.delete(tag)

    db.commit()

    return TagBulkDeleteResponse(
        deleted_count=deleted_count,
        tag_names=deleted_names,
    )


@router.delete("/{tag_id}", response_model=TagDeleteResponse)
async def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a specific tag by ID.

    This will also remove the tag from all associated digests.
    Returns the number of digests that were affected.
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    tag_name = tag.name

    # Count affected digests before deletion
    digests_affected = db.query(DigestTag).filter(DigestTag.tag_id == tag_id).count()

    # Delete the tag (cascade will remove DigestTag associations)
    db.delete(tag)
    db.commit()

    return TagDeleteResponse(
        deleted=True,
        tag_name=tag_name,
        digests_affected=digests_affected,
    )
