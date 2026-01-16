"""Health check endpoints.

Provides health check endpoints for monitoring and deployment purposes:

- GET /health - Public endpoint returning simple healthy/unhealthy status
- GET /health/detailed - Protected endpoint with full system details
  (requires authentication in production mode)

The separation ensures that:
1. Load balancers can check /health without authentication
2. Detailed system information is not exposed publicly in production
"""
from collections import Counter
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from reconly_api.config import settings
from reconly_api.dependencies import get_db
from reconly_api.auth.password import check_auth_cookie, check_basic_auth
from reconly_api.schemas.sources import SourcesHealthSummary
from reconly_core.database.models import Source
from reconly_api.routes.sources import _source_to_health_response


router = APIRouter()

# Track application start time for uptime calculation
_start_time: Optional[datetime] = None


def get_start_time() -> datetime:
    """Get or initialize the application start time."""
    global _start_time
    if _start_time is None:
        _start_time = datetime.now()
    return _start_time


class HealthStatus(BaseModel):
    """Simple health status response."""

    status: str


class DetailedHealthStatus(BaseModel):
    """Detailed health status response with system information."""

    status: str
    version: str
    environment: str
    database: str
    uptime_seconds: float
    timestamp: str
    components: dict


def _check_database(db: Session) -> tuple[bool, Optional[str]]:
    """Check database connectivity.

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return True, None
        return False, "Unexpected query result"
    except OperationalError as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def _is_authenticated_or_development(request: Request) -> bool:
    """Check if the request is authenticated or we're in development mode.

    In development mode (RECONLY_ENV != production), detailed health info
    is accessible without authentication. In production, authentication
    is required.

    Args:
        request: The FastAPI request object

    Returns:
        True if access should be granted, False otherwise
    """
    # Development mode: always allow access
    if not settings.is_production:
        return True

    # Production mode: require authentication if auth is configured
    if settings.auth_required:
        return check_auth_cookie(request) or check_basic_auth(request)

    # Production mode without auth configured: allow access
    # (user chose not to enable auth protection)
    return True


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """Public health check endpoint.

    Returns a simple status indicating whether the service is running.
    This endpoint is always public and suitable for load balancer health checks.

    Returns:
        {"status": "healthy"} if the service is running
    """
    return HealthStatus(status="healthy")


@router.get("/health/detailed", response_model=DetailedHealthStatus)
async def health_check_detailed(
    request: Request,
    db: Session = Depends(get_db),
):
    """Detailed health check endpoint with system information.

    This endpoint provides comprehensive system status including:
    - Application version
    - Environment (development/production)
    - Database connectivity status
    - Component statuses
    - Uptime

    Access Control:
    - Development mode: Always accessible (for debugging)
    - Production mode: Requires authentication if RECONLY_AUTH_PASSWORD is set

    Returns:
        Detailed health status object

    Raises:
        HTTPException 401: If authentication is required but not provided
    """
    # Check access permissions
    if not _is_authenticated_or_development(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for detailed health information",
            headers={"WWW-Authenticate": "Basic"},
        )

    start_time = get_start_time()
    uptime = (datetime.now() - start_time).total_seconds()

    # Check database connectivity
    db_healthy, db_error = _check_database(db)

    # Build component status
    components = {
        "database": {
            "status": "connected" if db_healthy else "disconnected",
            "error": db_error,
        },
        "scheduler": {
            "status": "running",  # Scheduler runs in the same process
        },
    }

    # Overall status is unhealthy if critical components fail
    overall_status = "healthy" if db_healthy else "unhealthy"

    return DetailedHealthStatus(
        status=overall_status,
        version=settings.app_version,
        environment=settings.reconly_env,
        database="connected" if db_healthy else "disconnected",
        uptime_seconds=uptime,
        timestamp=datetime.now().isoformat(),
        components=components,
    )


@router.get("/health/sources", response_model=SourcesHealthSummary)
async def get_sources_health_summary(
    include_details: bool = False,
    enabled_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get aggregate health status across all sources.

    Returns a summary of source health for monitoring dashboards
    and alerting systems.

    Args:
        include_details: If true, include per-source health details
        enabled_only: If true (default), only include enabled sources

    Returns:
        Summary with counts of healthy, degraded, and unhealthy sources,
        optionally with detailed per-source information.
    """
    query = db.query(Source)
    if enabled_only:
        query = query.filter(Source.enabled == True)

    sources = query.all()

    # Count by health status
    counts = Counter(source.health_status for source in sources)
    source_details = [_source_to_health_response(s) for s in sources] if include_details else None

    return SourcesHealthSummary(
        healthy=counts.get("healthy", 0),
        degraded=counts.get("degraded", 0),
        unhealthy=counts.get("unhealthy", 0),
        total=len(sources),
        sources=source_details,
    )
