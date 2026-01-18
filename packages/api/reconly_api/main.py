"""FastAPI main application."""
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# Load .env file before any other imports that use environment variables
from dotenv import load_dotenv
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from reconly_core.logging import configure_logging, get_logger, generate_trace_id, get_trace_id
from reconly_core.database import Base
from reconly_api.config import settings, validate_secret_key, validate_configuration, SecretKeyValidationError
from reconly_api.dependencies import SessionLocal, engine, limiter
from reconly_api.middleware import SecurityHeadersMiddleware
from reconly_api.routes import (
    digests, health, sources, feeds, feed_runs, templates,
    analytics, providers, dashboard, auth, exporters, fetchers, tags, bundles,
    extensions, search, rag, graph, agent_runs, oauth, chat
)
from reconly_api.routes import settings as settings_routes
from reconly_api.auth.password import is_public_route


def cleanup_stale_feed_runs(stale_threshold_hours: int = 1) -> int:
    """
    Mark feed runs that have been 'running' for too long as 'failed'.

    This handles cases where a feed run process crashed or was interrupted
    without properly updating the database status.

    Args:
        stale_threshold_hours: Number of hours after which a running feed is considered stale

    Returns:
        Number of feed runs that were marked as failed
    """
    from reconly_core.database.models import FeedRun

    try:
        db = SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=stale_threshold_hours)

            # Find stale feed runs
            stale_runs = db.query(FeedRun).filter(
                FeedRun.status == 'running',
                FeedRun.started_at < cutoff_time
            ).all()

            count = len(stale_runs)
            if count > 0:
                for run in stale_runs:
                    run.status = 'failed'
                    run.completed_at = datetime.utcnow()
                db.commit()
                print(f"[Startup] Cleaned up {count} stale feed run(s) that were stuck in 'running' status")

            return count
        finally:
            db.close()
    except Exception as e:
        # Gracefully handle errors during startup cleanup (e.g., during tests)
        print(f"[Startup] Skipping stale feed run cleanup: {e}")
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Configure structured logging
    configure_logging(
        log_level=settings.log_level if hasattr(settings, "log_level") else "INFO",
        json_output=False,
        development=True,
    )
    logger = get_logger(__name__)
    logger.info("Starting Reconly API", version=settings.app_version)

    # Validate SECRET_KEY configuration
    # This will raise SecretKeyValidationError in production if the key is insecure
    try:
        validate_secret_key(settings)
    except SecretKeyValidationError as e:
        logger.error("SECRET_KEY validation failed - aborting startup", error=str(e))
        raise SystemExit(f"FATAL: {e}") from e

    # Validate configuration and log summary
    # This tests DB connection, checks LLM keys, validates CORS - warns but doesn't abort
    validate_configuration(settings, db_session_factory=SessionLocal)

    # Create database tables if they don't exist
    logger.info("Initializing database tables")
    Base.metadata.create_all(bind=engine)

    # Startup: Clean up any stale feed runs from previous sessions
    cleanup_stale_feed_runs()

    # Start feed scheduler (APScheduler)
    from reconly_api.scheduler import init_scheduler, start_scheduler, shutdown_scheduler
    try:
        init_scheduler()
        start_scheduler()
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    yield

    # Shutdown: Stop scheduler
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")

    logger.info("Shutting down Reconly API")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API for Reconly - AI-powered RSS aggregator with summarization",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Secure exception handler - hides internal errors in production
@app.exception_handler(Exception)
async def secure_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them securely.

    In production (debug=False):
    - Returns generic "Internal server error" message
    - Logs full exception details with structlog for debugging

    In development (debug=True):
    - Returns detailed error message for debugging
    - Logs full exception details
    """
    logger = get_logger(__name__)

    # Generate or get request_id for correlation
    request_id = get_trace_id()
    if not request_id:
        request_id = generate_trace_id()

    # Always log the full exception with traceback
    logger.error(
        "Unhandled exception",
        request_id=request_id,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        path=str(request.url.path),
        method=request.method,
        exc_info=True,  # Include full traceback in logs
    )

    # In debug mode, return detailed error info
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Unhandled exception: {type(exc).__name__}: {exc}",
                "request_id": request_id,
            }
        )

    # In production, return generic error with request_id for correlation
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware, csp_policy=settings.csp_policy)

# Auth middleware - protect all routes when password is configured
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Check authentication for protected routes when password is configured.

    Public routes (health, config, auth, docs) are always accessible.
    Other routes require valid session cookie or Basic Auth.
    """
    from fastapi.responses import JSONResponse

    # Skip auth check if no password is configured
    if not settings.auth_required:
        return await call_next(request)

    # Skip auth for public routes
    if is_public_route(request.url.path):
        return await call_next(request)

    # Skip auth for static assets (UI files)
    path = request.url.path
    if path.startswith("/_astro/") or path.endswith((".css", ".js", ".svg", ".png", ".ico")):
        return await call_next(request)

    # Check authentication
    from reconly_api.auth.password import check_auth_cookie, check_basic_auth
    if check_auth_cookie(request) or check_basic_auth(request):
        return await call_next(request)

    # Return 401 for API routes, redirect to login for UI routes
    if path.startswith("/api/") or path.startswith(settings.api_v1_prefix):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": "Basic"},
        )

    # For UI routes, still return 401 (UI will handle redirect)
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required"},
    )


