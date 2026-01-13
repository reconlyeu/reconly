"""Add trace_id and error_details fields to feed_runs.

This migration adds:
- trace_id: UUID string for log correlation across the system
- error_details: JSON field for structured error information with source context

Revision ID: 004
Revises: 003
Create Date: 2026-01-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trace_id and error_details columns to feed_runs."""
    # Add trace_id column with index for correlation queries
    op.add_column('feed_runs', sa.Column('trace_id', sa.String(36), nullable=True))
    op.create_index('ix_feed_runs_trace_id', 'feed_runs', ['trace_id'])

    # Add error_details JSON column for structured errors
    op.add_column('feed_runs', sa.Column('error_details', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove trace_id and error_details columns from feed_runs."""
    op.drop_index('ix_feed_runs_trace_id', table_name='feed_runs')
    op.drop_column('feed_runs', 'error_details')
    op.drop_column('feed_runs', 'trace_id')
