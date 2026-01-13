"""Add digest_relationships table for tracking related content.

Creates the digest_relationships table to store relationships between digests
based on semantic similarity, shared tags, or common sources.

Relationship types:
- 'semantic': Digests with similar embeddings (cosine similarity > threshold)
- 'tag': Digests sharing one or more tags
- 'source': Digests from the same source/feed

Revision ID: 011
Revises: 010
Create Date: 2026-01-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create digest_relationships table."""
    op.create_table(
        'digest_relationships',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_digest_id', sa.Integer(), nullable=False),
        sa.Column('target_digest_id', sa.Integer(), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['source_digest_id'], ['digests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_digest_id'], ['digests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # Prevent duplicate relationships between the same pair
        sa.UniqueConstraint('source_digest_id', 'target_digest_id', 'relationship_type',
                           name='uq_digest_relationships_pair_type'),
    )

    # Create indexes for efficient querying
    op.create_index('ix_digest_relationships_source', 'digest_relationships', ['source_digest_id'])
    op.create_index('ix_digest_relationships_target', 'digest_relationships', ['target_digest_id'])
    op.create_index('ix_digest_relationships_type', 'digest_relationships', ['relationship_type'])
    op.create_index('ix_digest_relationships_score', 'digest_relationships', ['score'])

    # Composite index for finding all relationships of a digest by type
    op.create_index('ix_digest_relationships_source_type',
                    'digest_relationships', ['source_digest_id', 'relationship_type'])

    # Index for finding high-scoring relationships
    op.create_index('ix_digest_relationships_type_score',
                    'digest_relationships', ['relationship_type', 'score'])


def downgrade() -> None:
    """Remove digest_relationships table."""
    op.drop_index('ix_digest_relationships_type_score', table_name='digest_relationships')
    op.drop_index('ix_digest_relationships_source_type', table_name='digest_relationships')
    op.drop_index('ix_digest_relationships_score', table_name='digest_relationships')
    op.drop_index('ix_digest_relationships_type', table_name='digest_relationships')
    op.drop_index('ix_digest_relationships_target', table_name='digest_relationships')
    op.drop_index('ix_digest_relationships_source', table_name='digest_relationships')
    op.drop_table('digest_relationships')
