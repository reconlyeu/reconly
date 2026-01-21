"""Agent run history API routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from reconly_api.dependencies import get_db
from reconly_api.schemas.agents import (
    AgentCapabilitiesResponse,
    AgentRunListResponse,
    AgentRunResponse,
    StrategyInfoResponse,
)
from reconly_core.agents import AgentSettings, get_agent_capabilities
from reconly_core.database.models import AgentRun
from reconly_core.services.settings_service import SettingsService

router = APIRouter()


def _build_agent_run_response(run: AgentRun) -> dict[str, object]:
    """Build an AgentRunResponse dict from an AgentRun model.

    Extracts research strategy fields from extra_data JSON if present.
    """
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    # Extract research strategy fields from extra_data
    extra_data = run.extra_data or {}
    research_strategy = extra_data.get("research_strategy", "simple")
    subtopics = extra_data.get("subtopics")
    research_plan = extra_data.get("research_plan")
    report_format = extra_data.get("report_format")

    # source_count can come from extra_data or be derived from sources_consulted
    source_count = extra_data.get("source_count")
    if source_count is None and run.sources_consulted:
        source_count = len(run.sources_consulted)

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
        # Research strategy fields
        "research_strategy": research_strategy,
        "subtopics": subtopics,
        "research_plan": research_plan,
        "report_format": report_format,
        "source_count": source_count,
    }


@router.get("", response_model=AgentRunListResponse)
async def list_agent_runs(
    source_id: int | None = Query(None, description="Filter by source ID"),
    status: str | None = Query(None, description="Filter by status (pending, running, completed, failed)"),
    from_date: datetime | None = Query(None, description="Filter by start date (inclusive)"),
    to_date: datetime | None = Query(None, description="Filter by end date (inclusive)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
) -> AgentRunListResponse:
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


@router.get("/capabilities", response_model=AgentCapabilitiesResponse)
async def get_capabilities(db: Session = Depends(get_db)) -> AgentCapabilitiesResponse:
    """
    Check available agent research capabilities.

    Returns information about which research strategies are available,
    whether GPT Researcher is installed, and which search providers
    are configured.

    This endpoint is useful for:
    - UI to show/hide strategy options based on availability
    - Diagnosing configuration issues
    - Checking if advanced research features are available
    """
    # Get agent settings from settings service
    settings_service = SettingsService(db)
    agent_settings = AgentSettings.from_settings_service(settings_service)

    # Get capabilities using the core utility
    capabilities = get_agent_capabilities(settings=agent_settings)

    # Convert to response model
    strategies = {
        name: StrategyInfoResponse(
            available=info.available,
            description=info.description,
            estimated_duration_seconds=info.estimated_duration_seconds,
            requires_api_key=info.requires_api_key,
        )
        for name, info in capabilities.strategies.items()
    }

    return AgentCapabilitiesResponse(
        strategies=strategies,
        gpt_researcher_installed=capabilities.gpt_researcher_installed,
        search_providers=capabilities.search_providers,
        configured_search_provider=capabilities.configured_search_provider,
    )


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> AgentRunResponse:
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
