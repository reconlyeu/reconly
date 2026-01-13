"""Add agent_runs table for tracking agent research executions.

This migration creates the agent_runs table which tracks autonomous
agent research sessions similar to how feed_runs tracks feed executions.

Revision ID: 014
Revises: 013
Create Date: 2026-01-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_runs table with indexes."""
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('iterations', sa.Integer(), nullable=False, default=0),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('sources_consulted', sa.JSON(), nullable=True),
        sa.Column('result_title', sa.String(length=500), nullable=True),
        sa.Column('result_content', sa.Text(), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=False, default=0),
        sa.Column('tokens_out', sa.Integer(), nullable=False, default=0),
        sa.Column('estimated_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('trace_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Create individual indexes
    op.create_index('ix_agent_runs_source_id', 'agent_runs', ['source_id'])
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'])
    op.create_index('ix_agent_runs_trace_id', 'agent_runs', ['trace_id'])
    # Composite index for common query pattern (source + status filtering)
    op.create_index('ix_agent_runs_source_status', 'agent_runs', ['source_id', 'status'])


def downgrade() -> None:
    """Drop agent_runs table and indexes."""
    op.drop_index('ix_agent_runs_source_status', table_name='agent_runs')
    op.drop_index('ix_agent_runs_trace_id', table_name='agent_runs')
    op.drop_index('ix_agent_runs_status', table_name='agent_runs')
    op.drop_index('ix_agent_runs_source_id', table_name='agent_runs')
    op.drop_table('agent_runs')
