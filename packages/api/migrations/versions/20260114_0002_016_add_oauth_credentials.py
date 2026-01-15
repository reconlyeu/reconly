"""Add oauth_credentials table for email OAuth2 token storage.

This migration creates the oauth_credentials table which stores encrypted
OAuth2 access and refresh tokens for Gmail and Outlook email providers.

Revision ID: 016
Revises: 015
Create Date: 2026-01-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create oauth_credentials table with indexes."""
    op.create_table(
        'oauth_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id'),
    )
    # Create index on source_id for fast lookups
    op.create_index('ix_oauth_credentials_source_id', 'oauth_credentials', ['source_id'])
    # Create index on provider for filtering
    op.create_index('ix_oauth_credentials_provider', 'oauth_credentials', ['provider'])


def downgrade() -> None:
    """Drop oauth_credentials table and indexes."""
    op.drop_index('ix_oauth_credentials_provider', table_name='oauth_credentials')
    op.drop_index('ix_oauth_credentials_source_id', table_name='oauth_credentials')
    op.drop_table('oauth_credentials')
