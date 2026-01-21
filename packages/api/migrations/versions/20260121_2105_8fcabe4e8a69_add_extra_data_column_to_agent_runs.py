"""Add extra_data column to agent_runs

Revision ID: 8fcabe4e8a69
Revises: 020
Create Date: 2026-01-21 21:05:55.022212

This migration adds the extra_data JSON column to agent_runs for storing
strategy-specific metadata like research_strategy, subtopics, etc.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8fcabe4e8a69'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add extra_data column to agent_runs table."""
    op.add_column(
        'agent_runs',
        sa.Column('extra_data', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Remove extra_data column from agent_runs table."""
    op.drop_column('agent_runs', 'extra_data')
