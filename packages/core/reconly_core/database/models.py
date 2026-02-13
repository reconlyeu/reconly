"""SQLAlchemy models for digest database - OSS version.

Entity Model Overview:
─────────────────────
User              → Optional for single-user OSS, required for multi-user
Source            → Content sources (RSS, YouTube, websites, etc.)
Feed              → Groups sources with schedule and output configuration
FeedSource        → Many-to-many junction: Feed ↔ Source
PromptTemplate    → LLM prompt configuration for summarization
ReportTemplate    → Output rendering templates
FeedRun           → Execution history for feeds
Digest            → Processed content output (existing)
LLMUsageLog       → Per-request LLM usage tracking for billing
ChatConversation  → LLM chat conversation metadata
ChatMessage       → Individual messages in chat conversations

All entities have nullable user_id for single-user mode.
Enterprise extends with scope/org via migrations.

Requires PostgreSQL with pgvector extension for vector storage.
"""
from datetime import datetime
from typing import Literal

from jinja2 import Template
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean, JSON,
    ForeignKey, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship, backref
from pgvector.sqlalchemy import Vector

# Template origin types:
# - 'builtin': Shipped with Reconly, seeded on first run
# - 'user': Created by the user
# - 'imported': Imported from a marketplace bundle
TemplateOrigin = Literal["builtin", "user", "imported"]

# Embedding status types for RAG knowledge system:
# - None: Never attempted (legacy digests)
# - 'pending': Embedding in progress
# - 'completed': Successfully embedded
# - 'failed': Embedding failed
EmbeddingStatus = Literal["pending", "completed", "failed"]


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# APP SETTING
# ═══════════════════════════════════════════════════════════════════════════════

class AppSetting(Base):
    """
    Application settings stored in database for runtime configuration.

    Implements a key-value store with JSON-encoded values for type preservation.
    Used by SettingsService with priority chain: DB > env > default.
    """
    __tablename__ = 'app_settings'

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded for type preservation
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AppSetting(key='{self.key}')>"

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# USER
# ═══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """
    User account - minimal for OSS single-user mode.

    In OSS mode, this table may have 0-1 rows (single user or anonymous).
    Enterprise extends with organization_id, role via migrations.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sources = relationship('Source', back_populates='user', cascade='all, delete-orphan')
    feeds = relationship('Feed', back_populates='user', cascade='all, delete-orphan')
    prompt_templates = relationship('PromptTemplate', back_populates='user', cascade='all, delete-orphan')
    report_templates = relationship('ReportTemplate', back_populates='user', cascade='all, delete-orphan')
    digests = relationship('Digest', back_populates='user')
    llm_usage_logs = relationship('LLMUsageLog', back_populates='user')
    agent_runs = relationship('AgentRun', back_populates='user')
    chat_conversations = relationship('ChatConversation', back_populates='user', cascade='all, delete-orphan')
    connections = relationship('Connection', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE
# ═══════════════════════════════════════════════════════════════════════════════

class Source(Base):
    """
    Content source definition - replaces YAML-based SourceConfig.

    Supports: RSS feeds, YouTube channels, websites, blogs, IMAP email, etc.
    Each source can specify default LLM settings that can be overridden at feed level.
    """
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Core fields
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False, index=True)  # rss, youtube, website, blog, imap, agent
    url = Column(String(2048), nullable=False)

    # Type-specific configuration (JSON for flexibility)
    config = Column(JSON, nullable=True)  # e.g., {"fetch_full_content": true, "max_items": 10}

    enabled = Column(Boolean, default=True, nullable=False)

    # Connection reference for sources using reusable credentials
    # When set, source uses credentials from the linked Connection
    # When NULL, source uses its own embedded config or no auth
    connection_id = Column(Integer, ForeignKey('connections.id', ondelete='SET NULL'), nullable=True, index=True)

    # Authentication status for sources requiring credentials (IMAP, etc.)
    # - NULL: No authentication required (RSS, websites)
    # - 'active': Authenticated and working
    # - 'pending_oauth': OAuth flow not completed
    # - 'auth_failed': Authentication failed, needs re-authentication
    auth_status = Column(String(20), nullable=True, index=True)

    # Default LLM settings (can be overridden at feed level)
    default_language = Column(String(10), nullable=True)  # de, en, etc.
    default_provider = Column(String(100), nullable=True)  # ollama, anthropic, etc.
    default_model = Column(String(100), nullable=True)  # specific model name

    # Content filtering (filter fetched items before summarization)
    include_keywords = Column(JSON, nullable=True)  # ["keyword1", "keyword2"] - item must match at least one
    exclude_keywords = Column(JSON, nullable=True)  # ["spam", "ad"] - item must NOT match any
    filter_mode = Column(String(20), nullable=True, default="both")  # title_only, content, both
    use_regex = Column(Boolean, default=False, nullable=False)  # Interpret keywords as regex patterns

    # Health tracking for circuit breaker pattern
    # - consecutive_failures: Number of consecutive fetch failures
    # - last_failure_at: When the most recent failure occurred
    # - last_success_at: When the most recent success occurred
    # - health_status: Current health state (healthy, degraded, unhealthy)
    # - circuit_open_until: When circuit will attempt recovery (if open)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_failure_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    health_status = Column(String(20), default='healthy', nullable=False, index=True)
    circuit_open_until = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='sources')
    feed_sources = relationship('FeedSource', back_populates='source', cascade='all, delete-orphan')
    oauth_credentials = relationship('OAuthCredential', back_populates='source', cascade='all, delete-orphan', uselist=False)
    connection = relationship('Connection', back_populates='sources')

    # Indexes
    __table_args__ = (
        Index('ix_sources_user_type', 'user_id', 'type'),
    )

    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self):
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'type': self.type,
            'url': self.url,
            'config': self.config,
            'enabled': self.enabled,
            'connection_id': self.connection_id,
            'auth_status': self.auth_status,
            'default_language': self.default_language,
            'default_provider': self.default_provider,
            'default_model': self.default_model,
            'include_keywords': self.include_keywords,
            'exclude_keywords': self.exclude_keywords,
            'filter_mode': self.filter_mode,
            'use_regex': self.use_regex,
            # Health tracking fields
            'consecutive_failures': self.consecutive_failures,
            'last_failure_at': self.last_failure_at.isoformat() if self.last_failure_at else None,
            'last_success_at': self.last_success_at.isoformat() if self.last_success_at else None,
            'health_status': self.health_status,
            'circuit_open_until': self.circuit_open_until.isoformat() if self.circuit_open_until else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        # Add OAuth credential ID if source has one (uselist=False so it's a single object)
        if hasattr(self, 'oauth_credentials') and self.oauth_credentials:
            result['oauth_credential_id'] = self.oauth_credentials.id
        else:
            result['oauth_credential_id'] = None
        return result

    @property
    def is_circuit_open(self) -> bool:
        """Check if the circuit breaker is currently open for this source.

        Returns:
            True if circuit is open and recovery time hasn't passed yet.
        """
        if self.circuit_open_until is None:
            return False
        return datetime.utcnow() < self.circuit_open_until

    def update_health_success(self) -> None:
        """Update health status after a successful fetch.

        Resets consecutive failures, updates last_success_at, sets health to 'healthy',
        and clears circuit_open_until. This method is safe to call on newly created
        Source objects that haven't been persisted yet.
        """
        self.consecutive_failures = 0
        self.last_success_at = datetime.utcnow()
        self.health_status = 'healthy'
        self.circuit_open_until = None

    def update_health_failure(self, recovery_timeout: int = 300) -> None:
        """Update health status after a failed fetch.

        Increments consecutive failures, updates last_failure_at, and transitions
        health status based on failure count:
        - 0-2 failures: healthy
        - 3-4 failures: degraded
        - 5+ failures: unhealthy (circuit opens)

        Args:
            recovery_timeout: Seconds until circuit breaker attempts recovery (default 300)
        """
        from datetime import timedelta

        self.consecutive_failures = (self.consecutive_failures or 0) + 1
        self.last_failure_at = datetime.utcnow()

        # Determine health status based on consecutive failures
        if self.consecutive_failures >= 5:
            self.health_status = 'unhealthy'
            self.circuit_open_until = datetime.utcnow() + timedelta(seconds=recovery_timeout)
        elif self.consecutive_failures >= 3:
            self.health_status = 'degraded'
            self.circuit_open_until = None
        else:
            self.health_status = 'healthy'
            self.circuit_open_until = None


