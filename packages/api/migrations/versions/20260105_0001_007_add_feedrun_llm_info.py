"""Add LLM provider and model info to feed_runs.

Tracks which LLM provider and model was used for each feed run.

Revision ID: 007
Revises: 006
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add llm_provider and llm_model columns to feed_runs table."""
    op.add_column('feed_runs', sa.Column('llm_provider', sa.String(100), nullable=True))
    op.add_column('feed_runs', sa.Column('llm_model', sa.String(100), nullable=True))


def downgrade() -> None:
    """Remove llm_provider and llm_model columns from feed_runs table."""
    op.drop_column('feed_runs', 'llm_model')
    op.drop_column('feed_runs', 'llm_provider')
