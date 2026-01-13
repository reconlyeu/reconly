"""Initial schema with all entities.

This migration creates the complete Reconly OSS schema including:
- User, Source, Feed, FeedSource
- PromptTemplate, ReportTemplate
- FeedRun, LLMUsageLog
- Digest, Tag, DigestTag

Revision ID: 001
Revises: None
Create Date: 2026-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""

    # ═══════════════════════════════════════════════════════════════════════════
    # USERS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SOURCES
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('default_language', sa.String(10), nullable=True),
        sa.Column('default_provider', sa.String(100), nullable=True),
        sa.Column('default_model', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sources_user_id', 'sources', ['user_id'])
    op.create_index('ix_sources_type', 'sources', ['type'])
    op.create_index('ix_sources_user_type', 'sources', ['user_id', 'type'])

    # ═══════════════════════════════════════════════════════════════════════════
    # PROMPT TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('user_prompt_template', sa.Text(), nullable=False),
        sa.Column('language', sa.String(10), nullable=False, default='de'),
        sa.Column('target_length', sa.Integer(), nullable=False, default=150),
        sa.Column('model_provider', sa.String(100), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prompt_templates_user_id', 'prompt_templates', ['user_id'])

    # ═══════════════════════════════════════════════════════════════════════════
    # REPORT TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'report_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('format', sa.String(20), nullable=False, default='markdown'),
        sa.Column('template_content', sa.Text(), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_report_templates_user_id', 'report_templates', ['user_id'])

    # ═══════════════════════════════════════════════════════════════════════════
    # FEEDS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'feeds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schedule_cron', sa.String(100), nullable=True),
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('prompt_template_id', sa.Integer(), nullable=True),
        sa.Column('report_template_id', sa.Integer(), nullable=True),
        sa.Column('model_provider', sa.String(100), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('output_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_template_id'], ['prompt_templates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['report_template_id'], ['report_templates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feeds_user_id', 'feeds', ['user_id'])

    # ═══════════════════════════════════════════════════════════════════════════
    # FEED SOURCES (Junction)
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'feed_sources',
        sa.Column('feed_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=0),
        sa.ForeignKeyConstraint(['feed_id'], ['feeds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feed_id', 'source_id'),
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # FEED RUNS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'feed_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('feed_id', sa.Integer(), nullable=False),
        sa.Column('triggered_by', sa.String(50), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('sources_total', sa.Integer(), nullable=False, default=0),
        sa.Column('sources_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('sources_failed', sa.Integer(), nullable=False, default=0),
        sa.Column('items_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('total_tokens_in', sa.Integer(), nullable=False, default=0),
        sa.Column('total_tokens_out', sa.Integer(), nullable=False, default=0),
        sa.Column('total_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['feed_id'], ['feeds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feed_runs_feed_id', 'feed_runs', ['feed_id'])
    op.create_index('ix_feed_runs_status', 'feed_runs', ['status'])
    op.create_index('ix_feed_runs_feed_status', 'feed_runs', ['feed_id', 'status'])

    # ═══════════════════════════════════════════════════════════════════════════
    # TAGS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_tags_name', 'tags', ['name'], unique=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # DIGESTS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'digests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('title', sa.String(512), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=True),
        sa.Column('feed_url', sa.String(2048), nullable=True),
        sa.Column('feed_title', sa.String(512), nullable=True),
        sa.Column('author', sa.String(256), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('provider', sa.String(100), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True, default=0.0),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('feed_run_id', sa.Integer(), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['feed_run_id'], ['feed_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_index('ix_digests_url', 'digests', ['url'], unique=True)
    op.create_index('ix_digests_source_type', 'digests', ['source_type'])
    op.create_index('ix_digests_created_at', 'digests', ['created_at'])
    op.create_index('ix_digests_user_id', 'digests', ['user_id'])
    op.create_index('ix_digests_feed_run_id', 'digests', ['feed_run_id'])
    op.create_index('ix_digests_source_id', 'digests', ['source_id'])

    # ═══════════════════════════════════════════════════════════════════════════
    # DIGEST TAGS (Junction)
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'digest_tags',
        sa.Column('digest_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['digest_id'], ['digests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('digest_id', 'tag_id'),
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # LLM USAGE LOGS
    # ═══════════════════════════════════════════════════════════════════════════
    op.create_table(
        'llm_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('feed_run_id', sa.Integer(), nullable=True),
        sa.Column('digest_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=False, default=0),
        sa.Column('tokens_out', sa.Integer(), nullable=False, default=0),
        sa.Column('cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('request_type', sa.String(50), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['feed_run_id'], ['feed_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['digest_id'], ['digests.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_usage_logs_user_id', 'llm_usage_logs', ['user_id'])
    op.create_index('ix_llm_usage_logs_feed_run_id', 'llm_usage_logs', ['feed_run_id'])
    op.create_index('ix_llm_usage_logs_provider', 'llm_usage_logs', ['provider'])
    op.create_index('ix_llm_usage_logs_timestamp', 'llm_usage_logs', ['timestamp'])
    op.create_index('ix_llm_usage_user_provider', 'llm_usage_logs', ['user_id', 'provider'])
    op.create_index('ix_llm_usage_timestamp_provider', 'llm_usage_logs', ['timestamp', 'provider'])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('llm_usage_logs')
    op.drop_table('digest_tags')
    op.drop_table('digests')
    op.drop_table('tags')
    op.drop_table('feed_runs')
    op.drop_table('feed_sources')
    op.drop_table('feeds')
    op.drop_table('report_templates')
    op.drop_table('prompt_templates')
    op.drop_table('sources')
    op.drop_table('users')