# ═══════════════════════════════════════════════════════════════════════════════
# FEED
# ═══════════════════════════════════════════════════════════════════════════════

class Feed(Base):
    """
    Feed - groups sources with schedule, templates, and output configuration.

    A feed defines:
    - Which sources to aggregate (via FeedSource junction)
    - When to run (schedule_cron)
    - How to summarize (prompt_template)
    - How to format output (report_template)
    - Where to send results (output_config)
    - How to consolidate digests (digest_mode)
    """
    __tablename__ = 'feeds'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Core fields
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Digest consolidation mode
    # - 'individual': One digest per item (default, current behavior)
    # - 'per_source': One digest per source (consolidate items within each source)
    # - 'all_sources': One digest per feed run (consolidate ALL items across ALL sources)
    digest_mode = Column(String(20), default='individual', nullable=False)

    # Schedule configuration
    schedule_cron = Column(String(100), nullable=True)  # e.g., "0 8 * * *" for daily 8 AM
    schedule_enabled = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    # Template references
    prompt_template_id = Column(Integer, ForeignKey('prompt_templates.id', ondelete='SET NULL'), nullable=True)
    report_template_id = Column(Integer, ForeignKey('report_templates.id', ondelete='SET NULL'), nullable=True)

    # LLM override (takes precedence over template and source defaults)
    model_provider = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=True)

    # Output configuration (embedded JSON for flexibility)
    # Example: {"db": true, "email": {"enabled": true, "recipients": ["a@b.com"]},
    #           "obsidian": {"vault_path": "/path", "folder": "Digests"}}
    output_config = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='feeds')
    prompt_template = relationship('PromptTemplate', back_populates='feeds')
    report_template = relationship('ReportTemplate', back_populates='feeds')
    feed_sources = relationship('FeedSource', back_populates='feed', cascade='all, delete-orphan')
    feed_runs = relationship('FeedRun', back_populates='feed', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Feed(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'digest_mode': self.digest_mode,
            'schedule_cron': self.schedule_cron,
            'schedule_enabled': self.schedule_enabled,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
            'prompt_template_id': self.prompt_template_id,
            'report_template_id': self.report_template_id,
            'model_provider': self.model_provider,
            'model_name': self.model_name,
            'output_config': self.output_config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sources': [fs.to_dict() for fs in self.feed_sources] if self.feed_sources else [],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SOURCE (Junction Table)
# ═══════════════════════════════════════════════════════════════════════════════

class FeedSource(Base):
    """
    Many-to-many relationship between Feed and Source.

    Allows per-feed-source configuration like priority and enabled state.
    """
    __tablename__ = 'feed_sources'

    feed_id = Column(Integer, ForeignKey('feeds.id', ondelete='CASCADE'), primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.id', ondelete='CASCADE'), primary_key=True)

    # Per-feed-source settings
    enabled = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher = processed first

    # Relationships
    feed = relationship('Feed', back_populates='feed_sources')
    source = relationship('Source', back_populates='feed_sources')

    def __repr__(self):
        return f"<FeedSource(feed_id={self.feed_id}, source_id={self.source_id})>"

    def to_dict(self):
        return {
            'feed_id': self.feed_id,
            'source_id': self.source_id,
            'source_name': self.source.name if self.source else None,
            'source_type': self.source.type if self.source else None,
            'enabled': self.enabled,
            'priority': self.priority,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

class PromptTemplate(Base):
    """
    LLM prompt configuration for content summarization.

    Separates prompt engineering from report formatting.
    Supports variables: {title}, {content}, {source_type}, {target_length}
    """
    __tablename__ = 'prompt_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Core fields
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Prompt content
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)  # Template with {variables}

    # Default settings
    language = Column(String(10), default='de', nullable=False)
    target_length = Column(Integer, default=150, nullable=False)  # Target word count

    # Preferred model (optional)
    model_provider = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=True)

    # Template origin: 'builtin' (shipped), 'user' (created), 'imported' (marketplace)
    origin = Column(String(20), default='user', nullable=False)

    # Provenance tracking for imported templates (e.g., "sap-analyst-brief@1.0.0")
    imported_from_bundle = Column(String(100), nullable=True)

    # Is this template active/enabled?
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='prompt_templates')
    feeds = relationship('Feed', back_populates='prompt_template')

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'user_prompt_template': self.user_prompt_template,
            'language': self.language,
            'target_length': self.target_length,
            'model_provider': self.model_provider,
            'model_name': self.model_name,
            'origin': self.origin,
            'imported_from_bundle': self.imported_from_bundle,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_system(self) -> bool:
        """Backwards compatibility property - True if origin is 'builtin'."""
        return self.origin == 'builtin'

    def render_prompts(self, content_data: dict) -> dict:
        """
        Render the prompt templates with actual content using Jinja2.

        Args:
            content_data: Dict with keys: title, content, source_type

        Returns:
            Dict with 'system' and 'user' prompt strings
        """
        context = {
            'title': content_data.get('title', ''),
            'content': content_data.get('content', ''),
            'source_type': content_data.get('source_type', 'unknown'),
            'target_length': self.target_length,
        }
        user_prompt = Template(self.user_prompt_template).render(**context)
        return {
            'system': self.system_prompt,
            'user': user_prompt,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

class ReportTemplate(Base):
    """
    Report rendering template for formatting digest output.

    Supports Jinja2 templating for HTML/Markdown generation.
    Variables available: digests[], feed, run_info, generated_at
    """
    __tablename__ = 'report_templates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Core fields
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template content
    format = Column(String(20), default='markdown', nullable=False)  # markdown, html, text
    template_content = Column(Text, nullable=False)  # Jinja2 template

    # Template origin: 'builtin' (shipped), 'user' (created), 'imported' (marketplace)
    origin = Column(String(20), default='user', nullable=False)

    # Provenance tracking for imported templates (e.g., "sap-analyst-brief@1.0.0")
    imported_from_bundle = Column(String(100), nullable=True)

    # Is this template active/enabled?
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='report_templates')
    feeds = relationship('Feed', back_populates='report_template')

    def __repr__(self):
        return f"<ReportTemplate(id={self.id}, name='{self.name}', format='{self.format}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'format': self.format,
            'template_content': self.template_content,
            'origin': self.origin,
            'imported_from_bundle': self.imported_from_bundle,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def is_system(self) -> bool:
        """Backwards compatibility property - True if origin is 'builtin'."""
        return self.origin == 'builtin'


# ═══════════════════════════════════════════════════════════════════════════════
# FEED RUN
# ═══════════════════════════════════════════════════════════════════════════════

class FeedRun(Base):
    """
    Execution history for feed runs.

    Tracks each execution with status, timing, and aggregate metrics.
    Links to individual Digests created during the run.
    """
    __tablename__ = 'feed_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(Integer, ForeignKey('feeds.id', ondelete='CASCADE'), nullable=False, index=True)

    # Trigger info
    triggered_by = Column(String(50), nullable=False)  # schedule, manual, api
    triggered_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Status
    status = Column(String(20), default='pending', nullable=False, index=True)  # pending, running, completed, partial, failed

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Metrics
    sources_total = Column(Integer, default=0, nullable=False)
    sources_processed = Column(Integer, default=0, nullable=False)
    sources_failed = Column(Integer, default=0, nullable=False)
    items_processed = Column(Integer, default=0, nullable=False)  # Total content items (RSS entries, etc.)

    # Cost tracking (aggregated from LLMUsageLog)
    total_tokens_in = Column(Integer, default=0, nullable=False)
    total_tokens_out = Column(Integer, default=0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)

    # Error info
    error_log = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)  # Structured error data with source context

    # Tracing
    trace_id = Column(String(36), nullable=True, index=True)  # UUID for log correlation

    # LLM info (captured at run time)
    llm_provider = Column(String(100), nullable=True)  # anthropic, openai, ollama, etc.
    llm_model = Column(String(100), nullable=True)  # claude-3-5-sonnet, gpt-4, etc.

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    feed = relationship('Feed', back_populates='feed_runs')
    triggered_by_user = relationship('User', foreign_keys=[triggered_by_user_id])
    digests = relationship('Digest', back_populates='feed_run')
    llm_usage_logs = relationship('LLMUsageLog', back_populates='feed_run')

    # Indexes
    __table_args__ = (
        Index('ix_feed_runs_feed_status', 'feed_id', 'status'),
    )

    def __repr__(self):
        return f"<FeedRun(id={self.id}, feed_id={self.feed_id}, status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'feed_id': self.feed_id,
            'triggered_by': self.triggered_by,
            'triggered_by_user_id': self.triggered_by_user_id,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'sources_total': self.sources_total,
            'sources_processed': self.sources_processed,
            'sources_failed': self.sources_failed,
            'items_processed': self.items_processed,
            'total_tokens_in': self.total_tokens_in,
            'total_tokens_out': self.total_tokens_out,
            'total_cost': self.total_cost,
            'error_log': self.error_log,
            'error_details': self.error_details,
            'trace_id': self.trace_id,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# LLM USAGE LOG
