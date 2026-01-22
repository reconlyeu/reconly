"""Feed processing service using database-backed entities.

This service replaces YAML-based batch processing with database-driven
Feed and Source entities, providing proper execution tracking and
LLM usage logging.
"""
import time
import hmac
import hashlib
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import httpx

from sqlalchemy.orm import Session

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

from reconly_core.database.models import (
    Base, Feed, Source, FeedSource, FeedRun, Digest, LLMUsageLog,
    PromptTemplate, DigestSourceItem, SourceContent
)
from reconly_core.database.crud import DEFAULT_DATABASE_URL
from reconly_core.database.seed import get_default_prompt_template, get_default_consolidated_template
from reconly_core.fetchers import get_fetcher
from reconly_core.providers import get_summarizer
from reconly_core.providers.base import BaseProvider
from reconly_core.tracking import FeedTracker
from reconly_core.logging import get_logger, generate_trace_id, clear_trace_id
from reconly_core.services.email_service import EmailService
from reconly_core.services.content_filter import ContentFilter
from reconly_core.resilience import SourceCircuitBreaker, CircuitBreakerConfig

logger = get_logger(__name__)


# Error types for structured error reporting
ERROR_TYPE_FETCH = "FetchError"
ERROR_TYPE_PARSE = "ParseError"
ERROR_TYPE_SUMMARIZE = "SummarizeError"
ERROR_TYPE_SAVE = "SaveError"
ERROR_TYPE_TIMEOUT = "TimeoutError"
ERROR_TYPE_CIRCUIT_OPEN = "CircuitOpenError"
ERROR_TYPE_EXPORT = "ExportError"


def _detect_error_type(error_msg: str, default_type: str = ERROR_TYPE_FETCH) -> str:
    """Detect error type from error message."""
    msg_lower = error_msg.lower()
    if any(kw in msg_lower for kw in ['timeout', 'timed out', 'time out']):
        return ERROR_TYPE_TIMEOUT
    if any(kw in msg_lower for kw in ['connection', 'connect', 'network', 'unreachable']):
        return ERROR_TYPE_FETCH
    if any(kw in msg_lower for kw in ['parse', 'invalid', 'malformed', 'decode']):
        return ERROR_TYPE_PARSE
    return default_type


def _format_article_for_consolidation(
    title: str,
    content: str,
    source_name: Optional[str] = None,
    published_at: Optional[str] = None,
    url: Optional[str] = None
) -> str:
    """
    Format a single article for inclusion in a consolidated prompt.

    Args:
        title: Article title
        content: Article content
        source_name: Name of the source (for multi-source mode)
        published_at: Publication date (ISO format string)
        url: Original article URL for source linking

    Returns:
        Formatted article block with source attribution markers
    """
    parts = []

    if source_name:
        if url:
            parts.append(f"[Source: {source_name}]({url})")
        else:
            parts.append(f"[Source: {source_name}]")

    parts.append(f"Title: {title}")

    if url:
        parts.append(f"URL: {url}")

    if published_at:
        parts.append(f"Published: {published_at}")

    parts.append(f"Content:\n{content}")

    return "\n".join(parts)


