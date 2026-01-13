"""Add content filter columns to sources.

Adds include_keywords, exclude_keywords, filter_mode, and use_regex columns
for filtering fetched items before LLM summarization.

Revision ID: 008
Revises: 007
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content filter columns to sources table."""
    op.add_column('sources', sa.Column('include_keywords', sa.JSON(), nullable=True))
    op.add_column('sources', sa.Column('exclude_keywords', sa.JSON(), nullable=True))
    op.add_column('sources', sa.Column('filter_mode', sa.String(20), nullable=True, server_default='both'))
    op.add_column('sources', sa.Column('use_regex', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Remove content filter columns from sources table."""
    op.drop_column('sources', 'use_regex')
    op.drop_column('sources', 'filter_mode')
    op.drop_column('sources', 'exclude_keywords')
    op.drop_column('sources', 'include_keywords')
