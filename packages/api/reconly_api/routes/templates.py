"""Template management API routes."""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from reconly_core.database.models import PromptTemplate, ReportTemplate
from reconly_api.dependencies import get_db
from reconly_api.schemas.templates import (
    PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateResponse,
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse
)
from reconly_api.schemas.batch import BatchDeleteRequest, BatchDeleteResponse

router = APIRouter()


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

@router.get("/prompt", response_model=List[PromptTemplateResponse])
async def list_prompt_templates(
    system_only: bool = False,
    user_only: bool = False,
    active_only: bool = False,
    origin: str = None,
    db: Session = Depends(get_db)
):
    """List all prompt templates.

    Args:
        system_only: Filter to builtin templates only (deprecated, use origin=builtin)
        user_only: Filter to user-created templates only (deprecated, use origin=user)
        active_only: Filter to active templates only
        origin: Filter by origin type (builtin, user, imported)
    """
    query = db.query(PromptTemplate)

    # New origin filter takes precedence
    if origin:
        query = query.filter(PromptTemplate.origin == origin)
    elif system_only:
        query = query.filter(PromptTemplate.origin == 'builtin')
    elif user_only:
        query = query.filter(PromptTemplate.origin == 'user')

    if active_only:
        query = query.filter(PromptTemplate.is_active == True)

    templates = query.order_by(PromptTemplate.created_at.desc()).all()
    return [PromptTemplateResponse.model_validate(t) for t in templates]


@router.post("/prompt", response_model=PromptTemplateResponse, status_code=201)
async def create_prompt_template(
    template: PromptTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new prompt template."""
    db_template = PromptTemplate(
        name=template.name,
        description=template.description,
        system_prompt=template.system_prompt,
        user_prompt_template=template.user_prompt_template,
        language=template.language,
        target_length=template.target_length,
        model_provider=template.model_provider,
        model_name=template.model_name,
        origin='user',
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return PromptTemplateResponse.model_validate(db_template)


@router.get("/prompt/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific prompt template."""
    template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return PromptTemplateResponse.model_validate(template)


@router.put("/prompt/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: int,
    template_update: PromptTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update a prompt template."""
    db_template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)
    return PromptTemplateResponse.model_validate(db_template)


@router.delete("/prompt/{template_id}", status_code=204)
async def delete_prompt_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Delete a prompt template."""
    template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()
    return None


@router.patch("/prompt/{template_id}/toggle", response_model=PromptTemplateResponse)
async def toggle_prompt_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Toggle a prompt template's active status."""
    template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = not template.is_active
    db.commit()
    db.refresh(template)
    return PromptTemplateResponse.model_validate(template)


@router.post("/prompt/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_prompt_templates(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple prompt templates by ID."""
    deleted_count = 0
    failed_ids = []

    for template_id in request.ids:
        template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
        if template:
            db.delete(template)
            deleted_count += 1
        else:
            failed_ids.append(template_id)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )


# ============================================================================
# REPORT TEMPLATES
# ============================================================================

@router.get("/report", response_model=List[ReportTemplateResponse])
async def list_report_templates(
    system_only: bool = False,
    user_only: bool = False,
    active_only: bool = False,
    origin: str = None,
    db: Session = Depends(get_db)
):
    """List all report templates.

    Args:
        system_only: Filter to builtin templates only (deprecated, use origin=builtin)
        user_only: Filter to user-created templates only (deprecated, use origin=user)
        active_only: Filter to active templates only
        origin: Filter by origin type (builtin, user, imported)
    """
    query = db.query(ReportTemplate)

    # New origin filter takes precedence
    if origin:
        query = query.filter(ReportTemplate.origin == origin)
    elif system_only:
        query = query.filter(ReportTemplate.origin == 'builtin')
    elif user_only:
        query = query.filter(ReportTemplate.origin == 'user')

    if active_only:
        query = query.filter(ReportTemplate.is_active == True)

    templates = query.order_by(ReportTemplate.created_at.desc()).all()
    return [ReportTemplateResponse.model_validate(t) for t in templates]


@router.post("/report", response_model=ReportTemplateResponse, status_code=201)
async def create_report_template(
    template: ReportTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new report template."""
    db_template = ReportTemplate(
        name=template.name,
        description=template.description,
        format=template.format,
        template_content=template.template_content,
        origin='user',
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return ReportTemplateResponse.model_validate(db_template)


@router.get("/report/{template_id}", response_model=ReportTemplateResponse)
async def get_report_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific report template."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return ReportTemplateResponse.model_validate(template)


@router.put("/report/{template_id}", response_model=ReportTemplateResponse)
async def update_report_template(
    template_id: int,
    template_update: ReportTemplateUpdate,
    db: Session = Depends(get_db)
):
    """Update a report template."""
    db_template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)
    return ReportTemplateResponse.model_validate(db_template)


@router.delete("/report/{template_id}", status_code=204)
async def delete_report_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Delete a report template."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()
    return None


@router.patch("/report/{template_id}/toggle", response_model=ReportTemplateResponse)
async def toggle_report_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Toggle a report template's active status."""
    template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = not template.is_active
    db.commit()
    db.refresh(template)
    return ReportTemplateResponse.model_validate(template)


@router.post("/report/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_report_templates(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple report templates by ID."""
    deleted_count = 0
    failed_ids = []

    for template_id in request.ids:
        template = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if template:
            db.delete(template)
            deleted_count += 1
        else:
            failed_ids.append(template_id)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )
