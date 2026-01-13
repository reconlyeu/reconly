"""Add pgvector extension and digest_chunks table for RAG system.

Creates the digest_chunks table to store embedded text chunks from digests.
Each digest can be split into multiple chunks for semantic search.

The pgvector extension must be installed in the database before running this
migration. For PostgreSQL, use: CREATE EXTENSION IF NOT EXISTS vector;

Requires PostgreSQL with pgvector extension.

Revision ID: 010
Revises: 009
Create Date: 2026-01-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vector dimension matching BGE-M3 default
VECTOR_DIMENSION = 1024


def upgrade() -> None:
    """Create digest_chunks table with vector embedding support."""
    # Get the current connection and dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    # Require PostgreSQL
    if dialect_name != 'postgresql':
        raise RuntimeError(
            f"PostgreSQL is required for RAG features, but using {dialect_name}. "
            "Please configure a PostgreSQL database with pgvector extension."
        )

    # Enable pgvector extension (safe to run multiple times)
    op.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))

    # Create digest_chunks table with pgvector Vector type
    op.create_table(
        'digest_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('digest_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(VECTOR_DIMENSION), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['digest_id'], ['digests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for efficient querying
    op.create_index('ix_digest_chunks_digest_id', 'digest_chunks', ['digest_id'])
    op.create_index('ix_digest_chunks_digest_chunk', 'digest_chunks', ['digest_id', 'chunk_index'])

    # Create HNSW index for approximate nearest neighbor search
    # HNSW is faster than IVFFlat for most use cases
    # Using cosine distance for normalized embeddings (BGE-M3 produces normalized vectors)
    op.execute(text('''
        CREATE INDEX ix_digest_chunks_embedding_hnsw
        ON digest_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    '''))


def downgrade() -> None:
    """Remove digest_chunks table."""
    # Drop the HNSW index first
    op.execute(text('DROP INDEX IF EXISTS ix_digest_chunks_embedding_hnsw'))

    # Drop other indexes
    op.drop_index('ix_digest_chunks_digest_chunk', table_name='digest_chunks')
    op.drop_index('ix_digest_chunks_digest_id', table_name='digest_chunks')

    # Drop the table
    op.drop_table('digest_chunks')

    # Note: We don't drop the pgvector extension as other tables might use it
