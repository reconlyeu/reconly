"""Tool implementations for LLM chat tool calling.

This module implements all the tools that can be called by the LLM during
chat conversations. Tools wrap internal services and provide a clean interface
for the LLM to interact with the Reconly system.

Tools are registered with the global tool_registry and can be called by the
ToolExecutor during chat sessions.

Example:
    >>> from reconly_core.chat.tools_impl import *  # Registers all tools
    >>> from reconly_core.chat import tool_registry
    >>> print(tool_registry.list_tool_names())
    ['list_feeds', 'create_feed', 'run_feed', ...]
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from reconly_core.chat.tools import ToolDefinition, tool_registry
from reconly_core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)


# =============================================================================
# FEED TOOLS
# =============================================================================


@tool_registry.register
def list_feeds_tool() -> ToolDefinition:
    """Register the list_feeds tool."""

    async def handler(
        db: "Session",
        enabled_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List all feeds with optional filtering.

        Args:
            db: Database session (injected by executor).
            enabled_only: If True, only return feeds with schedule_enabled=True.
            limit: Maximum number of feeds to return.

        Returns:
            List of feed dictionaries.
        """
        from sqlalchemy.orm import joinedload
        from reconly_core.database.models import Feed, FeedSource

        query = db.query(Feed).options(
            joinedload(Feed.feed_sources).joinedload(FeedSource.source)
        )

        if enabled_only:
            query = query.filter(Feed.schedule_enabled == True)  # noqa: E712

        feeds = query.order_by(Feed.created_at.desc()).limit(limit).all()

        return [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "digest_mode": f.digest_mode,
                "schedule_cron": f.schedule_cron,
                "schedule_enabled": f.schedule_enabled,
                "last_run_at": f.last_run_at.isoformat() if f.last_run_at else None,
                "next_run_at": f.next_run_at.isoformat() if f.next_run_at else None,
                "source_count": len(f.feed_sources) if f.feed_sources else 0,
            }
            for f in feeds
        ]

    return ToolDefinition(
        name="list_feeds",
        description=(
            "List all feeds in the system. Feeds are collections of sources that "
            "are processed together on a schedule. Use this to see what feeds exist "
            "and their current status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "description": "If true, only return feeds with scheduling enabled",
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of feeds to return (1-100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        handler=handler,
        category="feeds",
    )


@tool_registry.register
def create_feed_tool() -> ToolDefinition:
    """Register the create_feed tool with bundle support."""

    async def handler(
        db: "Session",
        name: str,
        description: str | None = None,
        source_ids: list[int] | None = None,
        schedule_cron: str | None = None,
        schedule_enabled: bool = True,
        digest_mode: str = "individual",
        # Bundle format support - creates sources inline
        sources: list[dict[str, Any]] | None = None,
        prompt_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new feed.

        Can create a feed with:
        1. Existing source IDs: Use source_ids parameter
        2. Inline sources (bundle format): Use sources parameter to create new sources

        Args:
            db: Database session (injected by executor).
            name: Feed name (required).
            description: Optional description.
            source_ids: List of existing source IDs to include.
            schedule_cron: Cron expression for scheduling (e.g., "0 8 * * *" for daily 8 AM).
            schedule_enabled: Whether to enable the schedule.
            digest_mode: How to consolidate digests ("individual", "per_source", "all_sources").
            sources: List of source definitions to create inline (bundle format).
            prompt_template: Optional prompt template to create and associate.

        Returns:
            Created feed dictionary with ID.
        """
        from croniter import croniter
        from reconly_core.database.models import Feed, FeedSource, Source, PromptTemplate

        # Validate digest_mode
        valid_modes = ("individual", "per_source", "all_sources")
        if digest_mode not in valid_modes:
            raise ValueError(f"Invalid digest_mode: {digest_mode}. Must be one of {valid_modes}")

        # Create inline sources if provided (bundle format)
        created_source_ids: list[int] = []
        if sources:
            for src_def in sources:
                src = Source(
                    name=src_def.get("name", "Unnamed Source"),
                    type=src_def.get("type", "rss"),
                    url=src_def["url"],
                    config=src_def.get("config"),
                    enabled=src_def.get("enabled", True),
                )
                db.add(src)
                db.flush()
                created_source_ids.append(src.id)

        # Combine with explicit source_ids
        all_source_ids = (source_ids or []) + created_source_ids

        # Create prompt template if provided
        prompt_template_id = None
        if prompt_template:
            pt = PromptTemplate(
                name=prompt_template.get("name", f"{name} Template"),
                description=prompt_template.get("description"),
                system_prompt=prompt_template.get("system_prompt", "You are a helpful assistant."),
                user_prompt_template=prompt_template.get(
                    "user_prompt_template",
                    "Summarize the following content:\n\nTitle: {title}\n\nContent: {content}"
                ),
                language=prompt_template.get("language", "en"),
                target_length=prompt_template.get("target_length", 150),
                origin="user",
            )
            db.add(pt)
            db.flush()
            prompt_template_id = pt.id

        # Create the feed
        db_feed = Feed(
            name=name,
            description=description,
            digest_mode=digest_mode,
            schedule_cron=schedule_cron,
            schedule_enabled=schedule_enabled,
            prompt_template_id=prompt_template_id,
        )

        # Calculate next_run_at if schedule is enabled
        if schedule_enabled and schedule_cron:
            try:
                cron = croniter(schedule_cron, datetime.utcnow())
                db_feed.next_run_at = cron.get_next(datetime)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid cron expression: {e}")

        db.add(db_feed)
        db.flush()

        # Add sources to feed
        for priority, source_id in enumerate(all_source_ids):
            feed_source = FeedSource(
                feed_id=db_feed.id,
                source_id=source_id,
                priority=priority,
                enabled=True,
            )
            db.add(feed_source)

        db.commit()
        db.refresh(db_feed)

        return {
            "id": db_feed.id,
            "name": db_feed.name,
            "description": db_feed.description,
            "digest_mode": db_feed.digest_mode,
            "schedule_cron": db_feed.schedule_cron,
            "schedule_enabled": db_feed.schedule_enabled,
            "next_run_at": db_feed.next_run_at.isoformat() if db_feed.next_run_at else None,
            "source_count": len(all_source_ids),
            "sources_created": len(created_source_ids),
            "prompt_template_id": prompt_template_id,
            "message": f"Feed '{name}' created successfully with {len(all_source_ids)} sources",
        }

    return ToolDefinition(
        name="create_feed",
        description=(
            "Create a new feed to aggregate and process content from multiple sources. "
            "A feed can be created with existing source IDs or by defining new sources inline. "
            "Feeds can be scheduled to run automatically using cron expressions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the feed (required)",
                    "minLength": 1,
                    "maxLength": 255,
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of the feed's purpose",
                },
                "source_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs of existing sources to include in the feed",
                },
                "schedule_cron": {
                    "type": "string",
                    "description": "Cron expression for scheduling (e.g., '0 8 * * *' for daily at 8 AM)",
                },
                "schedule_enabled": {
                    "type": "boolean",
                    "description": "Whether to enable automatic scheduling",
                    "default": True,
                },
                "digest_mode": {
                    "type": "string",
                    "enum": ["individual", "per_source", "all_sources"],
                    "description": (
                        "How to consolidate digests: 'individual' (one per item), "
                        "'per_source' (one per source), 'all_sources' (single briefing)"
                    ),
                    "default": "individual",
                },
                "sources": {
                    "type": "array",
                    "description": "Create new sources inline (bundle format)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["rss", "youtube", "website", "blog", "imap", "agent"]},
                            "url": {"type": "string"},
                            "config": {"type": "object"},
                        },
                        "required": ["url"],
                    },
                },
                "prompt_template": {
                    "type": "object",
                    "description": "Optional prompt template to create and associate with the feed",
                    "properties": {
                        "name": {"type": "string"},
                        "system_prompt": {"type": "string"},
                        "user_prompt_template": {"type": "string"},
                        "language": {"type": "string"},
                        "target_length": {"type": "integer"},
                    },
                },
            },
            "required": ["name"],
        },
        handler=handler,
        category="feeds",
    )


@tool_registry.register
def run_feed_tool() -> ToolDefinition:
    """Register the run_feed tool."""

    async def handler(
        db: "Session",
        feed_id: int,
    ) -> dict[str, Any]:
        """Run a feed immediately.

        Args:
            db: Database session (injected by executor).
            feed_id: ID of the feed to run.

        Returns:
            Status information about the started run.
        """
        import asyncio
        import os
        from reconly_core.database.models import Feed
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Verify feed exists
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed with ID {feed_id} not found")

        feed_name = feed.name

        # Get database URL from environment (same pattern as API tasks)
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        # Run the feed synchronously in a thread pool to avoid blocking
        # This mirrors how the API handles it via BackgroundTasks
        def run_feed_sync():
            service = FeedService(database_url=database_url)
            options = FeedRunOptions(
                triggered_by="chat",
                triggered_by_user_id=None,
                enable_fallback=True,
                show_progress=False,
            )
            return service.run_feed(feed_id, options)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_feed_sync)

        logger.info(f"Feed run {result.feed_run_id} completed for feed {feed_id} via chat")

        return {
            "feed_id": feed_id,
            "feed_name": feed_name,
            "run_id": result.feed_run_id,
            "status": result.status,
            "sources_processed": result.sources_processed,
            "sources_failed": result.sources_failed,
            "items_processed": result.items_processed,
            "message": f"Feed run completed for '{feed_name}'. Processed {result.items_processed} items.",
        }

    return ToolDefinition(
        name="run_feed",
        description=(
            "Trigger an immediate run of a feed to process its sources. "
            "This will fetch content from all sources and generate digests. "
            "The run happens in the background - check the run status later for results."
        ),
        parameters={
            "type": "object",
            "properties": {
                "feed_id": {
                    "type": "integer",
                    "description": "ID of the feed to run",
                },
            },
            "required": ["feed_id"],
        },
        handler=handler,
        requires_confirmation=True,  # Costs LLM tokens
        category="feeds",
    )


# =============================================================================
# SOURCE TOOLS
# =============================================================================


@tool_registry.register
def list_sources_tool() -> ToolDefinition:
    """Register the list_sources tool."""

    async def handler(
        db: "Session",
        source_type: str | None = None,
        enabled_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List available sources.

        Args:
            db: Database session (injected by executor).
            source_type: Filter by source type (rss, youtube, website, etc.).
            enabled_only: If True, only return enabled sources.
            limit: Maximum number of sources to return.

        Returns:
            List of source dictionaries.
        """
        from reconly_core.database.models import Source

        query = db.query(Source)

        if source_type:
            query = query.filter(Source.type == source_type)
        if enabled_only:
            query = query.filter(Source.enabled == True)  # noqa: E712

        sources = query.order_by(Source.created_at.desc()).limit(limit).all()

        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "url": s.url,
                "enabled": s.enabled,
                "health_status": s.health_status,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            }
            for s in sources
        ]

    return ToolDefinition(
        name="list_sources",
        description=(
            "List all available content sources. Sources are RSS feeds, YouTube channels, "
            "websites, or other content origins that can be added to feeds."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["rss", "youtube", "website", "blog", "imap", "agent"],
                    "description": "Filter by source type",
                },
                "enabled_only": {
                    "type": "boolean",
                    "description": "Only return enabled sources",
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sources to return (1-100)",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        handler=handler,
        category="sources",
    )


@tool_registry.register
def create_source_tool() -> ToolDefinition:
    """Register the create_source tool."""

    async def handler(
        db: "Session",
        name: str,
        url: str,
        source_type: str = "rss",
        enabled: bool = True,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new content source.

        Args:
            db: Database session (injected by executor).
            name: Name for the source.
            url: URL of the source (RSS feed URL, YouTube channel URL, etc.).
            source_type: Type of source (rss, youtube, website, blog).
            enabled: Whether the source is enabled.
            config: Optional configuration for the source.

        Returns:
            Created source dictionary with ID.
        """
        from reconly_core.database.models import Source

        # Validate source_type
        valid_types = ("rss", "youtube", "website", "blog", "imap", "agent")
        if source_type not in valid_types:
            raise ValueError(f"Invalid source_type: {source_type}. Must be one of {valid_types}")

        db_source = Source(
            name=name,
            type=source_type,
            url=url,
            enabled=enabled,
            config=config,
        )
        db.add(db_source)
        db.commit()
        db.refresh(db_source)

        return {
            "id": db_source.id,
            "name": db_source.name,
            "type": db_source.type,
            "url": db_source.url,
            "enabled": db_source.enabled,
            "message": f"Source '{name}' created successfully",
        }

    return ToolDefinition(
        name="create_source",
        description=(
            "Create a new content source. Sources can be RSS feeds, YouTube channels, "
            "websites, or other content origins. After creating a source, add it to a feed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the source (required)",
                    "minLength": 1,
                    "maxLength": 255,
                },
                "url": {
                    "type": "string",
                    "description": "URL of the source (RSS feed URL, YouTube channel URL, etc.)",
                    "maxLength": 2048,
                },
                "source_type": {
                    "type": "string",
                    "enum": ["rss", "youtube", "website", "blog", "imap", "agent"],
                    "description": "Type of content source",
                    "default": "rss",
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Whether the source is enabled",
                    "default": True,
                },
                "config": {
                    "type": "object",
                    "description": "Optional configuration (e.g., max_items, fetch_full_content)",
                },
            },
            "required": ["name", "url"],
        },
        handler=handler,
        category="sources",
    )


# =============================================================================
# DIGEST TOOLS
# =============================================================================


@tool_registry.register
def search_digests_tool() -> ToolDefinition:
    """Register the search_digests tool."""

    async def handler(
        db: "Session",
        query: str | None = None,
        feed_id: int | None = None,
        source_id: int | None = None,
        tags: list[str] | None = None,
        source_type: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search digests by keywords, tags, or filters.

        Args:
            db: Database session (injected by executor).
            query: Search query for full-text search in title/summary.
            feed_id: Filter by feed ID.
            source_id: Filter by source ID.
            tags: Filter by tag names.
            source_type: Filter by source type.
            limit: Maximum results to return.

        Returns:
            Search results with total count and digest list.
        """
        from sqlalchemy import text
        from sqlalchemy.orm import joinedload
        from reconly_core.database.models import Digest, DigestTag, Tag, FeedRun

        db_query = db.query(Digest).options(joinedload(Digest.llm_usage_logs))

        if feed_id:
            db_query = db_query.join(FeedRun).filter(FeedRun.feed_id == feed_id)

        if source_id:
            db_query = db_query.filter(Digest.source_id == source_id)

        if source_type:
            db_query = db_query.filter(Digest.source_type == source_type)

        if tags:
            db_query = db_query.join(DigestTag).join(Tag).filter(Tag.name.in_(tags))

        if query:
            # Use PostgreSQL full-text search with prefix matching
            words = query.strip().split()
            if words:
                safe_words = [w.replace("'", "''").replace("\\", "\\\\") for w in words if w]
                if len(safe_words) == 1:
                    tsquery_str = f"{safe_words[0]}:*"
                else:
                    tsquery_str = " & ".join(safe_words[:-1]) + f" & {safe_words[-1]}:*"

                fts_condition = text("""
                    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, ''))
                    @@ to_tsquery('english', :search_query)
                """)
                db_query = db_query.filter(fts_condition).params(search_query=tsquery_str)

        total = db_query.count()
        digests = db_query.order_by(Digest.created_at.desc()).limit(limit).all()

        return {
            "total": total,
            "returned": len(digests),
            "digests": [
                {
                    "id": d.id,
                    "title": d.title,
                    "summary": d.summary[:500] if d.summary and len(d.summary) > 500 else d.summary,
                    "url": d.url,
                    "source_type": d.source_type,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "tags": [t.tag.name for t in d.tags] if d.tags else [],
                }
                for d in digests
            ],
        }

    return ToolDefinition(
        name="search_digests",
        description=(
            "Search through processed content digests. Use this to find specific information "
            "in the knowledge base by keywords, tags, source type, or feed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for full-text search in title and summary",
                },
                "feed_id": {
                    "type": "integer",
                    "description": "Filter by feed ID",
                },
                "source_id": {
                    "type": "integer",
                    "description": "Filter by source ID",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tag names",
                },
                "source_type": {
                    "type": "string",
                    "enum": ["rss", "youtube", "website", "blog", "imap", "agent"],
                    "description": "Filter by source type",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (1-100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        handler=handler,
        category="digests",
    )


@tool_registry.register
def export_digests_tool() -> ToolDefinition:
    """Register the export_digests tool."""

    async def handler(
        db: "Session",
        format: str = "json",
        feed_id: int | None = None,
        source_id: int | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Export digests to a specified format.

        Args:
            db: Database session (injected by executor).
            format: Export format (json, csv).
            feed_id: Filter by feed ID.
            source_id: Filter by source ID.
            tag: Filter by tag name.
            limit: Maximum digests to export.

        Returns:
            Export information with content preview.
        """
        from reconly_core.database.models import Digest, DigestTag, Tag, FeedRun
        from reconly_core.exporters import get_exporter, list_exporters

        # Build query
        query = db.query(Digest)

        if feed_id:
            query = query.join(FeedRun).filter(FeedRun.feed_id == feed_id)

        if source_id:
            query = query.filter(Digest.source_id == source_id)

        if tag:
            query = query.join(DigestTag).join(Tag).filter(Tag.name == tag)

        digests = query.order_by(Digest.created_at.desc()).limit(limit).all()

        if not digests:
            return {
                "success": True,
                "format": format,
                "digest_count": 0,
                "message": "No digests found matching the criteria",
            }

        # Get exporter and export
        try:
            exporter = get_exporter(format)
        except ValueError:
            available = list_exporters()
            raise ValueError(f"Unsupported format: {format}. Available: {available}")

        result = exporter.export(digests)

        return {
            "success": True,
            "format": format,
            "digest_count": len(digests),
            "content_type": result.content_type,
            "filename": result.filename,
            "content_preview": result.content[:2000] if len(result.content) > 2000 else result.content,
            "content_truncated": len(result.content) > 2000,
            "full_content_length": len(result.content),
        }

    return ToolDefinition(
        name="export_digests",
        description=(
            "Export digests to JSON or CSV format. Use this to get digest data in a "
            "structured format for external use or analysis."
        ),
        parameters={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["json", "csv"],
                    "description": "Export format",
                    "default": "json",
                },
                "feed_id": {
                    "type": "integer",
                    "description": "Filter by feed ID",
                },
                "source_id": {
                    "type": "integer",
                    "description": "Filter by source ID",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag name",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum digests to export (1-1000)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": [],
        },
        handler=handler,
        category="digests",
    )


# =============================================================================
# RAG / KNOWLEDGE TOOLS
# =============================================================================


@tool_registry.register
def query_knowledge_tool() -> ToolDefinition:
    """Register the query_knowledge tool (RAG)."""

    async def handler(
        db: "Session",
        question: str,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        max_chunks: int = 10,
    ) -> dict[str, Any]:
        """Query the knowledge base using RAG.

        Args:
            db: Database session (injected by executor).
            question: The question to answer.
            feed_id: Optionally restrict to a specific feed.
            source_id: Optionally restrict to a specific source.
            days: Optionally restrict to digests from the last N days.
            max_chunks: Maximum chunks to retrieve (1-50).

        Returns:
            RAG result with answer and citations.
        """
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.rag_service import RAGService, RAGFilters
        from reconly_core.providers.factory import get_summarizer

        # Get providers
        embedding_provider = get_embedding_provider(db=db)
        summarizer = get_summarizer(db=db, enable_fallback=False)

        # Create RAG service
        rag_service = RAGService(
            db=db,
            embedding_provider=embedding_provider,
            summarizer=summarizer,
        )

        # Build filters
        filters = RAGFilters(
            feed_id=feed_id,
            source_id=source_id,
            days=days,
        )

        # Execute query
        result = await rag_service.query(
            question=question,
            filters=filters,
            max_chunks=min(max_chunks, 50),
            include_answer=True,
        )

        return {
            "answer": result.answer,
            "citations": [
                {
                    "id": c.id,
                    "digest_id": c.digest_id,
                    "digest_title": c.digest_title,
                    "url": c.url,
                    "relevance_score": c.relevance_score,
                }
                for c in result.citations
            ],
            "chunks_retrieved": result.chunks_retrieved,
            "grounded": result.grounded,
            "model_used": result.model_used,
            "total_took_ms": result.total_took_ms,
        }

    return ToolDefinition(
        name="query_knowledge",
        description=(
            "Ask a question and get an answer based on the indexed knowledge base. "
            "This uses RAG (Retrieval-Augmented Generation) to find relevant content "
            "and generate an answer with citations to source digests."
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to answer based on the knowledge base",
                    "minLength": 1,
                },
                "feed_id": {
                    "type": "integer",
                    "description": "Optionally restrict search to a specific feed",
                },
                "source_id": {
                    "type": "integer",
                    "description": "Optionally restrict search to a specific source",
                },
                "days": {
                    "type": "integer",
                    "description": "Optionally restrict to digests from the last N days",
                    "minimum": 1,
                },
                "max_chunks": {
                    "type": "integer",
                    "description": "Maximum chunks to retrieve (1-50)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["question"],
        },
        handler=handler,
        category="knowledge",
    )


# =============================================================================
# ANALYTICS TOOLS
# =============================================================================


@tool_registry.register
def get_analytics_tool() -> ToolDefinition:
    """Register the get_analytics tool."""

    async def handler(
        db: "Session",
        period: str = "7d",
    ) -> dict[str, Any]:
        """Get analytics and dashboard data.

        Args:
            db: Database session (injected by executor).
            period: Time period for analytics (7d, 30d, 90d).

        Returns:
            Analytics summary with token usage, success rates, and counts.
        """
        from sqlalchemy import func
        from reconly_core.database.models import LLMUsageLog, FeedRun, Feed, Digest, Source

        # Parse period
        days_map = {"7d": 7, "30d": 30, "90d": 90}
        days = days_map.get(period, 7)
        since = datetime.utcnow() - timedelta(days=days)

        # Token totals
        token_stats = db.query(
            func.sum(LLMUsageLog.tokens_in).label("total_tokens_in"),
            func.sum(LLMUsageLog.tokens_out).label("total_tokens_out"),
            func.count(LLMUsageLog.id).label("total_requests"),
        ).filter(LLMUsageLog.timestamp >= since).first()

        # Success rate for feed runs
        total_runs = db.query(func.count(FeedRun.id)).filter(
            FeedRun.created_at >= since
        ).scalar() or 0

        successful_runs = db.query(func.count(FeedRun.id)).filter(
            FeedRun.created_at >= since,
            FeedRun.status == "completed",
        ).scalar() or 0

        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

        # Total digests in period
        total_digests = db.query(func.count(Digest.id)).filter(
            Digest.created_at >= since
        ).scalar() or 0

        # Overall counts
        total_feeds = db.query(func.count(Feed.id)).scalar() or 0
        total_sources = db.query(func.count(Source.id)).scalar() or 0
        all_digests = db.query(func.count(Digest.id)).scalar() or 0

        return {
            "period": period,
            "token_usage": {
                "tokens_in": token_stats.total_tokens_in or 0,
                "tokens_out": token_stats.total_tokens_out or 0,
                "total_requests": token_stats.total_requests or 0,
            },
            "feed_runs": {
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "success_rate": round(success_rate, 2),
            },
            "digests_created": total_digests,
            "totals": {
                "feeds": total_feeds,
                "sources": total_sources,
                "digests": all_digests,
            },
        }

    return ToolDefinition(
        name="get_analytics",
        description=(
            "Get analytics and statistics about the system. Includes token usage, "
            "feed run success rates, and content counts for a specified time period."
        ),
        parameters={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["7d", "30d", "90d"],
                    "description": "Time period for analytics",
                    "default": "7d",
                },
            },
            "required": [],
        },
        handler=handler,
        category="analytics",
    )


# =============================================================================
# TAG TOOLS
# =============================================================================


@tool_registry.register
def list_tags_tool() -> ToolDefinition:
    """Register the list_tags tool."""

    async def handler(
        db: "Session",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List all tags with usage counts.

        Args:
            db: Database session (injected by executor).
            limit: Maximum tags to return.

        Returns:
            List of tags with digest counts.
        """
        from sqlalchemy import func
        from reconly_core.database.models import Tag, DigestTag

        # Query tags with digest counts
        digest_count_subq = (
            db.query(DigestTag.tag_id, func.count(DigestTag.digest_id).label("count"))
            .group_by(DigestTag.tag_id)
            .subquery()
        )

        results = (
            db.query(Tag, func.coalesce(digest_count_subq.c.count, 0).label("digest_count"))
            .outerjoin(digest_count_subq, Tag.id == digest_count_subq.c.tag_id)
            .order_by(func.coalesce(digest_count_subq.c.count, 0).desc(), Tag.name)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "digest_count": digest_count,
            }
            for tag, digest_count in results
        ]

    return ToolDefinition(
        name="list_tags",
        description=(
            "List all tags used for categorizing digests. Tags help organize and "
            "filter content. Returns tags sorted by usage count (most used first)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum tags to return (1-200)",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": [],
        },
        handler=handler,
        category="tags",
    )


@tool_registry.register
def create_tag_tool() -> ToolDefinition:
    """Register the create_tag tool."""

    async def handler(
        db: "Session",
        name: str,
    ) -> dict[str, Any]:
        """Create a new tag.

        Args:
            db: Database session (injected by executor).
            name: Name for the tag.

        Returns:
            Created tag dictionary.
        """
        from reconly_core.database.models import Tag

        # Check if tag already exists
        existing = db.query(Tag).filter(Tag.name == name).first()
        if existing:
            return {
                "id": existing.id,
                "name": existing.name,
                "already_existed": True,
                "message": f"Tag '{name}' already exists",
            }

        # Create new tag
        tag = Tag(name=name)
        db.add(tag)
        db.commit()
        db.refresh(tag)

        return {
            "id": tag.id,
            "name": tag.name,
            "already_existed": False,
            "message": f"Tag '{name}' created successfully",
        }

    return ToolDefinition(
        name="create_tag",
        description=(
            "Create a new tag for categorizing digests. If the tag already exists, "
            "returns the existing tag information."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the tag (required)",
                    "minLength": 1,
                    "maxLength": 100,
                },
            },
            "required": ["name"],
        },
        handler=handler,
        category="tags",
    )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

# All tools are registered via decorators when this module is imported
__all__ = [
    "tool_registry",
]
