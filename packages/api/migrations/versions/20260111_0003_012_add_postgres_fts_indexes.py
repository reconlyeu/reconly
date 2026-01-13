"""Add PostgreSQL full-text search indexes on digests table.

Creates GIN indexes using to_tsvector for efficient full-text search on
title, summary, and content columns. These indexes enable fast text search
without requiring external search infrastructure.

Note: PostgreSQL is required for this project.

Revision ID: 012
Revises: 011
Create Date: 2026-01-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PostgreSQL full-text search indexes."""
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    # Only create FTS indexes for PostgreSQL
    if dialect_name != 'postgresql':
        return

    # Create GIN index on title using English text search configuration
    op.execute(text('''
        CREATE INDEX IF NOT EXISTS ix_digests_title_fts
        ON digests
        USING GIN (to_tsvector('english', COALESCE(title, '')))
    '''))

    # Create GIN index on summary
    op.execute(text('''
        CREATE INDEX IF NOT EXISTS ix_digests_summary_fts
        ON digests
        USING GIN (to_tsvector('english', COALESCE(summary, '')))
    '''))

    # Create combined GIN index on title + summary for unified search
    # This is useful for searching across both fields simultaneously
    op.execute(text('''
        CREATE INDEX IF NOT EXISTS ix_digests_title_summary_fts
        ON digests
        USING GIN (to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, '')))
    '''))

    # Create GIN index on content for deep content search
    # Note: This index can be large for long content, but enables fast search
    op.execute(text('''
        CREATE INDEX IF NOT EXISTS ix_digests_content_fts
        ON digests
        USING GIN (to_tsvector('english', COALESCE(content, '')))
    '''))


def downgrade() -> None:
    """Remove PostgreSQL full-text search indexes."""
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    # Only drop FTS indexes for PostgreSQL
    if dialect_name != 'postgresql':
        return

    op.execute(text('DROP INDEX IF EXISTS ix_digests_content_fts'))
    op.execute(text('DROP INDEX IF EXISTS ix_digests_title_summary_fts'))
    op.execute(text('DROP INDEX IF EXISTS ix_digests_summary_fts'))
    op.execute(text('DROP INDEX IF EXISTS ix_digests_title_fts'))
