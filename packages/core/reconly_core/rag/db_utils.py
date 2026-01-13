"""Database utilities for RAG module.

Shared helper functions used by search and graph services.
PostgreSQL with pgvector is required.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def ensure_postgres(db: "Session") -> None:
    """Verify that the database is PostgreSQL.

    Raises:
        RuntimeError: If not using PostgreSQL

    Args:
        db: Database session
    """
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect != "postgresql":
            raise RuntimeError(
                f"PostgreSQL is required for RAG features, but using {dialect or 'unknown'}. "
                "Please configure a PostgreSQL database with pgvector extension."
            )
    except AttributeError:
        raise RuntimeError("Could not determine database dialect. PostgreSQL is required.")