# Include API routers
app.include_router(health.router, tags=["health"])

# Auth routes
app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
    tags=["auth"]
)

# Dashboard
app.include_router(
    dashboard.router,
    prefix=f"{settings.api_v1_prefix}/dashboard",
    tags=["dashboard"]
)

# Sources
app.include_router(
    sources.router,
    prefix=f"{settings.api_v1_prefix}/sources",
    tags=["sources"]
)

# Feeds
app.include_router(
    feeds.router,
    prefix=f"{settings.api_v1_prefix}/feeds",
    tags=["feeds"]
)

# Feed Runs
app.include_router(
    feed_runs.router,
    prefix=f"{settings.api_v1_prefix}/feed-runs",
    tags=["feed-runs"]
)

# Templates
app.include_router(
    templates.router,
    prefix=f"{settings.api_v1_prefix}/templates",
    tags=["templates"]
)

# Digests
app.include_router(
    digests.router,
    prefix=f"{settings.api_v1_prefix}/digests",
    tags=["digests"]
)

# Tags
app.include_router(
    tags.router,
    prefix=f"{settings.api_v1_prefix}/tags",
    tags=["tags"]
)

# Exporters
app.include_router(
    exporters.router,
    prefix=f"{settings.api_v1_prefix}",
    tags=["exporters"]
)

# Fetchers
app.include_router(
    fetchers.router,
    prefix=f"{settings.api_v1_prefix}",
    tags=["fetchers"]
)

# Analytics
app.include_router(
    analytics.router,
    prefix=f"{settings.api_v1_prefix}/analytics",
    tags=["analytics"]
)

# Providers
app.include_router(
    providers.router,
    prefix=f"{settings.api_v1_prefix}/providers",
    tags=["providers"]
)

# Settings
app.include_router(
    settings_routes.router,
    prefix=f"{settings.api_v1_prefix}/settings",
    tags=["settings"]
)

# Bundles (marketplace export/import)
app.include_router(
    bundles.router,
    prefix=f"{settings.api_v1_prefix}",
    tags=["bundles"]
)

# Extensions
app.include_router(
    extensions.router,
    prefix=f"{settings.api_v1_prefix}",
    tags=["extensions"]
)

# Search (RAG hybrid search)
app.include_router(
    search.router,
    prefix=f"{settings.api_v1_prefix}/search",
    tags=["search"]
)

# RAG (Retrieval-Augmented Generation)
app.include_router(
    rag.router,
    prefix=f"{settings.api_v1_prefix}/rag",
    tags=["rag"]
)

# Graph (Knowledge Graph visualization)
app.include_router(
    graph.router,
    prefix=f"{settings.api_v1_prefix}/graph",
    tags=["graph"]
)

# Agent Runs
app.include_router(
    agent_runs.router,
    prefix=f"{settings.api_v1_prefix}/agent-runs",
    tags=["agent-runs"]
)

# OAuth (Email OAuth2 authentication)
app.include_router(
    oauth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
    tags=["oauth"]
)

# Chat (LLM conversations with tool calling)
app.include_router(
    chat.router,
    prefix=f"{settings.api_v1_prefix}/chat",
    tags=["chat"]
)


# Determine UI directory path
# When running from packages/api, the UI is at ../../ui/dist
# When running from project root, the UI is at reconly-oss/ui/dist
# When running in Docker, the UI is at /app/ui/dist
UI_DIR = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if not UI_DIR.exists():
    # Try alternative path (running from project root)
    UI_DIR = Path("reconly-oss/ui/dist")
if not UI_DIR.exists():
    # Try Docker path
    UI_DIR = Path("/app/ui/dist")
if not UI_DIR.exists():
    print(f"Warning: UI directory not found at {UI_DIR}")
    UI_DIR = None


@app.get("/")
async def root():
    """Root endpoint - serve UI or API info."""
    if UI_DIR and UI_DIR.exists():
        return FileResponse(UI_DIR / "index.html")
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


# Mount static files for UI (only if UI directory exists)
if UI_DIR and UI_DIR.exists():
    # Mount _astro assets directory
    astro_dir = UI_DIR / "_astro"
    if astro_dir.exists():
        app.mount("/_astro", StaticFiles(directory=str(astro_dir)), name="astro")

    # Serve favicon
    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(UI_DIR / "favicon.svg")

    # Catch-all route for SPA routing (serve index.html for all non-API routes)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        from fastapi import HTTPException
        # Don't intercept API routes, docs, or static assets
        if full_path.startswith(("api/", "docs", "redoc", "health", "_astro/")):
            raise HTTPException(status_code=404, detail="Not Found")

        # Check if there's a direct file match (for page routes like /sources/index.html)
        file_path = UI_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Check if there's an index.html in a directory
        index_path = UI_DIR / full_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)

        # Fall back to root index.html for client-side routing
        return FileResponse(UI_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
