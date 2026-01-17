"""Add chat_conversations and chat_messages tables for LLM chat interface.

This migration creates the tables needed for the LLM chat feature:
- chat_conversations: Stores conversation metadata and model configuration
- chat_messages: Stores individual messages with support for tool calling

Revision ID: 020
Revises: 019
Create Date: 2026-01-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '020'
down_revision: Union[str, None] = '019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chat_conversations and chat_messages tables with indexes."""
    # Create chat_conversations table
    op.create_table(
        'chat_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('model_provider', sa.String(length=50), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Create composite index for common query pattern (user's conversations by date)
    op.create_index('ix_chat_conversations_user_created', 'chat_conversations', ['user_id', 'created_at'])

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_call_id', sa.String(length=100), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Create composite index for common query pattern (messages in a conversation by date)
    op.create_index('ix_chat_messages_conversation_created', 'chat_messages', ['conversation_id', 'created_at'])


def downgrade() -> None:
    """Drop chat_messages and chat_conversations tables."""
    # Drop chat_messages table and index
    op.drop_index('ix_chat_messages_conversation_created', table_name='chat_messages')
    op.drop_table('chat_messages')

    # Drop chat_conversations table and index
    op.drop_index('ix_chat_conversations_user_created', table_name='chat_conversations')
    op.drop_table('chat_conversations')
