"""Add source health tracking columns for circuit breaker pattern.

This migration adds health tracking columns to the sources table to support
the circuit breaker pattern for source resilience:

- consecutive_failures: Count of consecutive fetch failures
- last_failure_at: Timestamp of most recent failure
- last_success_at: Timestamp of most recent success
- health_status: Current health state (healthy, degraded, unhealthy)
- circuit_open_until: When circuit will attempt recovery (if open)

Health Status Values:
- 'healthy': 0-2 consecutive failures
- 'degraded': 3-4 consecutive failures (warning state)
- 'unhealthy': 5+ consecutive failures, circuit is open

Revision ID: 018
Revises: 017
Create Date: 2026-01-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add health tracking columns to sources table."""
    # Add consecutive_failures column (default 0)
    op.add_column(
        'sources',
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0')
    )

    # Add last_failure_at column (nullable)
    op.add_column(
        'sources',
        sa.Column('last_failure_at', sa.DateTime(), nullable=True)
    )

    # Add last_success_at column (nullable)
    op.add_column(
        'sources',
        sa.Column('last_success_at', sa.DateTime(), nullable=True)
    )

    # Add health_status column (default 'healthy')
    op.add_column(
        'sources',
        sa.Column('health_status', sa.String(length=20), nullable=False, server_default='healthy')
    )

    # Add circuit_open_until column (nullable - only set when circuit is open)
    op.add_column(
        'sources',
        sa.Column('circuit_open_until', sa.DateTime(), nullable=True)
    )

    # Create index for filtering by health status
    op.create_index('ix_sources_health_status', 'sources', ['health_status'])


def downgrade() -> None:
    """Remove health tracking columns from sources table."""
    op.drop_index('ix_sources_health_status', table_name='sources')
    op.drop_column('sources', 'circuit_open_until')
    op.drop_column('sources', 'health_status')
    op.drop_column('sources', 'last_success_at')
    op.drop_column('sources', 'last_failure_at')
    op.drop_column('sources', 'consecutive_failures')
