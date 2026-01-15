"""Add auth_status column to sources table for IMAP authentication tracking.

This migration adds the auth_status column to track authentication state for
sources that require credentials (IMAP email sources). Values can be:
- NULL: No authentication required (RSS, websites, etc.)
- 'active': Authenticated and working
- 'pending_oauth': OAuth flow not completed
- 'auth_failed': Authentication failed, needs re-authentication

Revision ID: 017
Revises: 016
Create Date: 2026-01-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auth_status column to sources table."""
    op.add_column(
        'sources',
        sa.Column('auth_status', sa.String(length=20), nullable=True)
    )
    # Create index for filtering by auth status
    op.create_index('ix_sources_auth_status', 'sources', ['auth_status'])


def downgrade() -> None:
    """Remove auth_status column from sources table."""
    op.drop_index('ix_sources_auth_status', table_name='sources')
    op.drop_column('sources', 'auth_status')