# ═══════════════════════════════════════════════════════════════════════════════

class LLMUsageLog(Base):
    """
    Per-request LLM usage tracking for billing and analytics.

    Records each LLM API call with token counts and costs.
    Enables consumption-based billing in enterprise edition.
    """
    __tablename__ = 'llm_usage_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Context references
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    feed_run_id = Column(Integer, ForeignKey('feed_runs.id', ondelete='SET NULL'), nullable=True, index=True)
    digest_id = Column(Integer, ForeignKey('digests.id', ondelete='SET NULL'), nullable=True)

    # Provider/Model info
    provider = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False)

    # Usage metrics
    tokens_in = Column(Integer, default=0, nullable=False)
    tokens_out = Column(Integer, default=0, nullable=False)
    cost = Column(Float, default=0.0, nullable=False)

    # Request metadata
    request_type = Column(String(50), nullable=True)  # summarize, analyze, translate, etc.
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship('User', back_populates='llm_usage_logs')
    feed_run = relationship('FeedRun', back_populates='llm_usage_logs')
    digest = relationship('Digest', back_populates='llm_usage_logs')

    # Indexes
    __table_args__ = (
        Index('ix_llm_usage_user_provider', 'user_id', 'provider'),
        Index('ix_llm_usage_timestamp_provider', 'timestamp', 'provider'),
    )

    def __repr__(self):
        return f"<LLMUsageLog(id={self.id}, provider='{self.provider}', model='{self.model}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'feed_run_id': self.feed_run_id,
            'digest_id': self.digest_id,
            'provider': self.provider,
            'model': self.model,
            'tokens_in': self.tokens_in,
            'tokens_out': self.tokens_out,
            'cost': self.cost,
            'request_type': self.request_type,
            'latency_ms': self.latency_ms,
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DIGEST (existing, updated with feed_run_id)
# ═══════════════════════════════════════════════════════════════════════════════

