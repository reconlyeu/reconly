"""add image_url to digests

Revision ID: 7c4acf62b4b1
Revises: 008
Create Date: 2026-01-08 13:23:47.153303
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4acf62b4b1'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    with op.batch_alter_table('digests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    """Downgrade database schema."""
    with op.batch_alter_table('digests', schema=None) as batch_op:
        batch_op.drop_column('image_url')
