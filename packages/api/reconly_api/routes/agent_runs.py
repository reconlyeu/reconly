"""Agent run history API routes."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload

from reconly_core.database.models import AgentRun
from reconly_api.dependencies import get_db
from reconly_api.schemas.agents import AgentRunResponse, AgentRunListResponse

router = APIRouter()


def _build_agent_run_response(run: AgentRun) -> dict:
    """Build an AgentRunResponse dict from an AgentRun model."""
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    return {
        "id": run.id,
        "source_id": run.source_id,
        "source_name": run.source.name if run.source else None,
        "prompt": run.prompt,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "iterations": run.iterations,
        "tool_calls": run.tool_calls,
        "sources_consulted": run.sources_consulted,
        "result_title": run.result_title,
        "result_content": run.result_content,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "estimated_cost": run.estimated_cost,
        "error_log": run.error_log,
        "trace_id": run.trace_id,
        "created_at": run.created_at,
        "duration_seconds": duration_seconds,
    }


@router.get("", response_model=AgentRunListResponse)
async def list_agent_runs(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    status: Optional[str] = Query(None, description="Filter by status (pending, running, completed, failed)"),
    from_date: Optional[datetime] = Query(None, description="Filter by start date (inclusive)"),
    to_date: Optional[datetime] = Query(None, description="Filter by end date (inclusive)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """
    List agent run history with optional filtering.

    Returns recent agent runs ordered by created_at (newest first).
    Supports filtering by source_id, status, and date range.
    """
    query = db.query(AgentRun).options(joinedload(AgentRun.source))

    if source_id is not None:
        query = query.filter(AgentRun.source_id == source_id)

    if status:
        query = query.filter(AgentRun.status == status)

    if from_date:
        query = query.filter(AgentRun.created_at >= from_date)

    if to_date:
        query = query.filter(AgentRun.created_at <= to_date)

    # Get total count for pagination
    total = query.count()

    agent_runs = query.order_by(
        AgentRun.created_at.desc()
    ).limit(limit).offset(offset).all()

    items = [AgentRunResponse(**_build_agent_run_response(run)) for run in agent_runs]
    return AgentRunListResponse(items=items, total=total)


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Get details of a specific agent run.

    Returns comprehensive information about a single agent run including
    metrics, timing, status, source name, and execution results.
    """
    agent_run = db.query(AgentRun).options(
        joinedload(AgentRun.source)
    ).filter(AgentRun.id == run_id).first()

    if not agent_run:
        raise HTTPException(status_code=404, detail="Agent run not found")

    return AgentRunResponse(**_build_agent_run_response(agent_run))
