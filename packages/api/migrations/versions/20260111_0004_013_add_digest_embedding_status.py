"""Add embedding_status and embedding_error columns to digests table.

Adds tracking for the RAG embedding process:
- embedding_status: NULL (legacy), pending, completed, failed
- embedding_error: Error message if embedding failed

Revision ID: 013
Revises: 012
Create Date: 2026-01-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding_status and embedding_error columns to digests."""
    # Add embedding_status column (nullable for legacy digests)
    op.add_column(
        'digests',
        sa.Column('embedding_status', sa.String(20), nullable=True)
    )

    # Add embedding_error column for storing error messages
    op.add_column(
        'digests',
        sa.Column('embedding_error', sa.Text(), nullable=True)
    )

    # Create index on embedding_status for efficient querying of unembedded digests
    op.create_index(
        'ix_digests_embedding_status',
        'digests',
        ['embedding_status']
    )


def downgrade() -> None:
    """Remove embedding_status and embedding_error columns."""
    op.drop_index('ix_digests_embedding_status', table_name='digests')
    op.drop_column('digests', 'embedding_error')
    op.drop_column('digests', 'embedding_status')