class Digest(Base):
    """
    Main digest storage table - processed content output.

    Each Digest represents a summarized piece of content from a source.
    Links to the FeedRun that created it for execution tracking.

    For consolidated digests (per_source or all_sources mode):
    - consolidated_count: Number of items combined
    - source_id: NULL for all_sources mode, populated for per_source mode
    - source_items: Junction records tracking which items went into this digest
    """
    __tablename__ = 'digests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, unique=True, index=True)
    title = Column(String(512), index=True)  # Indexed for search performance
    content = Column(Text)
    summary = Column(Text)  # Indexed via migration for search performance
    source_type = Column(String(50), index=True)  # website, youtube, rss
    feed_url = Column(String(2048))  # For RSS: URL of the feed
    feed_title = Column(String(512))  # For RSS: Title of the feed
    image_url = Column(String(2048))  # Preview/thumbnail image URL
    author = Column(String(256))
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    provider = Column(String(100))  # huggingface-glm-4, anthropic, etc.
    language = Column(String(10))  # de, en
    estimated_cost = Column(Float, default=0.0)

    # Consolidation tracking
    # 1 for individual digests, >1 for consolidated digests
    consolidated_count = Column(Integer, default=1, nullable=False)

    # Embedding status for RAG knowledge system
    # - NULL: Never attempted (legacy digests)
    # - 'pending': Embedding in progress
    # - 'completed': Successfully embedded
    # - 'failed': Embedding failed (error stored in embedding_error)
    embedding_status = Column(String(20), nullable=True, index=True)
    embedding_error = Column(Text, nullable=True)  # Error message if embedding failed

    # Foreign keys
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    feed_run_id = Column(Integer, ForeignKey('feed_runs.id', ondelete='SET NULL'), nullable=True, index=True)
    source_id = Column(Integer, ForeignKey('sources.id', ondelete='SET NULL'), nullable=True, index=True)

    # Relationships
    tags = relationship('DigestTag', back_populates='digest', cascade='all, delete-orphan')
    user = relationship('User', back_populates='digests')
    feed_run = relationship('FeedRun', back_populates='digests')
    source = relationship('Source')
    llm_usage_logs = relationship('LLMUsageLog', back_populates='digest')
    source_items = relationship('DigestSourceItem', back_populates='digest', cascade='all, delete-orphan')

    # RAG Knowledge System relationships
    chunks = relationship('DigestChunk', back_populates='digest', cascade='all, delete-orphan',
                          order_by='DigestChunk.chunk_index')
    outgoing_relationships = relationship('DigestRelationship',
                                           foreign_keys='DigestRelationship.source_digest_id',
                                           back_populates='source_digest',
                                           cascade='all, delete-orphan')
    incoming_relationships = relationship('DigestRelationship',
                                           foreign_keys='DigestRelationship.target_digest_id',
                                           back_populates='target_digest',
                                           cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Digest(id={self.id}, title='{self.title[:50] if self.title else ''}...', source={self.source_type})>"

    def to_dict(self):
        """Convert to dictionary."""
        # Calculate total tokens from LLM usage logs
        tokens_in = 0
        tokens_out = 0
        if self.llm_usage_logs:
            for log in self.llm_usage_logs:
                tokens_in += log.tokens_in or 0
                tokens_out += log.tokens_out or 0

        result = {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'source_type': self.source_type,
            'feed_url': self.feed_url,
            'feed_title': self.feed_title,
            'image_url': self.image_url,
            'author': self.author,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'provider': self.provider,
            'language': self.language,
            'estimated_cost': self.estimated_cost,
            'consolidated_count': self.consolidated_count,
            'embedding_status': self.embedding_status,
            'embedding_error': self.embedding_error,
            'user_id': self.user_id,
            'feed_run_id': self.feed_run_id,
            'source_id': self.source_id,
            'tags': [tag.tag.name for tag in self.tags],
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
        }
        # Include source_items for consolidated digests
        if self.source_items:
            result['source_items'] = [item.to_dict() for item in self.source_items]
        return result


class Tag(Base):
    """Tags for categorizing digests."""

    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)

    # Relationship to digests
    digests = relationship('DigestTag', back_populates='tag', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}')>"


