"""Source management API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from reconly_core.database.models import Source
from reconly_api.dependencies import get_db
from reconly_api.schemas.sources import SourceCreate, SourceUpdate, SourceResponse
from reconly_api.schemas.batch import BatchDeleteRequest, BatchDeleteResponse

router = APIRouter()


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    type: Optional[str] = None,
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all sources with optional filtering."""
    query = db.query(Source)

    if type:
        query = query.filter(Source.type == type)
    if enabled_only:
        query = query.filter(Source.enabled == True)

    sources = query.order_by(Source.created_at.desc()).all()
    return [SourceResponse.model_validate(s) for s in sources]


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    source: SourceCreate,
    db: Session = Depends(get_db)
):
    """Create a new source."""
    db_source = Source(
        name=source.name,
        type=source.type,
        url=source.url,
        config=source.config,
        enabled=source.enabled if source.enabled is not None else True,
        # Content filtering fields
        include_keywords=source.include_keywords,
        exclude_keywords=source.exclude_keywords,
        filter_mode=source.filter_mode,
        use_regex=source.use_regex if source.use_regex is not None else False,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return SourceResponse.model_validate(db_source)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    """Update a source."""
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_source, key, value)

    db.commit()
    db.refresh(db_source)
    return SourceResponse.model_validate(db_source)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Delete a source."""
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()
    return None


@router.patch("/{source_id}", response_model=SourceResponse)
async def patch_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    """Partial update a source (e.g., toggle enabled status)."""
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_source, key, value)

    db.commit()
    db.refresh(db_source)
    return SourceResponse.model_validate(db_source)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_sources(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple sources by ID."""
    deleted_count = 0
    failed_ids = []

    for source_id in request.ids:
        source = db.query(Source).filter(Source.id == source_id).first()
        if source:
            db.delete(source)
            deleted_count += 1
        else:
            failed_ids.append(source_id)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )
