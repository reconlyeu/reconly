"""Add consolidated digest support.

Adds digest_mode to feeds, consolidated_count to digests, and digest_source_items table.

Revision ID: 006
Revises: 005
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add consolidated digest support.

    1. Add digest_mode to feeds (individual, per_source, all_sources)
    2. Add consolidated_count to digests
    3. Create digest_source_items junction table for provenance tracking
    """
    # Add digest_mode column to feeds table
    op.add_column(
        'feeds',
        sa.Column('digest_mode', sa.String(20), nullable=False, server_default='individual')
    )

    # Add consolidated_count column to digests table
    op.add_column(
        'digests',
        sa.Column('consolidated_count', sa.Integer(), nullable=False, server_default='1')
    )

    # Create digest_source_items junction table
    op.create_table(
        'digest_source_items',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('digest_id', sa.Integer(), sa.ForeignKey('digests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('item_url', sa.String(2048), nullable=False),
        sa.Column('item_title', sa.String(512), nullable=True),
        sa.Column('item_published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for digest_source_items
    op.create_index('ix_digest_source_items_digest_id', 'digest_source_items', ['digest_id'])
    op.create_index('ix_digest_source_items_source_id', 'digest_source_items', ['source_id'])
    op.create_index('ix_digest_source_items_digest_source', 'digest_source_items', ['digest_id', 'source_id'])


def downgrade() -> None:
    """Remove consolidated digest support."""
    # Drop indexes
    op.drop_index('ix_digest_source_items_digest_source', table_name='digest_source_items')
    op.drop_index('ix_digest_source_items_source_id', table_name='digest_source_items')
    op.drop_index('ix_digest_source_items_digest_id', table_name='digest_source_items')

    # Drop digest_source_items table
    op.drop_table('digest_source_items')

    # Drop consolidated_count column from digests
    op.drop_column('digests', 'consolidated_count')

    # Drop digest_mode column from feeds
    op.drop_column('feeds', 'digest_mode')