class DigestTag(Base):
    """Many-to-many relationship between digests and tags."""

    __tablename__ = 'digest_tags'

    digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)

    # Relationships
    digest = relationship('Digest', back_populates='tags')
    tag = relationship('Tag', back_populates='digests')

    def __repr__(self):
        return f"<DigestTag(digest_id={self.digest_id}, tag_id={self.tag_id})>"


# ═══════════════════════════════════════════════════════════════════════════════
# DIGEST SOURCE ITEM (Junction Table for Consolidated Digests)
# ═══════════════════════════════════════════════════════════════════════════════

class DigestSourceItem(Base):
    """
    Tracks which source items went into a consolidated digest.

    For consolidated digests (per_source or all_sources mode), this junction table
    preserves provenance: "This briefing synthesized 3 items from Bloomberg,
    2 from Reuters, 1 from SEC."
    """
    __tablename__ = 'digest_source_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey('sources.id', ondelete='SET NULL'), nullable=True, index=True)

    # Original item metadata
    item_url = Column(String(2048), nullable=False)
    item_title = Column(String(512), nullable=True)
    item_published_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    digest = relationship('Digest', back_populates='source_items')
    source = relationship('Source')
    source_content = relationship('SourceContent', back_populates='digest_source_item', uselist=False, cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        Index('ix_digest_source_items_digest_source', 'digest_id', 'source_id'),
    )

    def __repr__(self):
        return f"<DigestSourceItem(digest_id={self.digest_id}, source_id={self.source_id}, item_url='{self.item_url[:50]}...')>"

    def to_dict(self):
        return {
            'id': self.id,
            'digest_id': self.digest_id,
            'source_id': self.source_id,
            'source_name': self.source.name if self.source else None,
            'item_url': self.item_url,
            'item_title': self.item_title,
            'item_published_at': self.item_published_at.isoformat() if self.item_published_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE CONTENT (RAG Knowledge System - Original Source Content)
# ═══════════════════════════════════════════════════════════════════════════════


class SourceContent(Base):
    """
    Stores the original fetched content from source items for RAG embedding.

    Instead of embedding processed digest summaries (which contain template-based
    formatting noise), we embed the raw source content for cleaner semantic search.
    This provides better retrieval quality by avoiding template-induced similarity.

    One-to-one relationship with DigestSourceItem - each source item that gets
    processed can have its original content stored here for embedding.
    """
    __tablename__ = 'source_contents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_source_item_id = Column(
        Integer,
        ForeignKey('digest_source_items.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True
    )

    # Original content from the source
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256 for deduplication
    content_length = Column(Integer, nullable=False)  # Character count

    # Fetch metadata
    fetched_at = Column(DateTime, nullable=False)

    # Embedding status tracking (same pattern as Digest.embedding_status)
    # - NULL: Never attempted
    # - 'pending': Embedding in progress
    # - 'completed': Successfully embedded
    # - 'failed': Embedding failed (error stored in embedding_error)
    embedding_status = Column(String(20), nullable=True, index=True)
    embedding_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    digest_source_item = relationship('DigestSourceItem', back_populates='source_content')
    chunks = relationship(
        'SourceContentChunk',
        back_populates='source_content',
        cascade='all, delete-orphan',
        order_by='SourceContentChunk.chunk_index'
    )

    def __repr__(self):
        return f"<SourceContent(id={self.id}, digest_source_item_id={self.digest_source_item_id}, status='{self.embedding_status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'digest_source_item_id': self.digest_source_item_id,
            'content_hash': self.content_hash,
            'content_length': self.content_length,
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
            'embedding_status': self.embedding_status,
            'embedding_error': self.embedding_error,
            'chunk_count': len(self.chunks) if self.chunks else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE CONTENT CHUNK (RAG Knowledge System - Chunked Source Content)
# ═══════════════════════════════════════════════════════════════════════════════

# Vector dimension matching BGE-M3 default
VECTOR_DIMENSION = 1024


class SourceContentChunk(Base):
    """
    Stores embedded text chunks from original source content for RAG retrieval.

    Similar to DigestChunk but stores embeddings of the original source content
    rather than the processed digest summary. This provides cleaner semantic
    search results without template-based formatting noise.

    Uses pgvector's Vector type for efficient vector storage and
    similarity search in PostgreSQL.
    """
    __tablename__ = 'source_content_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_content_id = Column(
        Integer,
        ForeignKey('source_contents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    chunk_index = Column(Integer, nullable=False)  # Order within source content (0-indexed)
    text = Column(Text, nullable=False)

    # Vector embedding using pgvector for efficient similarity search
    embedding = Column(Vector(VECTOR_DIMENSION), nullable=True)

    token_count = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=False)  # Character offset in original content
    end_char = Column(Integer, nullable=False)
    extra_data = Column(JSON, nullable=True)  # {"heading": "...", "section": "..."}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    source_content = relationship('SourceContent', back_populates='chunks')

    # Indexes - composite index for efficient chunk lookup, HNSW index for vector search
    __table_args__ = (
        Index('ix_source_content_chunks_content_chunk', 'source_content_id', 'chunk_index'),
    )

    def __repr__(self):
        return f"<SourceContentChunk(id={self.id}, source_content_id={self.source_content_id}, chunk_index={self.chunk_index})>"

    def to_dict(self):
        return {
            'id': self.id,
            'source_content_id': self.source_content_id,
            'chunk_index': self.chunk_index,
            'text': self.text,
            'token_count': self.token_count,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'extra_data': self.extra_data,
            'has_embedding': self.embedding is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DIGEST CHUNK (RAG Knowledge System)
# ═══════════════════════════════════════════════════════════════════════════════


class DigestChunk(Base):
    """
    Stores embedded text chunks from digests for RAG knowledge retrieval.

    Each digest can be split into multiple chunks for semantic search.
    Chunks are created when a digest is processed and store both the
    text content and its vector embedding for similarity search.

    Uses pgvector's Vector type for efficient vector storage and
    similarity search in PostgreSQL.
    """
    __tablename__ = 'digest_chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Order within digest (0-indexed)
    text = Column(Text, nullable=False)

    # Vector embedding using pgvector for efficient similarity search
    embedding = Column(Vector(VECTOR_DIMENSION), nullable=True)

    token_count = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=False)  # Character offset in original text
    end_char = Column(Integer, nullable=False)
    extra_data = Column(JSON, nullable=True)  # {"heading": "...", "section": "..."}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    digest = relationship('Digest', back_populates='chunks')

    # Indexes
    __table_args__ = (
        Index('ix_digest_chunks_digest_chunk', 'digest_id', 'chunk_index'),
    )

    def __repr__(self):
        return f"<DigestChunk(id={self.id}, digest_id={self.digest_id}, chunk_index={self.chunk_index})>"

    def to_dict(self):
        return {
            'id': self.id,
            'digest_id': self.digest_id,
            'chunk_index': self.chunk_index,
            'text': self.text,
            'token_count': self.token_count,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'extra_data': self.extra_data,
            'has_embedding': self.embedding is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DIGEST RELATIONSHIP (RAG Knowledge System)
# ═══════════════════════════════════════════════════════════════════════════════

class DigestRelationship(Base):
    """
    Stores relationships between digests for knowledge graph navigation.

    Relationships can be:
    - 'semantic': Digests with similar embeddings (cosine similarity > threshold)
    - 'tag': Digests sharing one or more tags
    - 'source': Digests from the same source/feed

    Relationships are directional (source -> target) but typically created
    bidirectionally for semantic relationships.
    """
    __tablename__ = 'digest_relationships'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), nullable=False, index=True)
    target_digest_id = Column(Integer, ForeignKey('digests.id', ondelete='CASCADE'), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True)  # semantic, tag, source
    score = Column(Float, nullable=False, index=True)  # 0.0 to 1.0, higher = stronger relationship
    extra_data = Column(JSON, nullable=True)  # Additional context, e.g., shared tags

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    source_digest = relationship('Digest', foreign_keys=[source_digest_id],
                                  back_populates='outgoing_relationships')
    target_digest = relationship('Digest', foreign_keys=[target_digest_id],
                                  back_populates='incoming_relationships')

    # Indexes
    __table_args__ = (
        Index('ix_digest_relationships_source_type', 'source_digest_id', 'relationship_type'),
        Index('ix_digest_relationships_type_score', 'relationship_type', 'score'),
    )

    def __repr__(self):
        return f"<DigestRelationship(source={self.source_digest_id}, target={self.target_digest_id}, type='{self.relationship_type}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'source_digest_id': self.source_digest_id,
            'target_digest_id': self.target_digest_id,
            'relationship_type': self.relationship_type,
            'score': self.score,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH CREDENTIAL (Email OAuth2 Token Storage)
