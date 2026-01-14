"""Add user_id to agent_runs for enterprise multi-user support.

This migration adds optional user_id FK to agent_runs table.
In OSS mode this stays NULL; enterprise populates it for audit/attribution.

Revision ID: 015
Revises: 014
Create Date: 2026-01-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id column with FK to users table."""
    op.add_column(
        'agent_runs',
        sa.Column('user_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_agent_runs_user_id',
        'agent_runs',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_agent_runs_user_id', 'agent_runs', ['user_id'])


def downgrade() -> None:
    """Remove user_id column."""
    op.drop_index('ix_agent_runs_user_id', table_name='agent_runs')
    op.drop_constraint('fk_agent_runs_user_id', 'agent_runs', type_='foreignkey')
    op.drop_column('agent_runs', 'user_id')
