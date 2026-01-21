"""GPT Researcher strategy for comprehensive and deep research.

This module implements the ResearchStrategy interface using the gpt-researcher
library for comprehensive web research tasks.

Note:
    This module requires the 'research' extra to be installed:
    pip install reconly-core[research]
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import structlog

from reconly_core.agents.schema import AgentResult
from reconly_core.agents.strategies.base import ResearchStrategy

if TYPE_CHECKING:
    from collections.abc import Iterator

    from reconly_core.agents.settings import AgentSettings
    from reconly_core.providers.base import BaseProvider

log = structlog.get_logger(__name__)


class GPTResearcherStrategy(ResearchStrategy):
    """Research strategy using GPT Researcher for comprehensive research.

    GPT Researcher is a multi-agent framework using planner, executor, and
    publisher agents for web research with citations.

    Attributes:
        deep_mode: If True, use deep research with subtopics exploration
        summarizer: LLM provider for configuration (model, API key)
    """

    def __init__(
        self,
        deep_mode: bool = False,
        summarizer: "BaseProvider | None" = None,
    ):
        """Initialize the GPT Researcher strategy.

        Args:
            deep_mode: Enable deep research mode with subtopic exploration
            summarizer: LLM provider instance for configuration extraction
        """
        self.deep_mode = deep_mode
        self.summarizer = summarizer

    async def research(
        self,
        prompt: str,
        settings: "AgentSettings",
        max_iterations: int | None = None,
    ) -> AgentResult:
        """Execute research using GPT Researcher and return structured result.

        Args:
            prompt: The research topic or question to investigate
            settings: Agent settings with search provider configuration
            max_iterations: Not used by GPT Researcher (kept for interface compatibility)

        Returns:
            AgentResult with title, content, sources, and metadata
        """
        try:
            from gpt_researcher import GPTResearcher
        except ImportError as e:
            log.error("gpt_researcher_import_failed", error=str(e))
            raise ImportError(
                "GPT Researcher is not installed. Install with: "
                "pip install reconly-core[research]"
            ) from e

        strategy_name = "deep" if self.deep_mode else "comprehensive"
        log.info(
            "gpt_researcher_starting",
            strategy=strategy_name,
            prompt=prompt[:100],
            report_format=settings.gptr_report_format,
            max_subtopics=settings.gptr_max_subtopics,
        )

        with self._configure_environment(settings):
            try:
                report_type = "detailed_report" if self.deep_mode else "research_report"
                researcher = GPTResearcher(
                    query=prompt,
                    report_type=report_type,
                    report_format=settings.gptr_report_format,
                    max_subtopics=settings.gptr_max_subtopics,
                    verbose=False,
                )

                await researcher.conduct_research()
                report = await researcher.write_report()

                sources = self._get_attr(researcher, "get_source_urls", [])
                subtopics = self._get_attr(researcher, "get_subtopics", [])
                context = self._get_attr(researcher, "get_research_context", [])

                log.info(
                    "gpt_researcher_completed",
                    strategy=strategy_name,
                    sources_count=len(sources),
                    subtopics_count=len(subtopics),
                    report_length=len(report),
                )

                return AgentResult(
                    title=self._extract_title(report, prompt),
                    content=report,
                    sources=sources,
                    iterations=len(context) if context else 1,
                    tool_calls=self._build_tool_calls(sources, subtopics, context),
                )

            except Exception as e:
                log.error(
                    "gpt_researcher_failed",
                    strategy=strategy_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    @contextmanager
    def _configure_environment(self, settings: "AgentSettings") -> "Iterator[None]":
        """Configure GPT Researcher env vars, restoring originals on exit."""
        env_vars = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OLLAMA_BASE_URL",
            "SMART_LLM",
            "FAST_LLM",
            "RETRIEVER",
            "SEARX_URL",
            "TAVILY_API_KEY",
        ]
        original_values = {key: os.environ.get(key) for key in env_vars}

        try:
            self._configure_llm_env()
            self._configure_search_env(settings)
            yield
        finally:
            for key, value in original_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _configure_llm_env(self) -> None:
        """Map Reconly provider config to GPT Researcher env vars."""
        if self.summarizer is None:
            log.warning(
                "gpt_researcher_no_summarizer",
                msg="No summarizer provided, using default GPT Researcher LLM config",
            )
            return

        model_info = self.summarizer.get_model_info()
        provider_name = model_info.get("provider", "").lower()
        model_name = model_info.get("model", "")

        log.debug(
            "gpt_researcher_configuring_llm",
            provider=provider_name,
            model=model_name,
        )

        if provider_name in ("openai", "openai-compatible"):
            api_key = getattr(self.summarizer, "api_key", None)
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            os.environ["SMART_LLM"] = f"openai:{model_name}"
            os.environ["FAST_LLM"] = "openai:gpt-4o-mini"

        elif provider_name == "anthropic":
            api_key = getattr(self.summarizer, "api_key", None)
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
            os.environ["SMART_LLM"] = f"anthropic:{model_name}"
            os.environ["FAST_LLM"] = "anthropic:claude-3-haiku-20240307"

        elif provider_name == "ollama":
            base_url = getattr(self.summarizer, "base_url", None)
            if base_url:
                os.environ["OLLAMA_BASE_URL"] = base_url
            os.environ["SMART_LLM"] = f"ollama:{model_name}"
            os.environ["FAST_LLM"] = f"ollama:{model_name}"

        else:
            log.warning(
                "gpt_researcher_unsupported_provider",
                provider=provider_name,
                msg="Provider not directly supported, using default GPT Researcher config",
            )

    def _configure_search_env(self, settings: "AgentSettings") -> None:
        """Map Reconly search provider settings to GPT Researcher retriever config."""
        provider = settings.search_provider

        log.debug("gpt_researcher_configuring_search", search_provider=provider)

        if provider == "searxng":
            os.environ["RETRIEVER"] = "searx"
            if settings.searxng_url:
                os.environ["SEARX_URL"] = settings.searxng_url

        elif provider == "tavily":
            os.environ["RETRIEVER"] = "tavily"
            if settings.tavily_api_key:
                os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

        elif provider == "duckduckgo":
            os.environ["RETRIEVER"] = "duckduckgo"

        else:
            log.warning(
                "gpt_researcher_unsupported_search",
                search_provider=provider,
                msg="Search provider not directly supported, using duckduckgo fallback",
            )
            os.environ["RETRIEVER"] = "duckduckgo"

    def _extract_title(self, report: str, prompt: str) -> str:
        """Extract title from first markdown heading, or generate from prompt."""
        heading_match = re.search(r"^#{1,2}\s+(.+?)$", report, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

        title = prompt.strip()
        if len(title) > 100:
            title = title[:97] + "..."
        return f"Research: {title}"

    def _get_attr(self, researcher: Any, method_name: str, default: Any) -> Any:
        """Safely call a researcher method, returning default on failure."""
        try:
            if hasattr(researcher, method_name):
                return getattr(researcher, method_name)() or default
        except Exception as e:
            log.warning(
                "gpt_researcher_method_failed",
                method=method_name,
                error=str(e),
            )
        return default

    def _build_tool_calls(
        self,
        sources: list[str],
        subtopics: list[str],
        context: list[Any],
    ) -> list[dict[str, Any]]:
        """Build tool calls list representing the research process."""
        tool_calls: list[dict[str, Any]] = []

        if subtopics:
            subtopics_preview = ", ".join(subtopics[:5])
            if len(subtopics) > 5:
                subtopics_preview += "..."
            tool_calls.append({
                "tool": "gpt_researcher_subtopics",
                "input": {"count": len(subtopics)},
                "output": subtopics_preview,
            })

        if sources:
            tool_calls.append({
                "tool": "gpt_researcher_web_research",
                "input": {"sources_explored": len(sources)},
                "output": f"Researched {len(sources)} sources",
            })

        if context:
            tool_calls.append({
                "tool": "gpt_researcher_context",
                "input": {"context_items": len(context)},
                "output": f"Gathered {len(context)} context items",
            })

        return tool_calls

    def estimate_duration_seconds(self) -> int:
        """Return estimated duration in seconds (deep: 300s, comprehensive: 180s)."""
        return 300 if self.deep_mode else 180

    def estimate_cost_usd(self, model: str) -> float:
        """Return estimated cost in USD (deep: $1.00, comprehensive: $0.50)."""
        return 1.00 if self.deep_mode else 0.50