# ═══════════════════════════════════════════════════════════════════════════════


class OAuthCredential(Base):
    """
    Stores encrypted OAuth2 credentials for email providers.

    Used by GmailProvider and OutlookProvider to store access and refresh tokens
    securely. Tokens are encrypted using Fernet symmetric encryption with the
    SECRET_KEY from environment.

    Never expose tokens in API responses or logs.
    """
    __tablename__ = 'oauth_credentials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey('sources.id', ondelete='CASCADE'), nullable=False, index=True, unique=True)
    provider = Column(String(50), nullable=False)  # gmail, outlook

    # Encrypted tokens - use Fernet encryption via crypto module
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)

    # Token metadata
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(JSON, nullable=True)  # List of OAuth scopes

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship('Source', back_populates='oauth_credentials')

    def __repr__(self):
        return f"<OAuthCredential(id={self.id}, source_id={self.source_id}, provider='{self.provider}')>"

    def to_dict(self):
        """Convert to dictionary format, EXCLUDING sensitive token data."""
        return {
            'id': self.id,
            'source_id': self.source_id,
            'provider': self.provider,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'scopes': self.scopes,
            'has_refresh_token': self.refresh_token_encrypted is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION (Reusable Credentials)
# ═══════════════════════════════════════════════════════════════════════════════


class Connection(Base):
    """
    Reusable credential storage for email and other authenticated sources.

    Connections separate credential management from per-source configuration,
    enabling credential reuse across multiple sources (e.g., same Gmail account
    for multiple email sources with different filters).

    Config is encrypted as a JSON blob using Fernet symmetric encryption via
    the crypto module. Never expose decrypted config in API responses or logs.

    Connection Types:
    - 'email_imap': IMAP credentials (host, port, username, password)
    - 'email_oauth': OAuth2 credentials (tokens, provider info)
    - 'http_basic': HTTP Basic Auth (username, password)
    - 'api_key': API key authentication (key, optional header name)

    Providers (for email types):
    - 'gmail': Google Gmail
    - 'outlook': Microsoft Outlook/Office 365
    - 'generic': Generic IMAP/SMTP server
    """
    __tablename__ = 'connections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Core fields
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False, index=True)  # email_imap, email_oauth, http_basic, api_key
    provider = Column(String(50), nullable=True)  # gmail, outlook, generic (for email types)

    # Encrypted configuration (JSON blob)
    # Contains type-specific credentials encrypted via reconly_core.email.crypto
    config_encrypted = Column(Text, nullable=False)

    # Health tracking (simple timestamps for display, no circuit breaker logic here)
    # Circuit breaker pattern is handled at the Source level
    last_check_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='connections')
    sources = relationship('Source', back_populates='connection')

    # Indexes
    __table_args__ = (
        Index('ix_connections_user_type', 'user_id', 'type'),
    )

    def __repr__(self):
        return f"<Connection(id={self.id}, name='{self.name}', type='{self.type}')>"

    def to_dict(self):
        """Convert to dictionary format, EXCLUDING encrypted config."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'type': self.type,
            'provider': self.provider,
            'last_check_at': self.last_check_at.isoformat() if self.last_check_at else None,
            'last_success_at': self.last_success_at.isoformat() if self.last_success_at else None,
            'last_failure_at': self.last_failure_at.isoformat() if self.last_failure_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'source_count': len(self.sources) if self.sources else 0,
        }

    def update_health_success(self) -> None:
        """Update health timestamps after a successful connection check."""
        now = datetime.utcnow()
        self.last_check_at = now
        self.last_success_at = now

    def update_health_failure(self) -> None:
        """Update health timestamps after a failed connection check."""
        now = datetime.utcnow()
        self.last_check_at = now
        self.last_failure_at = now


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT RUN
# ═══════════════════════════════════════════════════════════════════════════════


class AgentRun(Base):
    """
    Execution history for agent research runs.

    Tracks each agent execution with status, timing, and results.
    Similar to FeedRun but for autonomous agent research sessions.
    """
    __tablename__ = 'agent_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey('sources.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Research input
    prompt = Column(Text, nullable=False)

    # Status
    status = Column(String(20), default='pending', nullable=False, index=True)  # pending, running, completed, failed

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Agent execution metrics
    iterations = Column(Integer, default=0, nullable=False)
    tool_calls = Column(JSON, nullable=True)  # List of {tool, input, output}
    sources_consulted = Column(JSON, nullable=True)  # List of URLs fetched

    # Result
    result_title = Column(String(500), nullable=True)
    result_content = Column(Text, nullable=True)

    # Token tracking
    tokens_in = Column(Integer, default=0, nullable=False)
    tokens_out = Column(Integer, default=0, nullable=False)
    estimated_cost = Column(Float, default=0.0, nullable=False)

    # Error info
    error_log = Column(Text, nullable=True)

    # Tracing
    trace_id = Column(String(36), nullable=True, index=True)  # UUID for log correlation

    # Strategy-specific extra data (research_strategy, subtopics, etc.)
    extra_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    source = relationship('Source', backref=backref('agent_runs', passive_deletes=True))
    user = relationship('User', back_populates='agent_runs')

    __table_args__ = (
        Index('ix_agent_runs_source_status', 'source_id', 'status'),
    )

    def __repr__(self):
        return f"<AgentRun(id={self.id}, source_id={self.source_id}, status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'user_id': self.user_id,
            'prompt': self.prompt,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'iterations': self.iterations,
            'tool_calls': self.tool_calls,
            'sources_consulted': self.sources_consulted,
            'result_title': self.result_title,
            'result_content': self.result_content,
            'tokens_in': self.tokens_in,
            'tokens_out': self.tokens_out,
            'estimated_cost': self.estimated_cost,
            'error_log': self.error_log,
            'trace_id': self.trace_id,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT CONVERSATION (LLM Chat Interface)
# ═══════════════════════════════════════════════════════════════════════════════

class ChatConversation(Base):
    """
    Stores chat conversation metadata for the LLM chat interface.

    Each conversation tracks:
    - Optional user association (nullable for single-user OSS mode)
    - Conversation title (auto-generated or user-defined)
    - Model configuration used for the conversation
    - Timestamps for ordering and display
    """
    __tablename__ = 'chat_conversations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    # Conversation metadata
    title = Column(String(255), nullable=False)
    model_provider = Column(String(50), nullable=True)  # ollama, anthropic, openai, etc.
    model_name = Column(String(100), nullable=True)  # llama3.2, claude-3-5-sonnet, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship('User', back_populates='chat_conversations')
    messages = relationship('ChatMessage', back_populates='conversation', cascade='all, delete-orphan',
                            order_by='ChatMessage.created_at')

    # Indexes
    __table_args__ = (
        Index('ix_chat_conversations_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<ChatConversation(id={self.id}, title='{self.title[:30] if self.title else ''}...')>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'model_provider': self.model_provider,
            'model_name': self.model_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': len(self.messages) if self.messages else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT MESSAGE (LLM Chat Interface)
# ═══════════════════════════════════════════════════════════════════════════════


class ChatMessage(Base):
    """
    Stores individual chat messages within a conversation.

    Supports multiple message types:
    - 'user': User input messages
    - 'assistant': LLM response messages (may include tool_calls)
    - 'tool_call': When assistant requests tool execution
    - 'tool_result': Results from tool execution (references tool_call_id)

    For tool calling:
    - tool_calls: JSONB array of tool call requests from assistant
    - tool_call_id: References which tool call this result is for
    """
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('chat_conversations.id', ondelete='CASCADE'),
                             nullable=False, index=True)

    # Message content
    role = Column(String(20), nullable=False, index=True)  # user, assistant, tool_call, tool_result
    content = Column(Text, nullable=True)  # Nullable for tool_call messages that only have tool_calls

    # Tool calling support
    # tool_calls: Array of tool call objects when assistant wants to call tools
    # Format: [{"id": "call_123", "type": "function", "function": {"name": "...", "arguments": "..."}}]
    tool_calls = Column(JSON, nullable=True)
    # tool_call_id: For tool_result messages, references the tool call this is responding to
    tool_call_id = Column(String(100), nullable=True)

    # Token usage tracking (populated for assistant messages)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship('ChatConversation', back_populates='messages')

    # Indexes
    __table_args__ = (
        Index('ix_chat_messages_conversation_created', 'conversation_id', 'created_at'),
    )

    def __repr__(self):
        content_preview = self.content[:30] if self.content else '(no content)'
        return f"<ChatMessage(id={self.id}, role='{self.role}', content='{content_preview}...')>"

    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'tool_calls': self.tool_calls,
            'tool_call_id': self.tool_call_id,
            'tokens_in': self.tokens_in,
            'tokens_out': self.tokens_out,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