def _build_prompts_from_template(
    template: PromptTemplate,
    content_data: Dict[str, Any],
) -> tuple[str, str]:
    """
    Build system and user prompts from a PromptTemplate and content data.

    Args:
        template: PromptTemplate instance
        content_data: Dictionary with 'title', 'content', 'source_type', etc.

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Get values from content_data
    title = content_data.get('title', 'No title')
    content = content_data.get('content', '')
    source_type = content_data.get('source_type', 'content')

    # Format user prompt template with placeholders
    try:
        user_prompt = template.user_prompt_template.format(
            title=title,
            content=content,
            source_type=source_type,
            target_length=template.target_length,
        )
    except KeyError:
        # If template has extra placeholders we don't have, use as-is
        user_prompt = template.user_prompt_template

    return template.system_prompt, user_prompt


@dataclass
class FeedRunOptions:
    """Options for running a feed."""
    triggered_by: str = "manual"  # manual, schedule, api
    triggered_by_user_id: Optional[int] = None
    enable_fallback: bool = True
    api_key: Optional[str] = None
    show_progress: bool = True
    delay_between: int = 2
    dry_run: bool = False  # If True, don't save digests or update run status


@dataclass
class FeedRunResult:
    """Result of a feed run."""
    feed_run_id: int
    feed_id: int
    feed_name: str
    status: str
    sources_total: int
    sources_processed: int
    sources_failed: int
    items_processed: int
    total_cost: float
    duration_seconds: Optional[float] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class ItemBatch:
    """A batch of items to be consolidated into a single digest."""
    items: List[Dict[str, Any]]  # Original article data
    source_id: Optional[int]  # Source ID (None for all_sources mode)
    source_name: Optional[str]  # Source name for prompts
    mode: str  # 'individual', 'per_source', or 'all_sources'


def _batch_items_by_mode(
    items: List[Dict[str, Any]],
    mode: str,
    source_id: int,
    source_name: str
) -> List[ItemBatch]:
    """
    Batch items based on digest mode.

    Args:
        items: List of article data dicts
        mode: Digest mode ('individual', 'per_source', 'all_sources')
        source_id: Source ID
        source_name: Source name

    Returns:
        List of ItemBatch objects
    """
    if mode == 'individual':
        # Each item is its own batch
        return [
            ItemBatch(
                items=[item],
                source_id=source_id,
                source_name=source_name,
                mode='individual'
            )
            for item in items
        ]
    elif mode == 'per_source':
        # All items from this source in one batch
        if not items:
            return []
        return [
            ItemBatch(
                items=items,
                source_id=source_id,
                source_name=source_name,
                mode='per_source'
            )
        ]
    else:
        # For all_sources, items are collected across sources
        # This function handles single-source batching, so just return one batch
        if not items:
            return []
        return [
            ItemBatch(
                items=items,
                source_id=source_id,
                source_name=source_name,
                mode='all_sources'
            )
        ]


def _generate_consolidated_url(feed_id: int, feed_run_id: int, mode: str, source_id: Optional[int] = None) -> str:
    """
    Generate synthetic URL for consolidated digests.

    Args:
        feed_id: Feed ID
        feed_run_id: FeedRun ID
        mode: Consolidation mode
        source_id: Source ID (for per_source mode)

    Returns:
        Synthetic URL string
    """
    if mode == 'per_source' and source_id:
        return f"consolidated://{feed_id}/{feed_run_id}/source/{source_id}"
    else:
        return f"consolidated://{feed_id}/{feed_run_id}/all"


class FeedService:
    """Service for managing and executing feeds."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize feed service.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url or DEFAULT_DATABASE_URL
        self._session: Optional[Session] = None
        self._engine = None
        self.tracker = FeedTracker()
        self.circuit_breaker = SourceCircuitBreaker(CircuitBreakerConfig.from_env())

    def _get_session(self) -> Session:
        """Get or create database session."""
        if self._session is None:
            if self._engine is None:
                self._engine = create_engine(self.database_url, echo=False)
                Base.metadata.create_all(self._engine)
            SessionLocal = sessionmaker(bind=self._engine)
            self._session = SessionLocal()
        return self._session

    def get_feed(self, feed_id: int, user_id: Optional[int] = None) -> Optional[Feed]:
        """
        Get a feed by ID.

        Args:
            feed_id: Feed ID
            user_id: Optional user ID for filtering

        Returns:
            Feed or None
        """
        session = self._get_session()
        query = session.query(Feed).filter(Feed.id == feed_id)

        if user_id is not None:
            query = query.filter(Feed.user_id == user_id)

        return query.first()

    def list_feeds(self, user_id: Optional[int] = None, enabled_only: bool = False) -> List[Feed]:
        """
        List all feeds.

        Args:
            user_id: Optional user ID for filtering
            enabled_only: Only return feeds with schedule_enabled=True

        Returns:
            List of feeds
        """
        session = self._get_session()
        query = session.query(Feed)

        if user_id is not None:
            query = query.filter(Feed.user_id == user_id)

        if enabled_only:
            query = query.filter(Feed.schedule_enabled == True)

        return query.all()

    def get_feed_sources(self, feed_id: int) -> List[Source]:
        """
        Get all enabled sources for a feed.

        Args:
            feed_id: Feed ID

        Returns:
            List of sources ordered by priority
        """
        session = self._get_session()

        feed_sources = session.query(FeedSource).filter(
            FeedSource.feed_id == feed_id,
            FeedSource.enabled == True
        ).order_by(FeedSource.priority.desc()).all()

        return [fs.source for fs in feed_sources if fs.source.enabled]

    def run_feed(self, feed_id: int, options: FeedRunOptions = None) -> FeedRunResult:
        """
        Execute a feed - fetch and process all sources.

        Args:
            feed_id: Feed ID to run
            options: Run options

        Returns:
            FeedRunResult with execution details
        """
        if options is None:
            options = FeedRunOptions()

        # Generate trace ID for log correlation
        trace_id = generate_trace_id()

        session = self._get_session()

        # Get feed
        feed = self.get_feed(feed_id)
        if not feed:
            logger.error("Feed not found", feed_id=feed_id)
            raise ValueError(f"Feed not found: {feed_id}")

        # Get sources
        sources = self.get_feed_sources(feed_id)
        if not sources:
            logger.warning("No enabled sources for feed", feed_id=feed_id, feed_name=feed.name)
            raise ValueError(f"No enabled sources for feed: {feed_id}")

        logger.info(
            "Starting feed run",
            feed_id=feed_id,
            feed_name=feed.name,
            sources_count=len(sources),
            triggered_by=options.triggered_by,
        )

        # Create FeedRun record with trace_id
        feed_run = FeedRun(
            feed_id=feed_id,
            triggered_by=options.triggered_by,
            triggered_by_user_id=options.triggered_by_user_id,
            status="running",
            started_at=datetime.utcnow(),
            sources_total=len(sources),
            trace_id=trace_id,
            created_at=datetime.utcnow(),
        )
        session.add(feed_run)
        session.commit()

        if options.show_progress:
            print(f"\n{'='*80}")
            print(f"🚀 Running feed: {feed.name}")
            print(f"{'='*80}")
            print(f"   Sources: {len(sources)}")
            print(f"   Run ID: {feed_run.id}")
            print()

        # Get summarizer
        summarizer = self._get_summarizer(feed, options)

        # Store LLM info on feed run
        feed_run.llm_provider = summarizer.get_provider_name()
        feed_run.llm_model = getattr(summarizer, 'model', None)
        session.commit()

        # Track metrics
        sources_processed = 0
        sources_failed = 0
        sources_skipped = 0  # Skipped due to circuit breaker
        items_processed = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0
        errors = []  # Legacy text errors
        structured_errors = []  # Structured error details

        # For all_sources mode, collect items from all sources first
        if feed.digest_mode == 'all_sources':
            all_items_result = self._collect_all_source_items(
                sources=sources,
                feed=feed,
                feed_run=feed_run,
                summarizer=summarizer,
                options=options,
                session=session,
            )
            sources_processed = all_items_result.get("sources_processed", 0)
            sources_failed = all_items_result.get("sources_failed", 0)
            sources_skipped = all_items_result.get("sources_skipped", 0)
            items_processed = all_items_result.get("items_count", 0)
            total_tokens_in = all_items_result.get("tokens_in", 0)
            total_tokens_out = all_items_result.get("tokens_out", 0)
            total_cost = all_items_result.get("cost", 0.0)
            errors = all_items_result.get("errors", [])
            structured_errors = all_items_result.get("structured_errors", [])
        else:
            # Process each source (individual or per_source mode)
            for idx, source in enumerate(sources, 1):
                try:
                    if options.show_progress:
                        print(f"📌 [{idx}/{len(sources)}] {source.name}")

                    # Check circuit breaker before processing
                    should_skip, skip_reason = self.circuit_breaker.should_skip(source)
                    if should_skip:
                        sources_skipped += 1
                        logger.info(
                            "Source skipped due to circuit breaker",
                            source_id=source.id,
                            source_name=source.name,
                            reason=skip_reason,
                            health_status=source.health_status,
                        )
                        structured_errors.append({
                            "source_id": source.id,
                            "source_name": source.name,
                            "error_type": ERROR_TYPE_CIRCUIT_OPEN,
                            "message": skip_reason,
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                        if options.show_progress:
                            print(f"   ⏸️ Skipped (circuit open): {source.health_status}")
                        continue

                    result = self._process_source(
                        source=source,
                        feed=feed,
                        feed_run=feed_run,
                        summarizer=summarizer,
                        options=options,
                        session=session,
                    )

                    if result["success"]:
                        sources_processed += 1
                        items_processed += result.get("items_count", 1)
                        total_tokens_in += result.get("tokens_in", 0)
                        total_tokens_out += result.get("tokens_out", 0)
                        total_cost += result.get("cost", 0.0)

                        # Record success with circuit breaker
                        self.circuit_breaker.record_success(source, session)

                        logger.info(
                            "Source processed successfully",
                            source_id=source.id,
                            source_name=source.name,
                            items_count=result.get("items_count", 1),
                        )

                        if options.show_progress:
                            print(f"   ✅ {result.get('items_count', 1)} item(s) processed")
                    else:
                        sources_failed += 1
                        error_msg = result.get('error', 'Unknown error')
                        error_type = result.get('error_type', ERROR_TYPE_FETCH)
                        errors.append(f"{source.name}: {error_msg}")
                        structured_errors.append({
                            "source_id": source.id,
                            "source_name": source.name,
                            "error_type": error_type,
                            "message": error_msg,
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                        # Record failure with circuit breaker
                        self.circuit_breaker.record_failure(source, session, Exception(error_msg))

                        logger.error(
                            "Source processing failed",
                            source_id=source.id,
                            source_name=source.name,
                            error_type=error_type,
                            error=error_msg,
                        )

                        if options.show_progress:
                            print(f"   ❌ {error_msg}")

                    # Delay between sources
                    if idx < len(sources) and options.delay_between > 0:
                        time.sleep(options.delay_between)

                except Exception as e:
                    sources_failed += 1
                    error_msg = str(e)
                    error_type = _detect_error_type(error_msg, ERROR_TYPE_FETCH)
                    errors.append(f"{source.name}: {error_msg}")
                    structured_errors.append({
                        "source_id": source.id,
                        "source_name": source.name,
                        "error_type": error_type,
                        "message": error_msg,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                    # Record failure with circuit breaker
                    self.circuit_breaker.record_failure(source, session, e)

                    logger.exception(
                        "Unexpected error processing source",
                        source_id=source.id,
                        source_name=source.name,
                        error=error_msg,
                    )

                    if options.show_progress:
                        print(f"   ❌ Error: {e}")

        # Update FeedRun with results
        # Check if any errors were timeouts - these should mark the run as failed
        has_timeout = any(
            err.get("error_type") == ERROR_TYPE_TIMEOUT
            for err in structured_errors
        )
        if sources_failed == 0:
            feed_run.status = "completed"
        elif has_timeout:
            feed_run.status = "failed"  # Timeout errors are critical failures
        else:
            feed_run.status = "partial"
        feed_run.completed_at = datetime.utcnow()
        feed_run.sources_processed = sources_processed
        feed_run.sources_failed = sources_failed
        feed_run.items_processed = items_processed
        feed_run.total_tokens_in = total_tokens_in
        feed_run.total_tokens_out = total_tokens_out
        feed_run.total_cost = total_cost

        if errors:
            feed_run.error_log = "\n".join(errors)

        # Store structured error details
        if structured_errors:
            feed_run.error_details = {
                "errors": structured_errors,
                "summary": f"{len(structured_errors)} source(s) failed during processing",
            }

        logger.info(
            "Feed run completed",
            feed_id=feed_id,
            feed_name=feed.name,
            status=feed_run.status,
            sources_processed=sources_processed,
            sources_failed=sources_failed,
            sources_skipped=sources_skipped,
            items_processed=items_processed,
            total_cost=total_cost,
            duration_seconds=feed_run.duration_seconds,
        )

        # Clear trace ID after run completes
        clear_trace_id()

        # Update feed last_run_at
        feed.last_run_at = datetime.utcnow()

        session.commit()

        # Send email if configured
        self._send_email_if_configured(feed, feed_run, session)

        # Send webhook if configured
        self._send_webhook_if_configured(feed, feed_run, session)

        # Export to configured destinations if items were processed
        export_errors = []
        if items_processed > 0:
            export_errors = self._export_if_configured(feed, feed_run, session)

            # If export errors occurred, update error_details and status
            if export_errors:
                # Add export errors to error_details
                current_details = feed_run.error_details or {}
                current_errors = current_details.get("errors", [])
                current_errors.extend(export_errors)
                current_details["errors"] = current_errors

                # Update summary to include export errors
                source_error_count = len([e for e in current_errors if e.get("error_type") != ERROR_TYPE_EXPORT])
                export_error_count = len(export_errors)
                current_details["summary"] = (
                    f"{source_error_count} source error(s), {export_error_count} export error(s)"
                    if source_error_count > 0
                    else f"{export_error_count} export error(s)"
                )

                feed_run.error_details = current_details

                # Update status to completed_with_warnings if was completed
                if feed_run.status == "completed":
                    feed_run.status = "completed_with_warnings"

                session.commit()

                if options.show_progress:
                    print(f"   Export errors: {len(export_errors)}")

        # Process RAG embeddings and relationships for new digests
        if items_processed > 0 and not options.dry_run:
            self._process_rag_for_feed_run(feed_run, session, options.show_progress)

        if options.show_progress:
            print(f"\n{'='*80}")
            print("✅ Feed run complete")
            print(f"   Sources: {sources_processed}/{len(sources)} successful")
            if sources_skipped > 0:
                print(f"   Skipped: {sources_skipped} (circuit breaker)")
            if sources_failed > 0:
                print(f"   Failed: {sources_failed}")
            if export_errors:
                print(f"   Export errors: {len(export_errors)}")
            print(f"   Items: {items_processed} processed")
            print(f"   Cost: ${total_cost:.4f}")
            print(f"{'='*80}")

        return FeedRunResult(
            feed_run_id=feed_run.id,
            feed_id=feed_id,
            feed_name=feed.name,
            status=feed_run.status,
            sources_total=len(sources),
            sources_processed=sources_processed,
            sources_failed=sources_failed,
            items_processed=items_processed,
            total_cost=total_cost,
            duration_seconds=feed_run.duration_seconds,
            errors=errors,
        )

    def _get_summarizer(self, feed: Feed, options: FeedRunOptions) -> BaseProvider:
        """Get summarizer based on feed/template settings.

        Priority order:
        1. Feed's model_provider/model_name
        2. Prompt template's model_provider/model_name
        3. Database settings (via SettingsService)
        4. Environment variables (DEFAULT_PROVIDER/DEFAULT_MODEL)
        5. Code defaults
        """
        provider = feed.model_provider
        model = feed.model_name

        # Check prompt template for model preference
        if feed.prompt_template:
            if not provider and feed.prompt_template.model_provider:
                provider = feed.prompt_template.model_provider
            if not model and feed.prompt_template.model_name:
                model = feed.prompt_template.model_name

        return get_summarizer(
            provider=provider,
            model=model,
            api_key=options.api_key,
            enable_fallback=options.enable_fallback,
            db=self._get_session(),
        )

    def _get_language(self, feed: Feed, source: Source) -> str:
        """Determine language from feed/template/source hierarchy."""
        # Feed's prompt template
        if feed.prompt_template and feed.prompt_template.language:
            return feed.prompt_template.language

        # Source default
        if source.default_language:
            return source.default_language

        # System default
        return "de"

    def _process_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        options: FeedRunOptions,
        session: Session,
    ) -> Dict[str, Any]:
        """Process a single source."""
        language = self._get_language(feed, source)

        try:
            # Use fetcher factory to get appropriate fetcher
            fetcher = get_fetcher(source.type)

            if source.type == "rss":
                return self._process_rss_source(
                    source, feed, feed_run, summarizer, language, options, session, fetcher
                )
            elif source.type == "youtube":
                return self._process_youtube_source(
                    source, feed, feed_run, summarizer, language, options, session, fetcher
                )
            elif source.type == "imap":
                return self._process_imap_source(
                    source, feed, feed_run, summarizer, language, options, session, fetcher
                )
            elif source.type == "agent":
                return self._process_agent_source(
                    source, feed, feed_run, summarizer, language, options, session, fetcher
                )
            else:
                return self._process_website_source(
                    source, feed, feed_run, summarizer, language, options, session, fetcher
                )

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _process_website_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        options: FeedRunOptions,
        session: Session,
        fetcher=None,
    ) -> Dict[str, Any]:
        """Process a website source."""
        if fetcher is None:
            fetcher = get_fetcher('website')
        content_items = fetcher.fetch(source.url)
        content_data = content_items[0] if content_items else {}

        # Apply content filter if configured
        if source.include_keywords or source.exclude_keywords:
            content_filter = ContentFilter(
                include_keywords=source.include_keywords,
                exclude_keywords=source.exclude_keywords,
                filter_mode=source.filter_mode or "both",
                use_regex=source.use_regex or False,
            )
            if not content_filter.matches(
                content_data.get("title", ""),
                content_data.get("content", "")
            ):
                logger.info(
                    "content_filter_excluded",
                    source_id=source.id,
                    source_name=source.name,
                    url=source.url,
                )
                return {"success": True, "items_count": 0}

        # Skip if digest already exists for this URL (fast pre-check)
        website_url = content_data.get("url") or source.url
        if website_url and self._digest_exists(website_url, session):
            logger.info(f"Digest already exists for URL: {website_url}, skipping summarization")
            return {"success": True, "items_count": 0}

        # Resolve prompt template
        template = None
        if feed.prompt_template_id:
            template = session.query(PromptTemplate).filter(
                PromptTemplate.id == feed.prompt_template_id
            ).first()
        if not template:
            template = get_default_prompt_template(session, language=language)

        # Build prompts from template
        system_prompt, user_prompt = None, None
        if template:
            system_prompt, user_prompt = _build_prompts_from_template(template, content_data)

        result = summarizer.summarize(
            content_data,
            language=language,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Save digest
        if not options.dry_run:
            digest = self._save_digest(
                result, source, feed, feed_run, session
            )
            self._log_llm_usage(
                result, source, feed, feed_run, digest, session
            )

        return {
            "success": True,
            "items_count": 1,
            "tokens_in": result.get("model_info", {}).get("input_tokens", 0),
            "tokens_out": result.get("model_info", {}).get("output_tokens", 0),
            "cost": result.get("estimated_cost", 0.0),
        }

    def _process_agent_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        options: FeedRunOptions,
        session: Session,
        fetcher=None,
    ) -> Dict[str, Any]:
        """Process an AI agent source.

        Agent sources use the URL field as a research prompt. The agent fetcher
        conducts research and returns a full report as content. We then run
        summarization using the feed's prompt template to generate a structured
        summary for display, while keeping the full report for RAG.
        """
        if fetcher is None:
            fetcher = get_fetcher('agent')

        # Agent fetcher requires db, source_id, and config kwargs to properly
        # resolve provider settings and track agent runs
        content_items = fetcher.fetch(
            source.url,  # This is the research prompt for agent sources
            db=session,
            source_id=source.id,
            config=source.config or {},
            trace_id=feed_run.trace_id if feed_run else None,
        )

        if not content_items:
            return {"success": True, "items_count": 0}

        content_data = content_items[0]

        # Track agent tokens separately (research phase)
        agent_metadata = content_data.get('metadata', {})
        agent_tokens_in = agent_metadata.get('tokens_in', 0)
        agent_tokens_out = agent_metadata.get('tokens_out', 0)

        # Resolve prompt template for summarization
        template = None
        if feed.prompt_template_id:
            template = session.query(PromptTemplate).filter(
                PromptTemplate.id == feed.prompt_template_id
            ).first()
        if not template:
            template = get_default_prompt_template(session, language=language)

        # Build prompts from template and run summarization
        # This generates a structured summary from the research report
        system_prompt, user_prompt = None, None
        if template:
            system_prompt, user_prompt = _build_prompts_from_template(template, content_data)
            logger.info(
                "agent_source_summarization_starting",
                source_id=source.id,
                template_id=template.id,
                content_length=len(content_data.get('content', '')),
            )
        else:
            logger.warning(
                "agent_source_no_template",
                source_id=source.id,
                message="No prompt template found, using fallback",
            )

        result = summarizer.summarize(
            content_data,
            language=language,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Log summarization result
        summary_text = result.get("summary", "")
        logger.info(
            "agent_source_summarization_complete",
            source_id=source.id,
            has_summary=bool(summary_text),
            summary_length=len(summary_text) if summary_text else 0,
        )

        # Get summarization token usage and provider info
        summary_model_info = result.get("model_info", {})
        summary_tokens_in = summary_model_info.get("input_tokens", 0)
        summary_tokens_out = summary_model_info.get("output_tokens", 0)
        summary_cost = result.get("estimated_cost", 0.0)

        # Save digest with both content (full report) and summary
        if not options.dry_run:
            digest = self._save_digest(
                result, source, feed, feed_run, session
            )

            # Log combined token usage (agent research + summarization)
            # Use summarizer's model_info for provider/model, but combine token counts
            combined_model_info = {
                **summary_model_info,
                'input_tokens': agent_tokens_in + summary_tokens_in,
                'output_tokens': agent_tokens_out + summary_tokens_out,
            }
            self._log_llm_usage(
                {
                    'model_info': combined_model_info,
                    'estimated_cost': summary_cost,  # Agent cost tracked separately in AgentRun
                },
                source, feed, feed_run, digest, session
            )

        return {
            "success": True,
            "items_count": 1,
            "tokens_in": agent_tokens_in + summary_tokens_in,
            "tokens_out": agent_tokens_out + summary_tokens_out,
            "cost": summary_cost,
        }

    def _process_imap_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        options: FeedRunOptions,
        session: Session,
        fetcher=None,
    ) -> Dict[str, Any]:
        """Process an IMAP email source.

        Fetches emails from IMAP server using credentials stored in source.config,
        processes each email through summarization, and tracks processed message IDs
        for incremental fetching.
        """
        if fetcher is None:
            fetcher = get_fetcher('imap')

        # Extract IMAP config from source
        source_config = source.config or {}

        # Build kwargs for IMAP fetcher
        imap_kwargs = {
            'imap_provider': source_config.get('provider', 'generic'),
            'imap_host': source_config.get('imap_host'),
            'imap_port': source_config.get('imap_port', 993),
            'imap_username': source_config.get('imap_username'),
            # Support both plaintext (dev/testing) and encrypted (production) passwords
            'imap_password': source_config.get('imap_password'),
            'imap_password_encrypted': source_config.get('imap_password_encrypted'),
            'imap_use_ssl': source_config.get('imap_use_ssl', True),
            'imap_folders': source_config.get('folders', ['INBOX']),
            'imap_from_filter': source_config.get('from_filter'),
            'imap_subject_filter': source_config.get('subject_filter'),
            # Pass processed message IDs for incremental fetching
            'processed_message_ids': source_config.get('processed_message_ids', []),
        }

        # Get last read timestamp and max_items
        last_read = self.tracker.get_last_read(source.url) if source.url else None
        max_items = source_config.get('max_items')

        logger.info(
            "imap_fetch_start",
            source_id=source.id,
            source_name=source.name,
            provider=imap_kwargs['imap_provider'],
            folders=imap_kwargs['imap_folders'],
        )

        try:
            # Fetch emails
            emails = fetcher.fetch(
                source.url or f"imap://{imap_kwargs['imap_host']}",
                since=last_read,
                max_items=max_items,
                **imap_kwargs
            )
        except Exception as e:
            logger.error(
                "imap_fetch_error",
                source_id=source.id,
                source_name=source.name,
                error=str(e),
                exc_info=True,
            )
            return {"success": False, "error": f"IMAP fetch failed: {e}"}

        if not emails:
            logger.info(
                "imap_fetch_empty",
                source_id=source.id,
                source_name=source.name,
            )
            return {"success": True, "items_count": 0}

        # Remove metadata if present (last item with _fetch_metadata key)
        if emails and isinstance(emails[-1], dict) and emails[-1].get("_fetch_metadata"):
            emails.pop()

        logger.info(
            "imap_fetch_complete",
            source_id=source.id,
            source_name=source.name,
            email_count=len(emails),
        )

        # Apply content filter if configured
        if source.include_keywords or source.exclude_keywords:
            content_filter = ContentFilter(
                include_keywords=source.include_keywords,
                exclude_keywords=source.exclude_keywords,
                filter_mode=source.filter_mode or "both",
                use_regex=source.use_regex or False,
            )
            original_count = len(emails)
            emails = [
                e for e in emails
                if content_filter.matches(e.get("title", ""), e.get("content", ""))
            ]
            if original_count != len(emails):
                logger.info(
                    "content_filter_applied",
                    source_id=source.id,
                    source_name=source.name,
                    original_count=original_count,
                    remaining_count=len(emails),
                    filtered_out=original_count - len(emails),
                )
            if not emails:
                return {"success": True, "items_count": 0}

        items_count = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0
        latest_timestamp = last_read
        new_message_ids = []

        # Resolve prompt template once for all emails
        template = None
        if feed.prompt_template_id:
            template = session.query(PromptTemplate).filter(
                PromptTemplate.id == feed.prompt_template_id
            ).first()
        if not template:
            template = get_default_prompt_template(session, language=language)

        for email in emails:
            try:
                # Track message ID for incremental fetching
                message_id = email.get("message_id")
                if message_id:
                    new_message_ids.append(message_id)

                # Skip if digest already exists for this message
                email_url = email.get("url")
                if email_url and self._digest_exists(email_url, session):
                    logger.debug(f"Digest already exists for email: {email_url}, skipping")
                    continue

                # Build prompts from template
                system_prompt, user_prompt = None, None
                if template:
                    system_prompt, user_prompt = _build_prompts_from_template(template, email)

                result = summarizer.summarize(
                    email,
                    language=language,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                # Save digest
                if not options.dry_run:
                    digest = self._save_digest(
                        result, source, feed, feed_run, session
                    )
                    self._log_llm_usage(
                        result, source, feed, feed_run, digest, session
                    )

                items_count += 1
                total_tokens_in += result.get("model_info", {}).get("input_tokens", 0)
                total_tokens_out += result.get("model_info", {}).get("output_tokens", 0)
                total_cost += result.get("estimated_cost", 0.0)

                # Track latest timestamp
                if email.get("published"):
                    try:
                        email_dt = datetime.fromisoformat(email["published"])
                        if latest_timestamp is None or email_dt > latest_timestamp:
                            latest_timestamp = email_dt
                    except Exception:
                        pass

            except Exception as e:
                logger.error(
                    "imap_email_process_error",
                    source_id=source.id,
                    email_subject=email.get("title", "unknown"),
                    error=str(e),
                    exc_info=True,
                )

        # Update processed message IDs in source config (keep last 1000)
        if new_message_ids and not options.dry_run:
            existing_ids = source_config.get('processed_message_ids', [])
            all_ids = list(set(existing_ids + new_message_ids))[-1000:]
            source.config = {**source_config, 'processed_message_ids': all_ids}
            session.add(source)

        # Update tracker with latest timestamp
        if latest_timestamp and not options.dry_run:
            self.tracker.update_last_read(source.url or f"imap-source-{source.id}", latest_timestamp)

        logger.info(
            "imap_source_complete",
            source_id=source.id,
            source_name=source.name,
            items_processed=items_count,
            total_cost=total_cost,
        )

        return {
            "success": True,
            "items_count": items_count,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost": total_cost,
        }

    def _process_youtube_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        options: FeedRunOptions,
        session: Session,
        fetcher=None,
    ) -> Dict[str, Any]:
        """Process a YouTube source (video or channel).

        For single videos: fetches transcript and summarizes.
        For channels: fetches transcripts for new videos since last read.
        """
        if fetcher is None:
            fetcher = get_fetcher('youtube')

        # Check if this is a channel URL - if so, use tracking like RSS
        is_channel = fetcher.is_channel_url(source.url)
        last_read = self.tracker.get_last_read(source.url) if is_channel else None

        # Get max_items from source config (default: 5 for channels)
        source_config = source.config or {}
        max_items = source_config.get('max_items', 5)

        # Fetch content (returns list for both videos and channels)
        content_items = fetcher.fetch(source.url, since=last_read, max_items=max_items)

        if not content_items:
            return {"success": True, "items_count": 0}

        # Apply content filter if configured
        if source.include_keywords or source.exclude_keywords:
            content_filter = ContentFilter(
                include_keywords=source.include_keywords,
                exclude_keywords=source.exclude_keywords,
                filter_mode=source.filter_mode or "both",
                use_regex=source.use_regex or False,
            )
            original_count = len(content_items)
            content_items = [
                item for item in content_items
                if content_filter.matches(
                    item.get("title", ""),
                    item.get("content", "")
                )
            ]
            if original_count != len(content_items):
                logger.info(
                    "content_filter_applied",
                    source_id=source.id,
                    source_name=source.name,
                    original_count=original_count,
                    remaining_count=len(content_items),
                    filtered_out=original_count - len(content_items),
                )
            if not content_items:
                return {"success": True, "items_count": 0}

        items_count = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0
        latest_timestamp = last_read

        digest_mode = feed.digest_mode or 'individual'

        if digest_mode == 'per_source' and len(content_items) > 1:
            # Consolidated mode: one digest per source
            result = self._process_consolidated_batch(
                articles=content_items,
                source=source,
                feed=feed,
                feed_run=feed_run,
                summarizer=summarizer,
                language=language,
                mode='per_source',
                options=options,
                session=session,
            )

            if result.get("success"):
                items_count = result.get("items_count", 0)
                total_tokens_in = result.get("tokens_in", 0)
                total_tokens_out = result.get("tokens_out", 0)
                total_cost = result.get("cost", 0.0)

                # Track latest timestamp from all items
                for item in content_items:
                    if item.get("published"):
                        try:
                            item_dt = datetime.fromisoformat(item["published"])
                            if latest_timestamp is None or item_dt > latest_timestamp:
                                latest_timestamp = item_dt
                        except Exception:
                            pass
        else:
            # Individual mode: one digest per video
            # Resolve prompt template once for all items
            template = None
            if feed.prompt_template_id:
                template = session.query(PromptTemplate).filter(
                    PromptTemplate.id == feed.prompt_template_id
                ).first()
            if not template:
                template = get_default_prompt_template(session, language=language)

            for content_data in content_items:
                try:
                    # Skip if digest already exists for this URL (fast pre-check)
                    video_url = content_data.get("url")
                    if video_url and self._digest_exists(video_url, session):
                        logger.info(f"Digest already exists for URL: {video_url}, skipping summarization")
                        # Still track timestamp for proper feed tracking
                        if content_data.get("published"):
                            try:
                                item_dt = datetime.fromisoformat(content_data["published"])
                                if latest_timestamp is None or item_dt > latest_timestamp:
                                    latest_timestamp = item_dt
                            except Exception:
                                pass
                        continue

                    # Build prompts from template
                    system_prompt, user_prompt = None, None
                    if template:
                        system_prompt, user_prompt = _build_prompts_from_template(template, content_data)

                    result = summarizer.summarize(
                        content_data,
                        language=language,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    )

                    if not options.dry_run:
                        digest = self._save_digest(
                            result, source, feed, feed_run, session
                        )
                        self._log_llm_usage(
                            result, source, feed, feed_run, digest, session
                        )

                    items_count += 1
                    total_tokens_in += result.get("model_info", {}).get("input_tokens", 0)
                    total_tokens_out += result.get("model_info", {}).get("output_tokens", 0)
                    total_cost += result.get("estimated_cost", 0.0)

                    # Track latest timestamp for channel sources
                    if content_data.get("published"):
                        try:
                            item_dt = datetime.fromisoformat(content_data["published"])
                            if latest_timestamp is None or item_dt > latest_timestamp:
                                latest_timestamp = item_dt
                        except Exception:
                            pass

                except Exception as e:
                    logger.warning(f"Failed to process video: {e}")

        # Update tracking for channel sources
        if is_channel and latest_timestamp and not options.dry_run:
            self.tracker.update_last_read(source.url, latest_timestamp)

        return {
            "success": True,
            "items_count": items_count,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost": total_cost,
        }

    def _process_rss_source(
        self,
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        options: FeedRunOptions,
        session: Session,
        fetcher=None,
    ) -> Dict[str, Any]:
        """Process an RSS source (individual or per_source mode)."""
        from reconly_core.services.settings_service import SettingsService

        # Get last read timestamp
        last_read = self.tracker.get_last_read(source.url)

        # Get max_items from source config
        source_config = source.config or {}
        max_items = source_config.get('max_items')

        # Get fetch_full_content setting
        settings = SettingsService(session)
        fetch_full_content = settings.get("fetch.rss.fetch_full_content")

        if fetcher is None:
            fetcher = get_fetcher('rss')
        articles = fetcher.fetch(
            source.url,
            since=last_read,
            max_items=max_items,
            fetch_full_content=fetch_full_content,
        )

        if not articles:
            return {"success": True, "items_count": 0}

        # Apply content filter if configured
        if source.include_keywords or source.exclude_keywords:
            content_filter = ContentFilter(
                include_keywords=source.include_keywords,
                exclude_keywords=source.exclude_keywords,
                filter_mode=source.filter_mode or "both",
                use_regex=source.use_regex or False,
            )
            original_count = len(articles)
            articles = [
                a for a in articles
                if content_filter.matches(a.get("title", ""), a.get("content", ""))
            ]
            logger.info(
                "content_filter_applied",
                source_id=source.id,
                source_name=source.name,
                original_count=original_count,
                remaining_count=len(articles),
                filtered_out=original_count - len(articles),
            )
            if not articles:
                return {"success": True, "items_count": 0}

        items_count = 0
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0
        latest_timestamp = last_read

        digest_mode = feed.digest_mode or 'individual'

        if digest_mode == 'per_source':
            # Consolidated mode: one digest per source
            result = self._process_consolidated_batch(
                articles=articles,
                source=source,
                feed=feed,
                feed_run=feed_run,
                summarizer=summarizer,
                language=language,
                mode='per_source',
                options=options,
                session=session,
            )

            if result.get("success"):
                items_count = result.get("items_count", 0)
                total_tokens_in = result.get("tokens_in", 0)
                total_tokens_out = result.get("tokens_out", 0)
                total_cost = result.get("cost", 0.0)

                # Track latest timestamp from all articles
                for article in articles:
                    if article.get("published"):
                        try:
                            article_dt = datetime.fromisoformat(article["published"])
                            if latest_timestamp is None or article_dt > latest_timestamp:
                                latest_timestamp = article_dt
                        except Exception:
                            pass
        else:
            # Individual mode: one digest per article (current behavior)
            # Resolve prompt template once for all articles
            template = None
            if feed.prompt_template_id:
                template = session.query(PromptTemplate).filter(
                    PromptTemplate.id == feed.prompt_template_id
                ).first()
            if not template:
                template = get_default_prompt_template(session, language=language)

            for article in articles:
                try:
                    # Skip if digest already exists for this URL (fast pre-check)
                    article_url = article.get("url")
                    if article_url and self._digest_exists(article_url, session):
                        logger.info(f"Digest already exists for URL: {article_url}, skipping summarization")
                        # Still track timestamp for proper feed tracking
                        if article.get("published"):
                            try:
                                article_dt = datetime.fromisoformat(article["published"])
                                if latest_timestamp is None or article_dt > latest_timestamp:
                                    latest_timestamp = article_dt
                            except Exception:
                                pass
                        continue

                    # Build prompts from template
                    system_prompt, user_prompt = None, None
                    if template:
                        system_prompt, user_prompt = _build_prompts_from_template(template, article)

                    result = summarizer.summarize(
                        article,
                        language=language,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                    )

                    if not options.dry_run:
                        digest = self._save_digest(
                            result, source, feed, feed_run, session
                        )
                        self._log_llm_usage(
                            result, source, feed, feed_run, digest, session
                        )

                    items_count += 1
                    total_tokens_in += result.get("model_info", {}).get("input_tokens", 0)
                    total_tokens_out += result.get("model_info", {}).get("output_tokens", 0)
                    total_cost += result.get("estimated_cost", 0.0)

                    # Track latest timestamp
                    if article.get("published"):
                        try:
                            article_dt = datetime.fromisoformat(article["published"])
                            if latest_timestamp is None or article_dt > latest_timestamp:
                                latest_timestamp = article_dt
                        except Exception:
                            pass

                except Exception as e:
                    logger.warning(f"Failed to process article: {e}")

        # Update tracking
        if latest_timestamp and not options.dry_run:
            self.tracker.update_last_read(source.url, latest_timestamp)

        return {
            "success": True,
            "items_count": items_count,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost": total_cost,
        }

    def _process_consolidated_batch(
        self,
        articles: List[Dict[str, Any]],
        source: Optional[Source],
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        language: str,
        mode: str,
        options: FeedRunOptions,
        session: Session,
        all_source_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a batch of articles into a single consolidated digest.

        Args:
            articles: List of article data dicts
            source: Source (for per_source mode, None for all_sources)
            feed: Feed being processed
            feed_run: Current FeedRun
            summarizer: Summarizer instance
            language: Target language
            mode: 'per_source' or 'all_sources'
            options: Run options
            session: Database session
            all_source_items: For all_sources mode, list of dicts with source_id, source_name, and item metadata
        """
        if not articles:
            return {"success": True, "items_count": 0}

        # Prepare articles for consolidated prompt
        prompt_articles = []
        for article in articles:
            prompt_article = {
                'title': article.get('title', 'Untitled'),
                'content': article.get('content', ''),
                'published_at': article.get('published'),
                'url': article.get('url'),  # Include URL for source linking
            }
            # For all_sources mode, include source name from all_source_items
            if mode == 'all_sources' and all_source_items:
                # Find matching item in all_source_items
                for item in all_source_items:
                    if item.get('url') == article.get('url'):
                        prompt_article['source_name'] = item.get('source_name')
                        break
            prompt_articles.append(prompt_article)

        # Generate consolidated prompt - check for custom template first
        source_name = source.name if source else feed.name

        # Check if feed has a custom prompt template for consolidated mode
        custom_template = None
        if feed.prompt_template_id:
            custom_template = session.query(PromptTemplate).filter(
                PromptTemplate.id == feed.prompt_template_id
            ).first()

        if custom_template and '{articles}' in custom_template.user_prompt_template:
            # Custom template designed for consolidated mode - use it
            # Format articles for inclusion in prompt
            formatted_articles = []
            for i, article in enumerate(prompt_articles, 1):
                formatted = _format_article_for_consolidation(
                    title=article.get('title', f'Article {i}'),
                    content=article.get('content', ''),
                    source_name=article.get('source_name'),
                    published_at=article.get('published_at'),
                    url=article.get('url')
                )
                formatted_articles.append(f"--- Article {i} ---\n{formatted}")
            articles_text = "\n\n".join(formatted_articles)

            # Count unique sources
            unique_sources = set(a.get('source_name') for a in prompt_articles if a.get('source_name'))

            # Format user prompt with consolidated variables
            user_prompt = custom_template.user_prompt_template.format(
                item_count=len(prompt_articles),
                source_count=len(unique_sources) or 1,
                articles=articles_text,
                target_length=custom_template.target_length,
            )

            prompts = {
                'system': custom_template.system_prompt,
                'user': user_prompt,
            }
            logger.info(
                "Using custom prompt template for consolidated digest",
                template_name=custom_template.name,
                target_length=custom_template.target_length,
            )
        else:
            # Use default consolidated template from database
            consolidated_template = get_default_consolidated_template(session, language=language)
            if consolidated_template:
                # Format articles for inclusion in prompt
                formatted_articles = []
                for i, article in enumerate(prompt_articles, 1):
                    formatted = _format_article_for_consolidation(
                        title=article.get('title', f'Article {i}'),
                        content=article.get('content', ''),
                        source_name=article.get('source_name'),
                        published_at=article.get('published_at'),
                        url=article.get('url')
                    )
                    formatted_articles.append(f"--- Article {i} ---\n{formatted}")
                articles_text = "\n\n".join(formatted_articles)

                # Count unique sources
                unique_sources = set(a.get('source_name') for a in prompt_articles if a.get('source_name'))

                # Format user prompt with consolidated variables
                user_prompt = consolidated_template.user_prompt_template.format(
                    item_count=len(prompt_articles),
                    source_count=len(unique_sources) or 1,
                    articles=articles_text,
                    target_length=consolidated_template.target_length,
                )

                prompts = {
                    'system': consolidated_template.system_prompt,
                    'user': user_prompt,
                }
            else:
                # Fallback: inline basic prompt if no template found
                formatted_articles = []
                for i, article in enumerate(prompt_articles, 1):
                    formatted = _format_article_for_consolidation(
                        title=article.get('title', f'Article {i}'),
                        content=article.get('content', ''),
                        source_name=article.get('source_name'),
                        published_at=article.get('published_at'),
                        url=article.get('url')
                    )
                    formatted_articles.append(f"--- Article {i} ---\n{formatted}")
                articles_text = "\n\n".join(formatted_articles)

                if language == 'de':
                    prompts = {
                        'system': "Du bist ein Content-Synthesizer. Erstelle zusammenhängende Briefings.",
                        'user': f"Erstelle ein zusammenfassendes Briefing aus den folgenden Artikeln.\n\n{articles_text}\n\nErstelle eine kohärente Zusammenfassung mit etwa 300 Wörtern.",
                    }
                else:
                    prompts = {
                        'system': "You are a content synthesizer. Create cohesive briefings.",
                        'user': f"Create a consolidated briefing from the following articles.\n\n{articles_text}\n\nCreate a cohesive summary of approximately 300 words.",
                    }

        # Create a synthetic content dict for summarization
        combined_content = prompts['user']  # Use the full prompt as content
        synthetic_url = _generate_consolidated_url(
            feed_id=feed.id,
            feed_run_id=feed_run.id,
            mode=mode,
            source_id=source.id if source else None,
        )

        # Generate title for consolidated digest
        if mode == 'per_source':
            title = f"Consolidated: {source_name} ({len(articles)} items)"
        else:
            source_count = len(set(item.get('source_name') for item in (all_source_items or []) if item.get('source_name')))
            title = f"Briefing: {feed.name} ({len(articles)} items from {source_count} sources)"

        # Use summarizer with custom prompt
        try:
            result = summarizer.summarize_with_prompt(
                content=combined_content,
                system_prompt=prompts['system'],
                title=title,
                url=synthetic_url,
                language=language,
            )
        except AttributeError:
            # Fallback if summarizer doesn't have summarize_with_prompt
            # Create a content_data dict and use regular summarize
            content_data = {
                'title': title,
                'content': combined_content,
                'url': synthetic_url,
                'source_type': 'consolidated',
            }
            result = summarizer.summarize(
                content_data,
                language=language,
                system_prompt=prompts['system'],
                user_prompt=prompts['user'],
            )
            result['url'] = synthetic_url

        if not options.dry_run:
            # Save consolidated digest
            digest = self._save_consolidated_digest(
                result=result,
                articles=articles,
                source=source,
                feed=feed,
                feed_run=feed_run,
                mode=mode,
                session=session,
                all_source_items=all_source_items,
            )

            if digest:
                self._log_llm_usage(
                    result, source, feed, feed_run, digest, session
                )

        return {
            "success": True,
            "items_count": len(articles),
            "tokens_in": result.get("model_info", {}).get("input_tokens", 0),
            "tokens_out": result.get("model_info", {}).get("output_tokens", 0),
            "cost": result.get("estimated_cost", 0.0),
        }

    def _store_source_content(
        self,
        source_item: DigestSourceItem,
        content: str,
        session: Session,
    ) -> Optional[SourceContent]:
        """
        Store source content for RAG embedding if enabled.

        Respects settings:
        - rag.source_content.enabled: Whether to store content
        - rag.source_content.max_length: Maximum content length to store

        Args:
            source_item: The DigestSourceItem to attach content to
            content: The original fetched content
            session: Database session

        Returns:
            Created SourceContent record, or None if disabled/skipped
        """
        from hashlib import sha256
        from reconly_core.services.settings_service import SettingsService

        try:
            settings = SettingsService(session)

            # Check if source content storage is enabled
            if not settings.get("rag.source_content.enabled"):
                return None

            # Skip if no content
            if not content:
                return None

            # Get max length setting
            max_length = settings.get("rag.source_content.max_length")

            # Truncate if necessary
            if len(content) > max_length:
                content = content[:max_length]
                logger.debug(f"Truncated content from {len(content)} to {max_length} chars")

            # Calculate hash for deduplication
            content_hash = sha256(content.encode('utf-8')).hexdigest()

            # Create SourceContent record
            source_content = SourceContent(
                digest_source_item_id=source_item.id,
                content=content,
                content_hash=content_hash,
                content_length=len(content),
                fetched_at=datetime.utcnow(),
            )
            session.add(source_content)
            return source_content

        except Exception as e:
            logger.error(f"Failed to store source content: {e}")
            return None

    def _save_consolidated_digest(
        self,
        result: Dict[str, Any],
        articles: List[Dict[str, Any]],
        source: Optional[Source],
        feed: Feed,
        feed_run: FeedRun,
        mode: str,
        session: Session,
        all_source_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Digest]:
        """Save a consolidated digest with provenance tracking."""
        url = result.get("url")
        if not url:
            logger.warning("No URL in result, skipping digest save")
            return None

        # Check for existing digest with same URL
        existing = session.query(Digest).filter(Digest.url == url).first()
        if existing:
            logger.info(f"Digest already exists for URL: {url}, skipping")
            return existing

        # Get provider info
        model_info = result.get("model_info", {})
        provider = model_info.get("provider", "unknown")
        if model_info.get("model_key"):
            provider = f"{provider}-{model_info['model_key']}"

        # Prefer full_content (scraped article) over content (RSS summary) for display
        digest_content = result.get("full_content") or result.get("content")

        # Create digest
        digest = Digest(
            url=result["url"],
            title=result.get("title"),
            content=digest_content,
            summary=result.get("summary"),
            source_type="consolidated",
            feed_url=None,
            feed_title=feed.name,
            author=None,
            published_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            provider=provider,
            language=result.get("summary_language", "de"),
            estimated_cost=result.get("estimated_cost", 0.0),
            consolidated_count=len(articles),
            user_id=feed.user_id,
            feed_run_id=feed_run.id,
            source_id=source.id if source else None,  # NULL for all_sources mode
        )

        session.add(digest)
        session.flush()  # Get ID

        # Create DigestSourceItem records for provenance tracking
        if mode == 'all_sources' and all_source_items:
            for item in all_source_items:
                published_at = None
                if item.get('published'):
                    try:
                        published_at = datetime.fromisoformat(item['published'])
                    except Exception:
                        pass

                source_item = DigestSourceItem(
                    digest_id=digest.id,
                    source_id=item.get('source_id'),
                    item_url=item.get('url', ''),
                    item_title=item.get('title'),
                    item_published_at=published_at,
                )
                session.add(source_item)
                session.flush()  # Get source_item.id for SourceContent FK

                # Store source content for RAG - prefer full_content if available
                content = item.get('full_content') or item.get('content', '')
                self._store_source_content(source_item, content, session)
        else:
            # per_source mode - all items from same source
            for article in articles:
                published_at = None
                if article.get('published'):
                    try:
                        published_at = datetime.fromisoformat(article['published'])
                    except Exception:
                        pass

                source_item = DigestSourceItem(
                    digest_id=digest.id,
                    source_id=source.id if source else None,
                    item_url=article.get('url', ''),
                    item_title=article.get('title'),
                    item_published_at=published_at,
                )
                session.add(source_item)
                session.flush()  # Get source_item.id for SourceContent FK

                # Store source content for RAG - prefer full_content if available
                content = article.get('full_content') or article.get('content', '')
                self._store_source_content(source_item, content, session)

        return digest

    def _collect_all_source_items(
        self,
        sources: List[Source],
        feed: Feed,
        feed_run: FeedRun,
        summarizer: BaseProvider,
        options: FeedRunOptions,
        session: Session,
    ) -> Dict[str, Any]:
        """
        Collect items from all sources and create a single consolidated digest.

        Used for all_sources digest mode.
        """
        all_articles = []
        all_source_items = []  # Track source info for each item
        sources_processed = 0
        sources_failed = 0
        sources_skipped = 0  # Skipped due to circuit breaker
        errors = []
        structured_errors = []
        language = self._get_language(feed, sources[0]) if sources else "de"

        if options.show_progress:
            print(f"📚 Collecting items from all {len(sources)} sources for consolidated briefing...")

        # Collect items from all RSS sources
        for idx, source in enumerate(sources, 1):
            try:
                if options.show_progress:
                    print(f"   📌 [{idx}/{len(sources)}] Fetching from {source.name}...")

                # Check circuit breaker before processing
                should_skip, skip_reason = self.circuit_breaker.should_skip(source)
                if should_skip:
                    sources_skipped += 1
                    logger.info(
                        "Source skipped due to circuit breaker",
                        source_id=source.id,
                        source_name=source.name,
                        reason=skip_reason,
                        health_status=source.health_status,
                    )
                    structured_errors.append({
                        "source_id": source.id,
                        "source_name": source.name,
                        "error_type": ERROR_TYPE_CIRCUIT_OPEN,
                        "message": skip_reason,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    if options.show_progress:
                        print(f"      ⏸️ Skipped (circuit open): {source.health_status}")
                    continue

                if source.type == "rss":
                    from reconly_core.services.settings_service import SettingsService

                    last_read = self.tracker.get_last_read(source.url)
                    source_config = source.config or {}
                    max_items = source_config.get('max_items')

                    # Get fetch_full_content setting
                    settings = SettingsService(session)
                    fetch_full_content = settings.get("fetch.rss.fetch_full_content")

                    fetcher = get_fetcher('rss')
                    articles = fetcher.fetch(
                        source.url,
                        since=last_read,
                        max_items=max_items,
                        fetch_full_content=fetch_full_content,
                    )

                    # Apply content filter if configured
                    if articles and (source.include_keywords or source.exclude_keywords):
                        content_filter = ContentFilter(
                            include_keywords=source.include_keywords,
                            exclude_keywords=source.exclude_keywords,
                            filter_mode=source.filter_mode or "both",
                            use_regex=source.use_regex or False,
                        )
                        original_count = len(articles)
                        articles = [
                            a for a in articles
                            if content_filter.matches(a.get("title", ""), a.get("content", ""))
                        ]
                        if original_count != len(articles):
                            logger.info(
                                "content_filter_applied",
                                source_id=source.id,
                                source_name=source.name,
                                original_count=original_count,
                                remaining_count=len(articles),
                                filtered_out=original_count - len(articles),
                            )

                    if articles:
                        for article in articles:
                            all_articles.append(article)
                            all_source_items.append({
                                'url': article.get('url'),
                                'title': article.get('title'),
                                'published': article.get('published'),
                                'content': article.get('content', ''),
                                'full_content': article.get('full_content'),
                                'source_id': source.id,
                                'source_name': source.name,
                            })

                        # Update tracking
                        if not options.dry_run:
                            latest = max(
                                (datetime.fromisoformat(a['published']) for a in articles if a.get('published')),
                                default=None
                            )
                            if latest:
                                self.tracker.update_last_read(source.url, latest)

                        if options.show_progress:
                            print(f"      ✅ {len(articles)} item(s) collected")
                    else:
                        if options.show_progress:
                            print("      ⏭️ No new items")

                    # Record success with circuit breaker
                    self.circuit_breaker.record_success(source, session)
                    sources_processed += 1
                else:
                    # Non-RSS sources not supported in all_sources mode yet
                    if options.show_progress:
                        print("      ⚠️ Skipping non-RSS source")
                    sources_processed += 1

            except Exception as e:
                sources_failed += 1
                error_msg = str(e)
                error_type = _detect_error_type(error_msg, ERROR_TYPE_FETCH)
                errors.append(f"{source.name}: {error_msg}")
                structured_errors.append({
                    "source_id": source.id,
                    "source_name": source.name,
                    "error_type": error_type,
                    "message": error_msg,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                # Record failure with circuit breaker
                self.circuit_breaker.record_failure(source, session, e)
                if options.show_progress:
                    print(f"      ❌ Error: {e}")

        if not all_articles:
            if options.show_progress:
                print("   ⏭️ No new items from any source")
            return {
                "success": True,
                "sources_processed": sources_processed,
                "sources_failed": sources_failed,
                "sources_skipped": sources_skipped,
                "items_count": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "errors": errors,
                "structured_errors": structured_errors,
            }

        # Cap articles at 50 to stay within LLM token limits
        # Prioritize newer articles, distributed fairly across sources
        MAX_ARTICLES = 50
        if len(all_articles) > MAX_ARTICLES:
            original_count = len(all_articles)

            # Group articles by source, sorted by published date (newest first)
            from collections import defaultdict
            articles_by_source = defaultdict(list)
            for i, article in enumerate(all_articles):
                source_name = all_source_items[i].get('source_name', 'unknown')
                articles_by_source[source_name].append((article, all_source_items[i]))

            # Sort each source's articles by published date (newest first)
            for source_name in articles_by_source:
                articles_by_source[source_name].sort(
                    key=lambda x: x[0].get('published', ''),
                    reverse=True
                )

            # Round-robin select from each source until we hit the cap
            selected_articles = []
            selected_source_items = []
            source_names = list(articles_by_source.keys())
            source_indices = {name: 0 for name in source_names}

            while len(selected_articles) < MAX_ARTICLES:
                added_this_round = False
                for source_name in source_names:
                    if len(selected_articles) >= MAX_ARTICLES:
                        break
                    idx = source_indices[source_name]
                    if idx < len(articles_by_source[source_name]):
                        article, source_item = articles_by_source[source_name][idx]
                        selected_articles.append(article)
                        selected_source_items.append(source_item)
                        source_indices[source_name] += 1
                        added_this_round = True
                if not added_this_round:
                    break

            all_articles = selected_articles
            all_source_items = selected_source_items

            if options.show_progress:
                print(f"   ⚠️ Capped from {original_count} to {len(all_articles)} articles (distributed across sources)")

        if options.show_progress:
            source_count = len(set(item['source_name'] for item in all_source_items))
            print(f"   📝 Creating consolidated briefing from {len(all_articles)} items across {source_count} sources...")

        # Process all items as one consolidated digest
        result = self._process_consolidated_batch(
            articles=all_articles,
            source=None,  # No single source for all_sources mode
            feed=feed,
            feed_run=feed_run,
            summarizer=summarizer,
            language=language,
            mode='all_sources',
            options=options,
            session=session,
            all_source_items=all_source_items,
        )

        if options.show_progress:
            if result.get("success"):
                print("   ✅ Consolidated briefing created")
            else:
                print("   ❌ Failed to create consolidated briefing")

        return {
            "success": result.get("success", False),
            "sources_processed": sources_processed,
            "sources_failed": sources_failed,
            "sources_skipped": sources_skipped,
            "items_count": result.get("items_count", 0),
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "cost": result.get("cost", 0.0),
            "errors": errors,
            "structured_errors": structured_errors,
        }

    def _digest_exists(self, url: str, session: Session) -> bool:
        """Check if a digest with this URL already exists (fast pre-check)."""
        if not url:
            return False
        return session.query(Digest).filter(Digest.url == url).first() is not None

    def _save_digest(
        self,
        result: Dict[str, Any],
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        session: Session,
    ) -> Optional[Digest]:
        """Save a digest to the database, or return existing if URL already processed."""
        url = result.get("url")
        if not url:
            logger.warning("No URL in result, skipping digest save")
            return None

        # Check for existing digest with same URL
        existing = session.query(Digest).filter(Digest.url == url).first()
        if existing:
            logger.info(f"Digest already exists for URL: {url}, skipping")
            return existing

        # Parse published_at
        published_at = None
        if result.get("published"):
            try:
                published_at = datetime.fromisoformat(result["published"])
            except Exception:
                pass

        # Get provider info
        model_info = result.get("model_info", {})
        provider = model_info.get("provider", "unknown")
        if model_info.get("model_key"):
            provider = f"{provider}-{model_info['model_key']}"

        # Prefer full_content (scraped article) over content (RSS summary) for display
        digest_content = result.get("full_content") or result.get("content")

        digest = Digest(
            url=result["url"],
            title=result.get("title"),
            content=digest_content,
            summary=result.get("summary"),
            source_type=result.get("source_type"),
            feed_url=result.get("feed_url"),
            feed_title=result.get("feed_title"),
            image_url=result.get("image_url"),
            author=result.get("author"),
            published_at=published_at,
            created_at=datetime.utcnow(),
            provider=provider,
            language=result.get("summary_language", "de"),
            estimated_cost=result.get("estimated_cost", 0.0),
            user_id=feed.user_id,
            feed_run_id=feed_run.id,
            source_id=source.id,
        )

        session.add(digest)
        session.flush()  # Get ID

        return digest

    def _log_llm_usage(
        self,
        result: Dict[str, Any],
        source: Source,
        feed: Feed,
        feed_run: FeedRun,
        digest: Digest,
        session: Session,
    ) -> None:
        """Log LLM usage for billing."""
        model_info = result.get("model_info", {})

        usage_log = LLMUsageLog(
            user_id=feed.user_id,
            feed_run_id=feed_run.id,
            digest_id=digest.id,
            provider=model_info.get("provider", "unknown"),
            model=model_info.get("model_key") or model_info.get("model", "unknown"),
            tokens_in=model_info.get("input_tokens", 0),
            tokens_out=model_info.get("output_tokens", 0),
            cost=result.get("estimated_cost", 0.0),
            request_type="summarize",
            success=True,
            timestamp=datetime.utcnow(),
        )

        session.add(usage_log)

    def _send_email_if_configured(
        self,
        feed: Feed,
        feed_run: FeedRun,
        session: Session,
    ) -> None:
        """Send digest email if email_recipients configured in output_config."""
        if not feed.output_config:
            return

        email_recipients = feed.output_config.get("email_recipients")
        if not email_recipients:
            return

        # Get digests created in this run
        digests = session.query(Digest).filter(
            Digest.feed_run_id == feed_run.id
        ).all()

        if not digests:
            logger.info("No digests to email", feed_id=feed.id, feed_run_id=feed_run.id)
            return

        # Convert to dicts for email template
        digest_dicts = [
            {
                "title": d.title,
                "summary": d.summary,
                "url": d.url,
                "source_type": d.source_type,
                "language": d.language or "en",
                "tags": d.tags or [],
                "consolidated_count": d.consolidated_count or 1,
                "image_url": d.image_url,
            }
            for d in digests
        ]

        # Get language from first digest or default
        language = digests[0].language if digests else "en"

        # Parse recipients (comma-separated)
        recipients = [r.strip() for r in email_recipients.split(",") if r.strip()]

        if not recipients:
            return

        try:
            email_service = EmailService()

            for recipient in recipients:
                success = email_service.send_digest_email(
                    to_email=recipient,
                    digests=digest_dicts,
                    language=language,
                )
                if success:
                    logger.info(
                        "Digest email sent",
                        recipient=recipient,
                        feed_id=feed.id,
                        digest_count=len(digests),
                    )
                else:
                    logger.warning(
                        "Failed to send digest email",
                        recipient=recipient,
                        feed_id=feed.id,
                    )

        except Exception as e:
            # Don't fail the feed run if email fails
            logger.error(
                "Error sending digest email",
                feed_id=feed.id,
                error=str(e),
            )

    def _send_webhook_if_configured(
        self,
        feed: Feed,
        feed_run: FeedRun,
        session: Session,
    ) -> None:
        """Send webhook POST if webhook_url configured in output_config."""
        if not feed.output_config:
            return

        webhook_url = feed.output_config.get("webhook_url")
        if not webhook_url:
            return

        # Get digests created in this run
        digests = session.query(Digest).filter(
            Digest.feed_run_id == feed_run.id
        ).all()

        # Build webhook payload
        payload = {
            "event": "feed.run_completed",
            "feed": {
                "id": feed.id,
                "name": feed.name,
            },
            "feed_run": {
                "id": feed_run.id,
                "status": feed_run.status,
                "started_at": feed_run.started_at.isoformat() if feed_run.started_at else None,
                "completed_at": feed_run.completed_at.isoformat() if feed_run.completed_at else None,
                "duration_seconds": feed_run.duration_seconds,
                "items_processed": feed_run.items_processed,
                "items_failed": feed_run.items_failed,
            },
            "digests": [
                {
                    "id": d.id,
                    "title": d.title,
                    "summary": d.summary,
                    "url": d.url,
                    "source_type": d.source_type,
                    "language": d.language or "en",
                    "tags": d.tags or [],
                    "consolidated_count": d.consolidated_count or 1,
                }
                for d in digests
            ],
            "digest_count": len(digests),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Generate signature for payload verification
        payload_json = str(payload)
        delivery_id = str(uuid.uuid4())

        # Get webhook secret if configured, otherwise use feed ID as fallback
        webhook_secret = feed.output_config.get("webhook_secret", f"reconly-feed-{feed.id}")
        signature = hmac.new(
            webhook_secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Reconly/1.0",
            "X-Reconly-Event": "feed.run_completed",
            "X-Reconly-Delivery": delivery_id,
            "X-Reconly-Signature": f"sha256={signature}",
            "X-Reconly-Timestamp": datetime.utcnow().isoformat(),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                logger.info(
                    "Webhook delivered successfully",
                    feed_id=feed.id,
                    feed_run_id=feed_run.id,
                    webhook_url=webhook_url,
                    status_code=response.status_code,
                    delivery_id=delivery_id,
                    digest_count=len(digests),
                )

        except httpx.TimeoutException:
            logger.warning(
                "Webhook delivery timed out",
                feed_id=feed.id,
                feed_run_id=feed_run.id,
                webhook_url=webhook_url,
                delivery_id=delivery_id,
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Webhook delivery failed with HTTP error",
                feed_id=feed.id,
                feed_run_id=feed_run.id,
                webhook_url=webhook_url,
                status_code=e.response.status_code,
                delivery_id=delivery_id,
            )

        except Exception as e:
            # Don't fail the feed run if webhook fails
            logger.error(
                "Error sending webhook",
                feed_id=feed.id,
                feed_run_id=feed_run.id,
                webhook_url=webhook_url,
                error=str(e),
                delivery_id=delivery_id,
            )

    def _export_if_configured(
        self,
        feed: Feed,
        feed_run: FeedRun,
        session: Session,
    ) -> List[Dict[str, Any]]:
        """Export digests to configured exporters after feed run completes.

        Reads per-feed export configuration from output_config.exports and
        triggers enabled exporters. Each exporter can have a path override
        or use the global path from SettingsService.

        Args:
            feed: The feed that was processed
            feed_run: The completed feed run
            session: Database session

        Returns:
            List of export error dicts for error_details (empty if all exports succeeded)

        Note:
            Export failures are logged and recorded in error_details but do not
            fail the feed run. The feed run status is set to 'completed_with_warnings'
            if any export errors occur.
        """
        import os

        export_errors = []

        if not feed.output_config:
            return export_errors

        exports_config = feed.output_config.get("exports")
        if not exports_config:
            return export_errors

        # Get digests created in this run
        digests = session.query(Digest).filter(
            Digest.feed_run_id == feed_run.id
        ).all()

        if not digests:
            logger.debug(
                "No digests to export",
                feed_id=feed.id,
                feed_run_id=feed_run.id,
            )
            return export_errors

        # Import exporter registry and settings service
        from reconly_core.exporters.registry import get_exporter_class, is_exporter_registered
        from reconly_core.services.settings_service import SettingsService

        settings_service = SettingsService(session)

        # Process each configured exporter
        for exporter_name, config in exports_config.items():
            # Skip if not enabled
            if not isinstance(config, dict):
                continue
            if not config.get("enabled", False):
                continue

            # Check if exporter exists
            if not is_exporter_registered(exporter_name):
                error_msg = f"Unknown exporter configured for auto-export: {exporter_name}"
                logger.warning(
                    "Unknown exporter configured for auto-export",
                    feed_id=feed.id,
                    exporter_name=exporter_name,
                )
                export_errors.append({
                    "exporter": exporter_name,
                    "error_type": ERROR_TYPE_EXPORT,
                    "message": error_msg,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                continue

            try:
                # Get exporter instance
                exporter_class = get_exporter_class(exporter_name)
                exporter = exporter_class()

                # Check if exporter supports direct export
                schema = exporter.get_config_schema()
                if not schema.supports_direct_export:
                    logger.debug(
                        "Exporter does not support direct export, skipping",
                        feed_id=feed.id,
                        exporter_name=exporter_name,
                    )
                    continue

                # Determine export path: per-feed override > global setting
                export_path = config.get("path")
                if not export_path:
                    # Get from global settings based on exporter
                    if exporter_name == "obsidian":
                        export_path = settings_service.get("export.obsidian.vault_path")
                    elif exporter_name == "json":
                        export_path = settings_service.get("export.json.export_path")
                    elif exporter_name == "csv":
                        export_path = settings_service.get("export.csv.export_path")

                if not export_path:
                    error_msg = f"No export path configured for {exporter_name}"
                    logger.warning(
                        "No export path configured for auto-export",
                        feed_id=feed.id,
                        exporter_name=exporter_name,
                    )
                    export_errors.append({
                        "exporter": exporter_name,
                        "error_type": ERROR_TYPE_EXPORT,
                        "message": error_msg,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    continue

                # Pre-validate export path exists and is writable
                if not os.path.exists(export_path):
                    error_msg = f"Export path does not exist: {export_path}"
                    logger.error(
                        "Export path does not exist",
                        feed_id=feed.id,
                        feed_run_id=feed_run.id,
                        exporter_name=exporter_name,
                        export_path=export_path,
                    )
                    export_errors.append({
                        "exporter": exporter_name,
                        "error_type": ERROR_TYPE_EXPORT,
                        "message": error_msg,
                        "path": export_path,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    continue

                if not os.access(export_path, os.W_OK):
                    error_msg = f"Export path is not writable: {export_path}"
                    logger.error(
                        "Export path is not writable",
                        feed_id=feed.id,
                        feed_run_id=feed_run.id,
                        exporter_name=exporter_name,
                        export_path=export_path,
                    )
                    export_errors.append({
                        "exporter": exporter_name,
                        "error_type": ERROR_TYPE_EXPORT,
                        "message": error_msg,
                        "path": export_path,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    continue

                # Build exporter config from global settings (filter out None values)
                exporter_config = {}
                if exporter_name == "obsidian":
                    exporter_config = {
                        k: v for k, v in {
                            "subfolder": settings_service.get("export.obsidian.subfolder"),
                            "filename_pattern": settings_service.get("export.obsidian.filename_pattern"),
                            "one_file_per_digest": settings_service.get("export.obsidian.one_file_per_digest"),
                        }.items() if v is not None
                    }
                elif exporter_name == "json":
                    exporter_config = {
                        k: v for k, v in {
                            "include_content": settings_service.get("export.json.include_content"),
                            "one_file_per_digest": settings_service.get("export.json.one_file_per_digest"),
                        }.items() if v is not None
                    }
                elif exporter_name == "csv":
                    exporter_config = {
                        k: v for k, v in {
                            "include_content": settings_service.get("export.csv.include_content"),
                            "one_file_per_digest": settings_service.get("export.csv.one_file_per_digest"),
                        }.items() if v is not None
                    }

                # Execute export
                result = exporter.export_to_path(
                    digests=digests,
                    base_path=export_path,
                    config=exporter_config,
                )

                if result.success:
                    logger.info(
                        "Auto-export completed successfully",
                        feed_id=feed.id,
                        feed_run_id=feed_run.id,
                        exporter_name=exporter_name,
                        files_written=result.files_written,
                        target_path=result.target_path,
                    )
                else:
                    error_msg = "; ".join(result.errors) if result.errors else "Export completed with errors"
                    logger.warning(
                        "Auto-export completed with errors",
                        feed_id=feed.id,
                        feed_run_id=feed_run.id,
                        exporter_name=exporter_name,
                        files_written=result.files_written,
                        errors=result.errors,
                    )
                    export_errors.append({
                        "exporter": exporter_name,
                        "error_type": ERROR_TYPE_EXPORT,
                        "message": error_msg,
                        "path": export_path,
                        "files_written": result.files_written,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            except Exception as e:
                # Don't fail the feed run if export fails, but record the error
                error_msg = str(e)
                logger.error(
                    "Error during auto-export",
                    feed_id=feed.id,
                    feed_run_id=feed_run.id,
                    exporter_name=exporter_name,
                    error=error_msg,
                )
                export_errors.append({
                    "exporter": exporter_name,
                    "error_type": ERROR_TYPE_EXPORT,
                    "message": error_msg,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return export_errors

    def _process_rag_for_feed_run(
        self,
        feed_run: FeedRun,
        session: Session,
        show_progress: bool = False,
    ) -> None:
        """Process RAG embeddings and graph relationships for digests in a feed run.

        Runs after feed completion to:
        1. Generate embeddings for new digests
        2. Generate embeddings for source content (original fetched content)
        3. Compute graph relationships

        Args:
            feed_run: The completed feed run
            session: Database session
            show_progress: Whether to print progress
        """
        import asyncio

        try:
            from reconly_core.rag import EmbeddingService
            from reconly_core.rag.embeddings import get_embedding_provider
            from reconly_core.rag.graph_service import GraphService

            digests = session.query(Digest).filter(
                Digest.feed_run_id == feed_run.id
            ).all()

            if not digests:
                return

            if show_progress:
                print(f"\n📊 Processing RAG for {len(digests)} digest(s)...")

            embedding_service = EmbeddingService(session)
            loop = asyncio.new_event_loop()
            try:
                # 1. Generate embeddings for digests
                for digest in digests:
                    if digest.embedding_status != 'completed':
                        loop.run_until_complete(
                            embedding_service.embed_digest(digest, update_status=True)
                        )
                session.commit()

                # 2. Generate embeddings for source content (if stored)
                # Use or_() to handle NULL status since NULL != 'completed' is NULL in SQL
                digest_ids = [d.id for d in digests]
                source_contents = session.query(SourceContent).join(
                    DigestSourceItem,
                    SourceContent.digest_source_item_id == DigestSourceItem.id
                ).filter(
                    DigestSourceItem.digest_id.in_(digest_ids),
                    or_(
                        SourceContent.embedding_status.is_(None),
                        SourceContent.embedding_status != 'completed'
                    )
                ).all()

                if source_contents:
                    if show_progress:
                        print(f"   📄 Embedding {len(source_contents)} source content record(s)...")

                    for source_content in source_contents:
                        try:
                            loop.run_until_complete(
                                embedding_service.embed_source_content(
                                    source_content, update_status=True
                                )
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to embed source content {source_content.id}: {e}"
                            )
                    session.commit()

                # 3. Compute graph relationships (if auto-compute enabled)
                from reconly_core.services.settings_service import SettingsService
                settings_service = SettingsService(session)

                auto_compute = settings_service.get("rag.graph.auto_compute")
                if auto_compute:
                    provider = get_embedding_provider(db=session)
                    default_chunk_source = settings_service.get("rag.source_content.default_chunk_source")
                    semantic_threshold = settings_service.get("rag.graph.semantic_threshold")
                    max_edges = settings_service.get("rag.graph.max_edges_per_digest")

                    graph_service = GraphService(
                        session,
                        provider,
                        semantic_threshold=semantic_threshold,
                        max_edges_per_digest=max_edges,
                        default_chunk_source=default_chunk_source,
                    )

                    for digest in digests:
                        loop.run_until_complete(
                            graph_service.compute_relationships(digest.id)
                        )
                    session.commit()
            finally:
                loop.close()

            if show_progress:
                print("   ✅ RAG processing complete")

        except ImportError as e:
            logger.warning(f"RAG processing skipped (missing dependency): {e}")
        except Exception as e:
            logger.error(f"RAG processing failed: {e}")
            # Don't fail the feed run

    def get_feed_runs(
        self,
        feed_id: int,
        limit: int = 10,
        status: Optional[str] = None
    ) -> List[FeedRun]:
        """
        Get feed run history.

        Args:
            feed_id: Feed ID
            limit: Maximum runs to return
            status: Filter by status

        Returns:
            List of FeedRun records
        """
        session = self._get_session()
        query = session.query(FeedRun).filter(FeedRun.feed_id == feed_id)

        if status:
            query = query.filter(FeedRun.status == status)

        return query.order_by(FeedRun.created_at.desc()).limit(limit).all()

    def get_usage_stats(
        self,
        user_id: Optional[int] = None,
        feed_id: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get LLM usage statistics.

        Args:
            user_id: Filter by user
            feed_id: Filter by feed
            since: Start date for stats

        Returns:
            Usage statistics dictionary
        """
        session = self._get_session()
        from sqlalchemy import func

        query = session.query(
            func.count(LLMUsageLog.id).label("total_requests"),
            func.sum(LLMUsageLog.tokens_in).label("total_tokens_in"),
            func.sum(LLMUsageLog.tokens_out).label("total_tokens_out"),
            func.sum(LLMUsageLog.cost).label("total_cost"),
        )

        if user_id:
            query = query.filter(LLMUsageLog.user_id == user_id)

        if feed_id:
            query = query.join(FeedRun).filter(FeedRun.feed_id == feed_id)

        if since:
            query = query.filter(LLMUsageLog.timestamp >= since)

        result = query.first()

        return {
            "total_requests": result.total_requests or 0,
            "total_tokens_in": result.total_tokens_in or 0,
            "total_tokens_out": result.total_tokens_out or 0,
            "total_cost": float(result.total_cost or 0.0),
        }
