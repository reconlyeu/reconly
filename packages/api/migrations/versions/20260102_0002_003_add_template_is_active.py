"""Add is_active field to prompt_templates and report_templates.

This migration adds an is_active boolean field to both template tables
to allow users to enable/disable templates without deleting them.

Revision ID: 003
Revises: 002
Create Date: 2026-01-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active column to template tables."""
    # Add is_active to prompt_templates (default True for existing records)
    op.add_column('prompt_templates', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))

    # Add is_active to report_templates (default True for existing records)
    op.add_column('report_templates', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Remove is_active column from template tables."""
    op.drop_column('report_templates', 'is_active')
    op.drop_column('prompt_templates', 'is_active')
