"""Agent fetcher that uses research strategies for autonomous web research.

This fetcher integrates research strategies as content source types,
allowing sources with type 'agent' to conduct autonomous web research
on configured topics.

The fetcher supports optional AgentRun tracking when called with a database
session and source_id, recording execution status, timing, and results.

Configuration:
    The fetcher supports per-source configuration via the config dict:
    - config["research_strategy"]: Strategy to use (simple, comprehensive, deep)
    - config["search_provider"]: Override the global search provider for this source
    - config["report_format"]: Report citation format (comprehensive/deep only)
    - config["max_subtopics"]: Max subtopics for deep research (deep only)
    - If not set, uses the global agent.* settings

Strategy Details:
    - simple: ReAct loop with web search/fetch (default, 2 min timeout)
    - comprehensive: GPT Researcher comprehensive mode (5 min timeout)
    - deep: GPT Researcher deep research with subtopics (10 min timeout)
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from reconly_core.config_types import ConfigField
from reconly_core.utils.images import fetch_preview_image_from_urls
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema, ValidationResult
from reconly_core.fetchers.metadata import FetcherMetadata
from reconly_core.fetchers.registry import register_fetcher

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.agents import AgentResult, AgentSettings
    from reconly_core.agents.strategies.base import ResearchStrategy
    from reconly_core.database.models import AgentRun
    from reconly_core.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Strategy timeout values in seconds
# Note: Local LLMs (Ollama) need longer timeouts than cloud APIs
STRATEGY_TIMEOUTS: dict[str, int] = {
    "simple": 180,        # 3 minutes
    "comprehensive": 600,  # 10 minutes (increased for local LLMs)
    "deep": 900,          # 15 minutes
}

# Valid strategy names
VALID_STRATEGIES = frozenset(["simple", "comprehensive", "deep"])

# Valid report formats for GPT Researcher
VALID_REPORT_FORMATS = frozenset(["APA", "MLA", "CMS", "Harvard", "IEEE"])


@register_fetcher('agent')
class AgentFetcher(BaseFetcher):
    """Fetcher that uses research strategies to investigate topics.

    Unlike other fetchers that retrieve content from URLs, the agent fetcher
    uses an LLM with web tools to autonomously research a given topic.

    The `url` field in agent sources is repurposed as the research prompt/topic
    to investigate. The agent will search the web, fetch relevant articles,
    and synthesize findings into a structured research report.

    Strategies:
        - simple: ReAct loop with web search/fetch (default)
        - comprehensive: GPT Researcher comprehensive research
        - deep: GPT Researcher deep research with subtopics

    Configuration:
        max_iterations: Maximum research iterations (simple strategy only)
        research_strategy: Strategy to use (simple, comprehensive, deep)
        report_format: Citation format for comprehensive/deep (APA, MLA, etc.)
        max_subtopics: Max subtopics for deep research (1-10)

    Example:
        >>> fetcher = AgentFetcher()
        >>> # Simple strategy (default)
        >>> results = fetcher.fetch("Latest developments in AI safety research")
        >>> # Comprehensive strategy
        >>> results = fetcher.fetch("AI safety research", config={"research_strategy": "comprehensive"})
        >>> print(results[0]['title'])  # Agent-generated title
        >>> print(results[0]['content'])  # Research findings in markdown
    """

    metadata = FetcherMetadata(
        name='agent',
        display_name='AI Agent',
        description='AI-powered content research and gathering',
        icon='mdi:robot',
        url_schemes=['agent'],
        supports_incremental=False,
        supports_validation=False,
        supports_test_fetch=False,
    )

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> list[dict[str, Any]]:
        """
        Run research agent and return findings.

        For agent sources, the `url` field is repurposed as the research
        prompt/topic to investigate. The `since` and `max_items` parameters
        are ignored since agent research produces a single synthesized result.

        Args:
            url: The research prompt/topic (not a URL for agent sources)
            since: Ignored for agent sources
            max_items: Ignored for agent sources
            **kwargs: May contain:
                - config: Dict with agent settings (max_iterations)
                - db: SQLAlchemy Session for tracking AgentRun records
                - source_id: Source ID for AgentRun tracking
                - trace_id: Optional trace ID for log correlation

        Returns:
            List containing single dict with research findings:
            - url: Synthetic URL (agent://topic-summary)
            - title: Agent-generated title for the research
            - content: Research findings in markdown format
            - source_type: 'agent'
            - metadata: Dict with iterations, tool_calls, sources, tokens
            - agent_run_id: ID of the AgentRun record (if db tracking enabled)

        Raises:
            Exception: If agent settings are misconfigured or research fails
        """
        config = kwargs.get('config', {})
        db: Optional["Session"] = kwargs.get('db')
        source_id: Optional[int] = kwargs.get('source_id')
        trace_id: Optional[str] = kwargs.get('trace_id')

        logger.info(
            "Starting agent research",
            extra={"prompt": url[:100], "config": config, "source_id": source_id},
        )

        # Run async agent in sync context with optional tracking
        result = asyncio.run(self._run_agent(
            prompt=url,
            config=config,
            db=db,
            source_id=source_id,
            trace_id=trace_id,
        ))

        logger.info(
            "Agent research complete",
            extra={
                "title": result['title'],
                "iterations": result['metadata'].get('iterations', 0),
                "sources_count": len(result['metadata'].get('sources', [])),
                "agent_run_id": result.get('agent_run_id'),
            },
        )

        return [result]

    async def _run_agent(
        self,
        prompt: str,
        config: dict,
        db: Optional["Session"] = None,
        source_id: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run the research strategy asynchronously with optional tracking.

        Args:
            prompt: The research topic to investigate
            config: Configuration dict with optional settings:
                - research_strategy: Strategy name (simple, comprehensive, deep)
                - max_iterations: Max iterations for simple strategy
                - search_provider: Override the global search provider
                - report_format: Report format for comprehensive/deep
                - max_subtopics: Max subtopics for deep research
            db: Optional SQLAlchemy Session for AgentRun tracking
            source_id: Source ID for AgentRun tracking (required if db provided)
            trace_id: Optional trace ID for log correlation

        Returns:
            Dict formatted as a fetcher result with metadata
        """
        from reconly_core.agents.strategies import get_strategy
        from reconly_core.providers.factory import get_summarizer

        agent_run: Optional["AgentRun"] = None
        agent_run_id: Optional[int] = None

        # Determine which strategy to use
        strategy_name = config.get('research_strategy', 'simple')

        # Create AgentRun record if tracking is enabled
        if db is not None and source_id is not None:
            agent_run = self._create_agent_run(
                db, source_id, prompt, trace_id, strategy_name
            )
            agent_run_id = agent_run.id

        try:
            # Get agent settings from environment/defaults
            agent_settings = self._get_agent_settings()

            # Apply per-source overrides from config
            source_override = config.get('search_provider')
            if source_override:
                agent_settings.search_provider = source_override

            # Apply GPT Researcher-specific overrides
            if strategy_name in ('comprehensive', 'deep'):
                report_format = config.get('report_format')
                if report_format:
                    agent_settings.gptr_report_format = report_format

                max_subtopics = config.get('max_subtopics')
                if max_subtopics is not None:
                    agent_settings.gptr_max_subtopics = int(max_subtopics)

            # Log strategy and provider being used
            logger.info(
                "Agent research starting",
                extra={
                    "strategy": strategy_name,
                    "search_provider": agent_settings.search_provider,
                    "source_override": source_override is not None,
                    "source_id": source_id,
                },
            )

            agent_settings.validate()

            # Get summarizer (uses default provider from settings)
            # Pass db to read UI-configured provider/model from database
            summarizer = get_summarizer(enable_fallback=True, db=db)

            # Get embedding settings for GPT Researcher
            embedding_config = self._get_embedding_config(db)

            # Configure max iterations from config or settings default
            max_iterations = config.get(
                'max_iterations',
                agent_settings.default_max_iterations
            )

            # Update status to running
            if agent_run is not None:
                agent_run.status = 'running'
                agent_run.started_at = datetime.utcnow()
                db.commit()

            # Get the appropriate strategy
            strategy = get_strategy(
                strategy_name,
                summarizer=summarizer,
                embedding_config=embedding_config,
            )

            # Get timeout for this strategy
            timeout = STRATEGY_TIMEOUTS.get(strategy_name, 120)

            logger.info(
                "Running research strategy",
                extra={
                    "strategy": strategy_name,
                    "timeout_seconds": timeout,
                    "max_iterations": max_iterations,
                },
            )

            # Run the strategy with timeout
            result = await asyncio.wait_for(
                strategy.research(prompt, agent_settings, max_iterations),
                timeout=timeout,
            )

            # Update AgentRun with success
            if agent_run is not None:
                self._update_agent_run_success(
                    db, agent_run, result, strategy, strategy_name, summarizer
                )

            # Format as fetcher result
            formatted = self._format_result(prompt, result, strategy_name, summarizer, db)
            if agent_run_id is not None:
                formatted['agent_run_id'] = agent_run_id
            return formatted

        except asyncio.TimeoutError:
            timeout = STRATEGY_TIMEOUTS.get(strategy_name, 120)
            error_msg = (
                f"Research strategy '{strategy_name}' timed out after {timeout} seconds"
            )
            logger.error(
                "Agent research timeout",
                extra={
                    "strategy": strategy_name,
                    "timeout_seconds": timeout,
                    "source_id": source_id,
                },
            )
            if agent_run is not None:
                self._update_agent_run_failure(db, agent_run, error_msg)
            raise TimeoutError(error_msg)

        except ImportError as e:
            # Handle missing gpt-researcher dependency
            error_msg = str(e)
            logger.error(
                "Agent research import error",
                extra={
                    "strategy": strategy_name,
                    "error": error_msg,
                    "source_id": source_id,
                },
            )
            if agent_run is not None:
                self._update_agent_run_failure(db, agent_run, error_msg)
            raise

        except Exception as e:
            # Update AgentRun with failure
            if agent_run is not None:
                self._update_agent_run_failure(db, agent_run, str(e))
            raise

    def _create_agent_run(
        self,
        db: "Session",
        source_id: int,
        prompt: str,
        trace_id: Optional[str] = None,
        strategy_name: str = "simple",
    ) -> "AgentRun":
        """Create a new AgentRun record in pending state.

        Args:
            db: SQLAlchemy Session
            source_id: Source ID for the agent run
            prompt: Research prompt
            trace_id: Optional trace ID for log correlation
            strategy_name: Name of the research strategy being used

        Returns:
            Created AgentRun instance
        """
        from reconly_core.database.models import AgentRun

        agent_run = AgentRun(
            source_id=source_id,
            prompt=prompt,
            status='pending',
            trace_id=trace_id or str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            # Store strategy in extra_data (JSON field)
            extra_data={"research_strategy": strategy_name},
        )
        db.add(agent_run)
        db.commit()

        logger.info(
            "Created AgentRun record",
            extra={
                "agent_run_id": agent_run.id,
                "source_id": source_id,
                "trace_id": agent_run.trace_id,
                "strategy": strategy_name,
            },
        )

        return agent_run

    def _update_agent_run_success(
        self,
        db: "Session",
        agent_run: "AgentRun",
        result: "AgentResult",
        strategy: "ResearchStrategy",
        strategy_name: str,
        summarizer: "BaseProvider",
    ) -> None:
        """Update AgentRun record on successful completion.

        Args:
            db: SQLAlchemy Session
            agent_run: AgentRun record to update
            result: AgentResult from research
            strategy: ResearchStrategy instance used
            strategy_name: Name of the strategy (simple, comprehensive, deep)
            summarizer: LLM provider instance for cost estimation
        """
        agent_run.status = 'completed'
        agent_run.completed_at = datetime.utcnow()
        agent_run.iterations = result.iterations
        agent_run.tool_calls = result.tool_calls
        agent_run.sources_consulted = result.sources
        agent_run.result_title = result.title
        agent_run.result_content = result.content

        # Token tracking: SimpleStrategy exposes tokens via the inner agent
        # GPTResearcherStrategy does not track tokens (handled by gpt-researcher internally)
        tokens_in = 0
        tokens_out = 0

        if strategy_name == "simple":
            # SimpleStrategy wraps ResearchAgent which tracks tokens
            # We need to get them from the last agent run
            # Note: For now, we don't have direct access to the agent's token counts
            # since the strategy wraps it. This could be enhanced in future.
            pass

        agent_run.tokens_in = tokens_in
        agent_run.tokens_out = tokens_out

        # Estimate cost using summarizer's method (OSS edition returns 0.0)
        # For comprehensive/deep strategies, use the strategy's estimate
        if strategy_name in ('comprehensive', 'deep'):
            model_info = summarizer.get_model_info() if summarizer else {}
            model = model_info.get('model', '')
            agent_run.estimated_cost = strategy.estimate_cost_usd(model)
        else:
            agent_run.estimated_cost = summarizer.estimate_cost(tokens_in + tokens_out)

        # Update metadata with strategy-specific information
        metadata = agent_run.extra_data or {}
        metadata['research_strategy'] = strategy_name
        metadata.update(self._extract_gptr_metadata(result.tool_calls, strategy_name))

        agent_run.extra_data = metadata

        db.commit()

        logger.info(
            "AgentRun completed successfully",
            extra={
                "agent_run_id": agent_run.id,
                "strategy": strategy_name,
                "iterations": result.iterations,
                "sources_count": len(result.sources),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "estimated_cost": agent_run.estimated_cost,
            },
        )

    def _update_agent_run_failure(
        self,
        db: "Session",
        agent_run: "AgentRun",
        error_message: str,
    ) -> None:
        """Update AgentRun record on failure.

        Args:
            db: SQLAlchemy Session
            agent_run: AgentRun record to update
            error_message: Error message to record
        """
        agent_run.status = 'failed'
        agent_run.completed_at = datetime.utcnow()
        agent_run.error_log = error_message
        db.commit()

        logger.error(
            "AgentRun failed",
            extra={
                "agent_run_id": agent_run.id,
                "error": error_message,
            },
        )

    def _get_agent_settings(self) -> "AgentSettings":
        """Get agent settings from environment variables.

        Returns:
            AgentSettings instance configured from environment
        """
        from reconly_core.agents import AgentSettings

        return AgentSettings(
            search_provider=os.getenv('AGENT_SEARCH_PROVIDER', 'duckduckgo'),
            searxng_url=os.getenv('SEARXNG_URL', 'http://localhost:8080'),
            tavily_api_key=os.getenv('TAVILY_API_KEY'),
            max_search_results=int(os.getenv('AGENT_MAX_SEARCH_RESULTS', '10')),
            default_max_iterations=int(os.getenv('AGENT_DEFAULT_MAX_ITERATIONS', '5')),
            gptr_report_format=os.getenv('AGENT_GPTR_REPORT_FORMAT', 'APA'),
            gptr_max_subtopics=int(os.getenv('AGENT_GPTR_MAX_SUBTOPICS', '3')),
        )

    def _get_embedding_config(self, db: Optional["Session"]) -> dict[str, str]:
        """Get embedding configuration from settings service.

        Args:
            db: SQLAlchemy Session for reading settings

        Returns:
            Dict with 'provider' and 'model' keys
        """
        config = {"provider": "ollama", "model": "bge-m3"}  # Defaults

        if db is not None:
            try:
                from reconly_core.services.settings_service import SettingsService
                service = SettingsService(db)
                provider = service.get("embedding.provider")
                model = service.get("embedding.model")
                if provider:
                    config["provider"] = provider
                if model:
                    config["model"] = model
            except Exception as e:
                logger.warning(
                    "Failed to get embedding config from settings",
                    extra={"error": str(e)},
                )

        return config

    def _extract_gptr_metadata(
        self,
        tool_calls: list[dict],
        strategy_name: str,
    ) -> dict[str, object]:
        """Extract GPT Researcher-specific metadata from tool calls.

        Args:
            tool_calls: List of tool call records from the research result
            strategy_name: Name of the strategy (only extracts for comprehensive/deep)

        Returns:
            Dict with subtopics_count, context_items if present
        """
        metadata: dict[str, object] = {}
        if strategy_name not in ('comprehensive', 'deep'):
            return metadata

        for tool_call in tool_calls:
            tool_name = tool_call.get('tool')
            if tool_name == 'gpt_researcher_subtopics':
                metadata['subtopics_count'] = tool_call.get('input', {}).get('count', 0)
            elif tool_name == 'gpt_researcher_context':
                metadata['context_items'] = tool_call.get('input', {}).get('context_items', 0)

        return metadata

    def _generate_unique_agent_url(
        self,
        prompt: str,
        db: Optional["Session"] = None,
    ) -> str:
        """Generate a unique agent URL with date prefix and sequence fallback.

        Creates URLs in the format:
        - agent://2026-01-24/topic-name (first run of the day)
        - agent://2026-01-24-2/topic-name (second run same day)
        - agent://2026-01-24-3/topic-name (third run same day)

        Args:
            prompt: The research prompt to include in the URL
            db: Optional database session for checking existing URLs

        Returns:
            Unique synthetic URL for the agent digest
        """
        # Sanitize prompt for URL
        safe_prompt = prompt[:50].replace(' ', '-').replace('/', '-')
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Base URL without sequence number
        base_url = f"agent://{today}/{safe_prompt}"

        # If no database session, return base URL (can't check for duplicates)
        if db is None:
            return base_url

        # Check if base URL already exists
        from reconly_core.database.models import Digest

        existing = db.query(Digest).filter(Digest.url == base_url).first()
        if not existing:
            return base_url

        # Find next available sequence number
        sequence = 2
        while sequence <= 100:  # Safety limit
            sequenced_url = f"agent://{today}-{sequence}/{safe_prompt}"
            existing = db.query(Digest).filter(Digest.url == sequenced_url).first()
            if not existing:
                return sequenced_url
            sequence += 1

        # Fallback: use timestamp if too many runs (shouldn't happen in practice)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
        return f"agent://{timestamp}/{safe_prompt}"

    def _format_result(
        self,
        prompt: str,
        result: "AgentResult",
        strategy_name: str,
        summarizer: "BaseProvider",
        db: Optional["Session"] = None,
    ) -> dict[str, object]:
        """Format strategy result as fetcher output.

        Args:
            prompt: Original research prompt
            result: AgentResult from research strategy
            strategy_name: Name of the strategy used (simple, comprehensive, deep)
            summarizer: LLM provider instance (for model info)
            db: Optional database session for checking existing URLs

        Returns:
            Dict with url, title, content, source_type, and metadata
        """
        # Create synthetic URL from prompt with date prefix for uniqueness
        # Format: agent://YYYY-MM-DD/topic-name or agent://YYYY-MM-DD-N/topic-name
        synthetic_url = self._generate_unique_agent_url(prompt, db)

        metadata: dict[str, object] = {
            'iterations': result.iterations,
            'tool_calls': result.tool_calls,
            'sources': result.sources,
            'research_strategy': strategy_name,
        }

        # Add model info if available
        if summarizer:
            model_info = summarizer.get_model_info()
            metadata['llm_provider'] = model_info.get('provider', 'unknown')
            metadata['llm_model'] = model_info.get('model', 'unknown')

        # Extract GPT Researcher-specific metadata
        metadata.update(self._extract_gptr_metadata(result.tool_calls, strategy_name))

        # Extract preview image from source URLs (og:image)
        image_url = fetch_preview_image_from_urls(result.sources)

        return {
            'url': synthetic_url,
            'title': result.title,
            'content': result.content,
            'source_type': 'agent',
            'image_url': image_url,
            'metadata': metadata,
        }

    def get_source_type(self) -> str:
        """Return 'agent' as the source type identifier."""
        return 'agent'

    def get_description(self) -> str:
        """Return human-readable description for UI display."""
        return 'AI Research Agent (web search + content analysis)'

    def get_config_schema(self) -> FetcherConfigSchema:
        """Return configuration schema for agent sources.

        Fields include:
        - research_strategy: Strategy to use (simple, comprehensive, deep)
        - max_iterations: Max iterations for simple strategy
        - search_provider: Override global search provider
        - report_format: Citation format for comprehensive/deep
        - max_subtopics: Max subtopics for deep research
        """
        return FetcherConfigSchema(
            fields=[
                ConfigField(
                    key="research_strategy",
                    type="select",
                    label="Research Strategy",
                    description=(
                        "Strategy for conducting research. "
                        "'simple' uses a ReAct loop (fast, 2 min timeout). "
                        "'comprehensive' uses GPT Researcher (thorough, 5 min timeout). "
                        "'deep' uses GPT Researcher with subtopics (most thorough, 10 min timeout)."
                    ),
                    default="simple",
                    editable=True,
                    required=False,
                    # Note: options_from could be used for dynamic options, but for now
                    # we rely on validation to enforce valid values
                ),
                ConfigField(
                    key="max_iterations",
                    type="integer",
                    label="Max Iterations",
                    description=(
                        "Maximum number of research iterations (simple strategy only). "
                        "Higher values allow deeper research but take longer."
                    ),
                    default=5,
                    editable=True,
                    required=False,
                ),
                ConfigField(
                    key="search_provider",
                    type="select",
                    label="Search Provider",
                    description=(
                        "Search provider override for this source. "
                        "Leave empty to use global setting."
                    ),
                    default=None,
                    editable=True,
                    required=False,
                ),
                ConfigField(
                    key="report_format",
                    type="select",
                    label="Report Format",
                    description=(
                        "Citation format for research reports "
                        "(comprehensive and deep strategies only). "
                        "Options: APA, MLA, CMS, Harvard, IEEE."
                    ),
                    default="APA",
                    editable=True,
                    required=False,
                ),
                ConfigField(
                    key="max_subtopics",
                    type="integer",
                    label="Max Subtopics",
                    description=(
                        "Maximum number of subtopics to explore "
                        "(comprehensive and deep strategies only). "
                        "Range: 1-10."
                    ),
                    default=3,
                    editable=True,
                    required=False,
                ),
            ]
        )

    def validate(
        self,
        url: str,
        config: Optional[dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate agent configuration and prompt.

        For agent sources, the `url` field is repurposed as the research
        prompt/topic. This validation checks:
        - Prompt is not empty
        - Prompt length is reasonable
        - Research strategy is valid
        - Strategy-specific options are valid
        - GPT Researcher is available (for comprehensive/deep strategies)
        - Agent settings are valid (if test_fetch=True)
        - Search provider is configured (if test_fetch=True)

        Args:
            url: The research prompt/topic (not a URL for agent sources)
            config: Configuration dictionary with optional settings:
                - research_strategy: Strategy to use (simple, comprehensive, deep)
                - max_iterations: Max iterations for simple strategy
                - search_provider: Override global search provider
                - report_format: Report format for comprehensive/deep
                - max_subtopics: Max subtopics for deep research
            test_fetch: If True, validate agent settings can be loaded
            timeout: Not used for agent validation

        Returns:
            ValidationResult with:
            - valid: True if configuration is valid
            - errors: List of error messages
            - warnings: List of warning messages
            - url_type: 'agent'
        """
        result = ValidationResult()
        result.url_type = 'agent'
        config = config or {}

        # For agent sources, 'url' is actually the research prompt
        prompt = url

        # Validate prompt is not empty
        if not prompt or not prompt.strip():
            result.add_error(
                "Research prompt is required. "
                "Enter a topic or question for the agent to investigate."
            )
            return result

        # Validate prompt length
        min_length = 10
        max_length = 5000

        if len(prompt) < min_length:
            result.add_error(
                f"Research prompt is too short (minimum {min_length} characters). "
                "Provide a more detailed topic for better research results."
            )
            return result

        if len(prompt) > max_length:
            result.add_error(
                f"Research prompt exceeds maximum length of {max_length} characters."
            )
            return result

        # Validate research_strategy if provided
        strategy = config.get('research_strategy', 'simple')
        result = self._validate_research_strategy(result, strategy)

        # Validate max_iterations if provided (only relevant for simple strategy)
        max_iterations = config.get('max_iterations')
        if max_iterations is not None:
            try:
                max_iter = int(max_iterations)
                if max_iter < 1:
                    result.add_error(
                        "max_iterations must be at least 1."
                    )
                elif max_iter > 20:
                    result.add_warning(
                        f"max_iterations={max_iter} is very high. "
                        "This may result in long execution times and high costs."
                    )
            except (ValueError, TypeError):
                result.add_error(
                    f"Invalid max_iterations value: {max_iterations}. "
                    "Must be an integer."
                )

        # Validate report_format if provided (for comprehensive/deep strategies)
        report_format = config.get('report_format')
        if report_format is not None:
            if report_format not in VALID_REPORT_FORMATS:
                result.add_error(
                    f"Invalid report_format '{report_format}'. "
                    f"Valid formats: {', '.join(sorted(VALID_REPORT_FORMATS))}"
                )
            elif strategy == 'simple':
                result.add_warning(
                    "report_format is ignored for the 'simple' strategy. "
                    "Use 'comprehensive' or 'deep' strategy for formatted reports."
                )

        # Validate max_subtopics if provided (for comprehensive/deep strategies)
        max_subtopics = config.get('max_subtopics')
        if max_subtopics is not None:
            try:
                subtopics = int(max_subtopics)
                if subtopics < 1 or subtopics > 10:
                    result.add_error(
                        f"max_subtopics must be between 1 and 10, got {subtopics}."
                    )
                elif strategy == 'simple':
                    result.add_warning(
                        "max_subtopics is ignored for the 'simple' strategy. "
                        "Use 'comprehensive' or 'deep' strategy for subtopic exploration."
                    )
            except (ValueError, TypeError):
                result.add_error(
                    f"Invalid max_subtopics value: {max_subtopics}. "
                    "Must be an integer."
                )

        # Validate search_provider override if provided
        search_provider = config.get('search_provider')
        if search_provider:
            result = self._validate_search_provider(result, search_provider)

        # If test_fetch is enabled, validate agent settings
        if test_fetch and result.valid:
            result = self._validate_agent_settings(result, config)

        return result

    def _validate_research_strategy(
        self,
        result: ValidationResult,
        strategy: str,
    ) -> ValidationResult:
        """
        Validate research strategy and check dependencies.

        Args:
            result: ValidationResult to update
            strategy: The research strategy name to validate

        Returns:
            Updated ValidationResult
        """
        # Validate strategy name
        if strategy not in VALID_STRATEGIES:
            result.add_error(
                f"Invalid research_strategy '{strategy}'. "
                f"Valid strategies: {', '.join(sorted(VALID_STRATEGIES))}"
            )
            return result

        # Check if GPT Researcher is available for comprehensive/deep strategies
        if strategy in ('comprehensive', 'deep'):
            import importlib.util
            if importlib.util.find_spec("gpt_researcher") is None:
                result.add_warning(
                    f"The '{strategy}' strategy requires gpt-researcher which is not installed. "
                    "Install with: pip install reconly-core[research]. "
                    "Falling back to 'simple' strategy will occur at runtime."
                )

            # Add cost/time warnings for comprehensive/deep strategies
            if strategy == 'comprehensive':
                result.add_warning(
                    "The 'comprehensive' strategy takes 3-5 minutes and may incur higher LLM costs."
                )
            elif strategy == 'deep':
                result.add_warning(
                    "The 'deep' strategy takes 5-10 minutes and incurs the highest LLM costs."
                )

        return result

    def _validate_search_provider(
        self,
        result: ValidationResult,
        provider: str,
    ) -> ValidationResult:
        """
        Validate that a search provider is valid and properly configured.

        Args:
            result: ValidationResult to update
            provider: The search provider name to validate

        Returns:
            Updated ValidationResult
        """
        from reconly_core.agents.search import SEARCH_PROVIDERS

        # Check if provider is valid
        if provider not in SEARCH_PROVIDERS:
            available = ", ".join(sorted(SEARCH_PROVIDERS.keys()))
            result.add_error(
                f"Invalid search provider '{provider}'. "
                f"Available providers: {available}"
            )
            return result

        # Validate provider-specific requirements
        if provider == "tavily":
            tavily_key = os.getenv("TAVILY_API_KEY")
            if not tavily_key:
                result.add_error(
                    "Tavily search provider requires TAVILY_API_KEY environment variable. "
                    "Get your API key at https://tavily.com/"
                )

        if provider == "searxng":
            searxng_url = os.getenv("SEARXNG_URL")
            if not searxng_url:
                result.add_warning(
                    "SearXNG URL is not configured. "
                    "Using default: http://localhost:8080"
                )

        return result

    def _validate_agent_settings(
        self,
        result: ValidationResult,
        config: Optional[dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate agent settings can be loaded and are configured.

        Note: Provider-specific validation (API keys, URLs) is handled by
        _validate_search_provider() which is called earlier in the validation flow.
        This method focuses on loading settings and verifying LLM availability.

        Args:
            result: ValidationResult to update
            config: Optional config dict with potential search_provider override

        Returns:
            Updated ValidationResult
        """
        config = config or {}

        try:
            agent_settings = self._get_agent_settings()

            # Apply per-source search_provider override if specified
            source_override = config.get('search_provider')
            if source_override:
                agent_settings.search_provider = source_override

            # Validate settings (catches any issues not caught by _validate_search_provider)
            try:
                agent_settings.validate()
            except Exception as e:
                result.add_error(f"Agent settings validation failed: {str(e)}")

            # Check if summarizer is available
            try:
                from reconly_core.providers.factory import get_summarizer
                summarizer = get_summarizer(enable_fallback=True)
                if not summarizer.is_available():
                    result.add_warning(
                        "No LLM provider is currently available. "
                        "Agent research requires a working LLM provider."
                    )
            except Exception as e:
                result.add_warning(
                    f"Could not verify LLM availability: {str(e)}"
                )

        except Exception as e:
            result.add_error(f"Failed to load agent settings: {str(e)}")

        return result

    def _is_valid_scheme(self, url: str) -> bool:
        """
        Check if URL has a valid scheme for agent fetcher.

        Agent fetcher accepts any string as the 'URL' field since
        it's repurposed as the research prompt.

        Args:
            url: URL/prompt to check

        Returns:
            True (always valid for agent fetcher)
        """
        # Agent sources use 'url' field as research prompt, so any string is valid
        return True
