"""Replace is_system with origin for template provenance tracking

Replaces the boolean is_system flag with a string origin field that supports
three values: 'builtin', 'user', 'imported'. Also adds imported_from_bundle
field to track marketplace provenance.

Revision ID: 009
Revises: 7c4acf62b4b1
Create Date: 2026-01-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '7c4acf62b4b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # PromptTemplate: Add origin and imported_from_bundle, migrate data, drop is_system
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        # Add new columns
        batch_op.add_column(sa.Column('origin', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('imported_from_bundle', sa.String(length=100), nullable=True))

    # Migrate data: is_system=True -> origin='builtin', else origin='user'
    op.execute(
        "UPDATE prompt_templates SET origin = CASE WHEN is_system = TRUE THEN 'builtin' ELSE 'user' END"
    )

    # Make origin NOT NULL and drop is_system
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.alter_column('origin', nullable=False, server_default='user')
        batch_op.drop_column('is_system')

    # ReportTemplate: Add origin and imported_from_bundle, migrate data, drop is_system
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        # Add new columns
        batch_op.add_column(sa.Column('origin', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('imported_from_bundle', sa.String(length=100), nullable=True))

    # Migrate data: is_system=True -> origin='builtin', else origin='user'
    op.execute(
        "UPDATE report_templates SET origin = CASE WHEN is_system = TRUE THEN 'builtin' ELSE 'user' END"
    )

    # Make origin NOT NULL and drop is_system
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.alter_column('origin', nullable=False, server_default='user')
        batch_op.drop_column('is_system')


def downgrade() -> None:
    """Downgrade database schema."""
    # PromptTemplate: Add is_system back, migrate data, drop new columns
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_system', sa.Boolean(), nullable=True, server_default='0'))

    # Migrate data: origin='builtin' -> is_system=True, else is_system=False
    op.execute(
        "UPDATE prompt_templates SET is_system = CASE WHEN origin = 'builtin' THEN TRUE ELSE FALSE END"
    )

    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.alter_column('is_system', nullable=False)
        batch_op.drop_column('imported_from_bundle')
        batch_op.drop_column('origin')

    # ReportTemplate: Add is_system back, migrate data, drop new columns
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_system', sa.Boolean(), nullable=True, server_default='0'))

    # Migrate data: origin='builtin' -> is_system=True, else is_system=False
    op.execute(
        "UPDATE report_templates SET is_system = CASE WHEN origin = 'builtin' THEN TRUE ELSE FALSE END"
    )

    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.alter_column('is_system', nullable=False)
        batch_op.drop_column('imported_from_bundle')
        batch_op.drop_column('origin')
