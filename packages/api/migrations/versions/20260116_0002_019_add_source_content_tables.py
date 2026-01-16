"""Add source_contents and source_content_chunks tables for RAG system.

Creates tables to store original fetched content from source items for RAG embedding.
Instead of embedding processed digest summaries (which contain template-based
formatting noise), we embed the raw source content for cleaner semantic search.

Tables created:
- source_contents: Stores original fetched content from source items
- source_content_chunks: Stores embedded text chunks for vector similarity search

The pgvector extension must already be installed (created by migration 010).

Requires PostgreSQL with pgvector extension.

Revision ID: 019
Revises: 018
Create Date: 2026-01-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vector dimension matching BGE-M3 default (same as digest_chunks)
VECTOR_DIMENSION = 1024


def upgrade() -> None:
    """Create source_contents and source_content_chunks tables with vector embedding support."""
    # Get the current connection and dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    # Require PostgreSQL
    if dialect_name != 'postgresql':
        raise RuntimeError(
            f"PostgreSQL is required for RAG features, but using {dialect_name}. "
            "Please configure a PostgreSQL database with pgvector extension."
        )

    # Create source_contents table
    op.create_table(
        'source_contents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('digest_source_item_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('content_length', sa.Integer(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('embedding_status', sa.String(20), nullable=True),
        sa.Column('embedding_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['digest_source_item_id'],
            ['digest_source_items.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('digest_source_item_id', name='uq_source_contents_digest_source_item_id'),
    )

    # Create indexes for source_contents
    # Note: digest_source_item_id already has a unique constraint which creates an implicit index
    op.create_index('ix_source_contents_content_hash', 'source_contents', ['content_hash'])
    op.create_index('ix_source_contents_embedding_status', 'source_contents', ['embedding_status'])

    # Create source_content_chunks table with pgvector Vector type
    op.create_table(
        'source_content_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_content_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(VECTOR_DIMENSION), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['source_content_id'],
            ['source_contents.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for source_content_chunks
    op.create_index('ix_source_content_chunks_source_content_id', 'source_content_chunks', ['source_content_id'])
    op.create_index('ix_source_content_chunks_content_chunk', 'source_content_chunks', ['source_content_id', 'chunk_index'])

    # Create HNSW index for approximate nearest neighbor search on embeddings
    # Using cosine distance for normalized embeddings (BGE-M3 produces normalized vectors)
    op.execute(text('''
        CREATE INDEX ix_source_content_chunks_embedding_hnsw
        ON source_content_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    '''))


def downgrade() -> None:
    """Remove source_contents and source_content_chunks tables."""
    # Drop the HNSW index first
    op.execute(text('DROP INDEX IF EXISTS ix_source_content_chunks_embedding_hnsw'))

    # Drop source_content_chunks indexes
    op.drop_index('ix_source_content_chunks_content_chunk', table_name='source_content_chunks')
    op.drop_index('ix_source_content_chunks_source_content_id', table_name='source_content_chunks')

    # Drop source_content_chunks table
    op.drop_table('source_content_chunks')

    # Drop source_contents indexes
    op.drop_index('ix_source_contents_embedding_status', table_name='source_contents')
    op.drop_index('ix_source_contents_content_hash', table_name='source_contents')

    # Drop source_contents table
    op.drop_table('source_contents')
