"""Agent fetcher that uses ResearchAgent for autonomous web research.

This fetcher integrates the ResearchAgent as a content source type,
allowing sources with type 'agent' to conduct autonomous web research
on configured topics.

The fetcher supports optional AgentRun tracking when called with a database
session and source_id, recording execution status, timing, and results.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from reconly_core.config_types import ConfigField
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema
from reconly_core.fetchers.registry import register_fetcher

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.agents import AgentResult, AgentSettings, ResearchAgent
    from reconly_core.database.models import AgentRun

logger = logging.getLogger(__name__)


@register_fetcher('agent')
class AgentFetcher(BaseFetcher):
    """Fetcher that uses a research agent to investigate topics.

    Unlike other fetchers that retrieve content from URLs, the agent fetcher
    uses an LLM with web tools to autonomously research a given topic.

    The `url` field in agent sources is repurposed as the research prompt/topic
    to investigate. The agent will search the web, fetch relevant articles,
    and synthesize findings into a structured research report.

    Configuration:
        max_iterations: Maximum number of research iterations (default: 5)

    Example:
        >>> fetcher = AgentFetcher()
        >>> results = fetcher.fetch("Latest developments in AI safety research")
        >>> print(results[0]['title'])  # Agent-generated title
        >>> print(results[0]['content'])  # Research findings in markdown
    """

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
        """Run the research agent asynchronously with optional tracking.

        Args:
            prompt: The research topic to investigate
            config: Configuration dict with optional max_iterations
            db: Optional SQLAlchemy Session for AgentRun tracking
            source_id: Source ID for AgentRun tracking (required if db provided)
            trace_id: Optional trace ID for log correlation

        Returns:
            Dict formatted as a fetcher result with metadata
        """
        from reconly_core.agents import ResearchAgent, AgentSettings
        from reconly_core.summarizers.factory import get_summarizer

        agent_run: Optional["AgentRun"] = None
        agent_run_id: Optional[int] = None

        # Create AgentRun record if tracking is enabled
        if db is not None and source_id is not None:
            agent_run = self._create_agent_run(db, source_id, prompt, trace_id)
            agent_run_id = agent_run.id

        try:
            # Get agent settings from environment/defaults
            agent_settings = self._get_agent_settings()
            agent_settings.validate()

            # Get summarizer (uses default provider from settings)
            summarizer = get_summarizer(enable_fallback=True)

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

            # Create and run agent
            agent = ResearchAgent(
                summarizer=summarizer,
                settings=agent_settings,
                max_iterations=max_iterations,
            )

            result = await agent.run(prompt)

            # Update AgentRun with success
            if agent_run is not None:
                self._update_agent_run_success(db, agent_run, result, agent)

            # Format as fetcher result
            formatted = self._format_result(prompt, result, agent)
            if agent_run_id is not None:
                formatted['agent_run_id'] = agent_run_id
            return formatted

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
    ) -> "AgentRun":
        """Create a new AgentRun record in pending state.

        Args:
            db: SQLAlchemy Session
            source_id: Source ID for the agent run
            prompt: Research prompt
            trace_id: Optional trace ID for log correlation

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
        )
        db.add(agent_run)
        db.commit()

        logger.info(
            "Created AgentRun record",
            extra={
                "agent_run_id": agent_run.id,
                "source_id": source_id,
                "trace_id": agent_run.trace_id,
            },
        )

        return agent_run

    def _update_agent_run_success(
        self,
        db: "Session",
        agent_run: "AgentRun",
        result: "AgentResult",
        agent: "ResearchAgent",
    ) -> None:
        """Update AgentRun record on successful completion.

        Args:
            db: SQLAlchemy Session
            agent_run: AgentRun record to update
            result: AgentResult from research
            agent: ResearchAgent instance for token tracking
        """
        agent_run.status = 'completed'
        agent_run.completed_at = datetime.utcnow()
        agent_run.iterations = result.iterations
        agent_run.tool_calls = result.tool_calls
        agent_run.sources_consulted = result.sources
        agent_run.result_title = result.title
        agent_run.result_content = result.content
        agent_run.tokens_in = agent.total_tokens_in
        agent_run.tokens_out = agent.total_tokens_out

        # Estimate cost using summarizer's method (OSS edition returns 0.0)
        agent_run.estimated_cost = agent.summarizer.estimate_cost(
            agent.total_tokens_in + agent.total_tokens_out
        )

        db.commit()

        logger.info(
            "AgentRun completed successfully",
            extra={
                "agent_run_id": agent_run.id,
                "iterations": result.iterations,
                "sources_count": len(result.sources),
                "tokens_in": agent.total_tokens_in,
                "tokens_out": agent.total_tokens_out,
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
            search_provider=os.getenv('AGENT_SEARCH_PROVIDER', 'brave'),
            brave_api_key=os.getenv('BRAVE_API_KEY'),
            searxng_url=os.getenv('SEARXNG_URL', 'http://localhost:8080'),
            max_search_results=int(os.getenv('AGENT_MAX_SEARCH_RESULTS', '10')),
            default_max_iterations=int(os.getenv('AGENT_DEFAULT_MAX_ITERATIONS', '5')),
        )

    def _format_result(
        self,
        prompt: str,
        result: "AgentResult",
        agent: "ResearchAgent",
    ) -> dict[str, Any]:
        """Format agent result as fetcher output.

        Args:
            prompt: Original research prompt
            result: AgentResult from research
            agent: ResearchAgent instance (for token tracking)

        Returns:
            Dict with url, title, content, source_type, and metadata
        """
        # Create synthetic URL from prompt (sanitized)
        safe_prompt = prompt[:50].replace(' ', '-').replace('/', '-')
        synthetic_url = f"agent://{safe_prompt}"

        return {
            'url': synthetic_url,
            'title': result.title,
            'content': result.content,
            'source_type': 'agent',
            'metadata': {
                'iterations': result.iterations,
                'tool_calls': result.tool_calls,
                'sources': result.sources,
                'tokens_in': agent.total_tokens_in,
                'tokens_out': agent.total_tokens_out,
            },
        }

    def get_source_type(self) -> str:
        """Return 'agent' as the source type identifier."""
        return 'agent'

    def get_description(self) -> str:
        """Return human-readable description for UI display."""
        return 'AI Research Agent (web search + content analysis)'

    def get_config_schema(self) -> FetcherConfigSchema:
        """Return configuration schema with max_iterations field."""
        return FetcherConfigSchema(
            fields=[
                ConfigField(
                    key="max_iterations",
                    type="integer",
                    label="Max Iterations",
                    description=(
                        "Maximum number of research iterations. "
                        "Higher values allow deeper research but take longer."
                    ),
                    default=5,
                    editable=True,
                ),
            ]
        )
