"""Add connections table and source.connection_id foreign key.

This migration adds the connections table for reusable credential storage
and links it to sources via a new connection_id column.

Connections enable credential reuse across multiple sources (e.g., same
Gmail account for multiple email sources with different filters).

Connection Types:
- email_imap: IMAP credentials (host, port, username, password)
- email_oauth: OAuth2 credentials (tokens, provider info)
- http_basic: HTTP Basic Auth (username, password)
- api_key: API key authentication (key, optional header name)

Revision ID: 021
Revises: 8fcabe4e8a69
Create Date: 2026-01-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '8fcabe4e8a69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create connections table and add connection_id to sources."""
    # Create connections table
    op.create_table(
        'connections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('config_encrypted', sa.Text(), nullable=False),
        sa.Column('last_check_at', sa.DateTime(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for connections table
    op.create_index('ix_connections_user_id', 'connections', ['user_id'])
    op.create_index('ix_connections_type', 'connections', ['type'])
    op.create_index('ix_connections_user_type', 'connections', ['user_id', 'type'])

    # Add connection_id foreign key to sources table
    op.add_column(
        'sources',
        sa.Column('connection_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_sources_connection_id',
        'sources',
        'connections',
        ['connection_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_sources_connection_id', 'sources', ['connection_id'])


def downgrade() -> None:
    """Remove connections table and connection_id from sources."""
    # Remove connection_id from sources
    op.drop_index('ix_sources_connection_id', table_name='sources')
    op.drop_constraint('fk_sources_connection_id', 'sources', type_='foreignkey')
    op.drop_column('sources', 'connection_id')

    # Drop connections table indexes
    op.drop_index('ix_connections_user_type', table_name='connections')
    op.drop_index('ix_connections_type', table_name='connections')
    op.drop_index('ix_connections_user_id', table_name='connections')

    # Drop connections table
    op.drop_table('connections')
