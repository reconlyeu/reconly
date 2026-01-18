"""FastAPI dependency injection for database sessions and rate limiting."""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from reconly_api.config import settings


# Check if we're in a test environment (pytest sets this, or check for test database)
_is_testing = (
    os.environ.get("PYTEST_CURRENT_TEST") is not None
    or "test" in os.environ.get("DATABASE_URL", "").lower()
)

# Shared rate limiter instance for use across route files
# Default limit is configurable via settings.rate_limit_per_minute
# Disabled during tests to prevent flaky test failures
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    enabled=not _is_testing
)


def get_engine():
    """Create database engine with PostgreSQL connection pooling."""
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.debug
    )


# Create engine and session factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Usage:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
