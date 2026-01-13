"""Add indexes on digests title and summary for faster search.

This migration adds indexes to improve search performance on the digests table.
The ILIKE pattern matching used in search was causing full table scans.

Revision ID: 002
Revises: 001
Create Date: 2026-01-02
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes on title and summary columns."""
    op.create_index('ix_digests_title', 'digests', ['title'])
    op.create_index('ix_digests_summary', 'digests', ['summary'], postgresql_ops={'summary': 'text_pattern_ops'})


def downgrade() -> None:
    """Remove the indexes."""
    op.drop_index('ix_digests_summary', table_name='digests')
    op.drop_index('ix_digests_title', table_name='digests')
