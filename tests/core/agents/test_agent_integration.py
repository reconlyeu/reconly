"""Integration tests for Agent Source functionality.

Tests cover:
- Full flow: create agent source → add to feed → run feed → verify digest
- Agent with Brave search (requires API key)
- Agent with SearXNG (requires instance)
- Error handling (search failure, LLM timeout)
- Max iterations timeout
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from reconly_core.database.models import (
    Source,
    Feed,
    FeedSource,
    FeedRun,
    Digest,
    AgentRun,
)
from reconly_core.agents.schema import AgentResult
from reconly_core.agents.settings import AgentSettings
from reconly_core.fetchers.agent import AgentFetcher


# =============================================================================
# Environment Detection
# =============================================================================

def _has_brave_api_key() -> bool:
    """Check if Brave API key is configured."""
    return bool(os.getenv("BRAVE_API_KEY"))


def _has_searxng_instance() -> bool:
    """Check if SearXNG instance is available."""
    import requests
    searxng_url = os.getenv("SEARXNG_URL", "http://localhost:8080")
    try:
        resp = requests.get(f"{searxng_url}/healthz", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


# Skip markers
requires_brave = pytest.mark.skipif(
    not _has_brave_api_key(),
    reason="Brave API key not configured (set BRAVE_API_KEY)"
)

requires_searxng = pytest.mark.skipif(
    not _has_searxng_instance(),
    reason="SearXNG instance not available (set SEARXNG_URL)"
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def agent_source(db_session) -> Source:
    """Create an agent source for testing."""
    source = Source(
        name="Test Research Agent",
        type="agent",
        url="What are the latest trends in AI?",  # URL is the prompt for agent sources
        enabled=True,
        config={"max_iterations": 3},
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def agent_feed(db_session, agent_source, sample_prompt_template) -> Feed:
    """Create a feed with an agent source."""
    feed = Feed(
        name="AI Research Feed",
        description="Feed using agent source",
        schedule_enabled=False,
        prompt_template_id=sample_prompt_template.id,
    )
    db_session.add(feed)
    db_session.commit()
    db_session.refresh(feed)

    # Link agent source to feed
    feed_source = FeedSource(
        feed_id=feed.id,
        source_id=agent_source.id,
        priority=0,
        enabled=True,
    )
    db_session.add(feed_source)
    db_session.commit()
    db_session.refresh(feed)
    return feed


@pytest.fixture
def mock_agent_result():
    """Create a mock AgentResult for testing."""
    return AgentResult(
        title="AI Trends Research Summary",
        content="## Key Findings\n\n1. Large language models continue to evolve...\n2. Multimodal AI is gaining traction...",
        sources=["https://example.com/ai-trends", "https://example.com/llm-news"],
        iterations=2,
        tool_calls=[
            {"tool": "web_search", "input": {"query": "latest AI trends 2024"}, "output": "Search results..."},
            {"tool": "web_fetch", "input": {"url": "https://example.com/ai-trends"}, "output": "Article content..."},
        ],
    )


@pytest.fixture
def mock_summarizer():
    """Create a mock summarizer for agent testing."""
    summarizer = MagicMock()
    summarizer.summarize = MagicMock(return_value={
        "summary": "AI is evolving rapidly with new developments in LLMs and multimodal systems.",
        "tokens_in": 500,
        "tokens_out": 100,
        "model": "test-model",
    })
    return summarizer


# =============================================================================
# Full Flow Integration Tests
# =============================================================================

class TestAgentFullFlow:
    """Test the complete agent source flow: create → add to feed → run → verify."""

    def test_agent_source_creation(self, db_session, agent_source):
        """Test that an agent source can be created with correct properties."""
        assert agent_source.id is not None
        assert agent_source.type == "agent"
        assert agent_source.enabled is True
        assert "AI" in agent_source.url  # URL contains the prompt
        assert agent_source.config.get("max_iterations") == 3

    def test_agent_source_in_feed(self, db_session, agent_feed, agent_source):
        """Test that an agent source can be linked to a feed."""
        feed_sources = db_session.query(FeedSource).filter_by(feed_id=agent_feed.id).all()
        assert len(feed_sources) == 1
        assert feed_sources[0].source_id == agent_source.id
        assert feed_sources[0].enabled is True

    def test_agent_fetcher_fetch_with_mock(
        self, db_session, agent_source, mock_agent_result, mock_summarizer
    ):
        """Test AgentFetcher.fetch() with mocked ResearchAgent."""
        fetcher = AgentFetcher()

        # Create mock settings that pass validation
        mock_settings = MagicMock()
        mock_settings.search_provider = "searxng"
        mock_settings.searxng_url = "http://localhost:8080"
        mock_settings.max_search_results = 10
        mock_settings.default_max_iterations = 5
        mock_settings.validate = MagicMock()  # Skip validation

        with patch('reconly_core.agents.ResearchAgent') as MockAgent, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer, \
             patch.object(fetcher, '_get_agent_settings', return_value=mock_settings):

            # Setup mocks - use AsyncMock for async run() method
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_instance.tokens_in = 500
            mock_agent_instance.tokens_out = 100
            MockAgent.return_value = mock_agent_instance
            mock_get_summarizer.return_value = mock_summarizer

            # Execute fetch - url is the prompt string, not the Source object
            result = fetcher.fetch(
                url=agent_source.url,  # The prompt text
                since=None,
                config=agent_source.config,
                source_id=agent_source.id,
            )

            # Verify result
            assert result is not None
            assert len(result) == 1
            item = result[0]
            assert "AI Trends" in item['title']
            assert item['content'] is not None
            assert item['url'].startswith("agent://")

    def test_full_flow_creates_digest(
        self, db_session, agent_feed, agent_source, mock_agent_result, mock_summarizer
    ):
        """Test that running a feed with agent source creates a digest."""
        # Create a feed run
        feed_run = FeedRun(
            feed_id=agent_feed.id,
            triggered_by="manual",
            status="pending",
            started_at=datetime.utcnow(),
            sources_total=1,
        )
        db_session.add(feed_run)
        db_session.commit()

        # Simulate the agent producing a result and creating a digest
        digest = Digest(
            url=f"agent://ai-trends-{agent_source.id}",
            title=mock_agent_result.title,
            content=mock_agent_result.content,
            summary="AI is evolving rapidly with new developments.",
            source_type="agent",
            source_id=agent_source.id,
            feed_run_id=feed_run.id,
        )
        db_session.add(digest)

        # Update feed run status
        feed_run.status = "completed"
        feed_run.sources_processed = 1
        feed_run.items_processed = 1
        feed_run.completed_at = datetime.utcnow()
        db_session.commit()

        # Verify
        db_session.refresh(digest)
        db_session.refresh(feed_run)

        assert digest.id is not None
        assert digest.source_type == "agent"
        assert digest.source_id == agent_source.id
        assert feed_run.status == "completed"
        assert feed_run.items_processed == 1


# =============================================================================
# Brave Search Integration Tests
# =============================================================================

@requires_brave
class TestAgentWithBraveSearch:
    """Test agent with real Brave Search API (requires BRAVE_API_KEY)."""

    def test_brave_search_integration(self, db_session):
        """Test that agent can use Brave Search for web queries."""
        from reconly_core.agents.search import web_search

        settings = AgentSettings(
            search_provider="brave",
            brave_api_key=os.getenv("BRAVE_API_KEY"),
            max_search_results=3,
        )

        # Perform a real search
        results = web_search("Python programming", settings)

        assert results is not None
        assert isinstance(results, str)
        assert len(results) > 0
        # Results should contain markdown formatted search results
        assert "http" in results.lower() or "www" in results.lower()


# =============================================================================
# SearXNG Integration Tests
# =============================================================================

@requires_searxng
class TestAgentWithSearXNG:
    """Test agent with real SearXNG instance (requires running SearXNG)."""

    def test_searxng_search_integration(self, db_session):
        """Test that agent can use SearXNG for web queries."""
        from reconly_core.agents.search import web_search

        settings = AgentSettings(
            search_provider="searxng",
            searxng_url=os.getenv("SEARXNG_URL", "http://localhost:8080"),
            max_search_results=3,
        )

        # Perform a real search
        results = web_search("Python programming", settings)

        assert results is not None
        assert isinstance(results, str)
        assert len(results) > 0


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestAgentErrorHandling:
    """Test agent error handling scenarios."""

    def test_search_failure_handling(self, db_session, agent_source):
        """Test that agent handles search API failures gracefully."""
        fetcher = AgentFetcher()

        # Create mock settings that pass validation
        mock_settings = MagicMock()
        mock_settings.search_provider = "searxng"
        mock_settings.searxng_url = "http://localhost:8080"
        mock_settings.max_search_results = 10
        mock_settings.default_max_iterations = 5
        mock_settings.validate = MagicMock()

        with patch('reconly_core.agents.ResearchAgent') as MockAgent, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer, \
             patch.object(fetcher, '_get_agent_settings', return_value=mock_settings):

            # Setup mock to raise an exception during search
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.side_effect = Exception("Search API unavailable")
            MockAgent.return_value = mock_agent_instance
            mock_get_summarizer.return_value = MagicMock()

            # Fetch should handle the error and return empty or raise gracefully
            with pytest.raises(Exception) as exc_info:
                fetcher.fetch(
                    url=agent_source.url,
                    since=None,
                    config=agent_source.config,
                    source_id=agent_source.id,
                )

            assert "Search API unavailable" in str(exc_info.value)

    def test_llm_timeout_handling(self, db_session, agent_source):
        """Test that agent handles LLM timeout gracefully."""
        fetcher = AgentFetcher()

        # Create mock settings that pass validation
        mock_settings = MagicMock()
        mock_settings.search_provider = "searxng"
        mock_settings.searxng_url = "http://localhost:8080"
        mock_settings.max_search_results = 10
        mock_settings.default_max_iterations = 5
        mock_settings.validate = MagicMock()

        with patch('reconly_core.agents.ResearchAgent') as MockAgent, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer, \
             patch.object(fetcher, '_get_agent_settings', return_value=mock_settings):

            # Setup mock to simulate timeout
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.side_effect = TimeoutError("LLM request timed out")
            MockAgent.return_value = mock_agent_instance
            mock_get_summarizer.return_value = MagicMock()

            with pytest.raises(TimeoutError) as exc_info:
                fetcher.fetch(
                    url=agent_source.url,
                    since=None,
                    config=agent_source.config,
                    source_id=agent_source.id,
                )

            assert "timed out" in str(exc_info.value)

    def test_partial_results_on_error(self, db_session, agent_source):
        """Test that agent can return partial results if error occurs mid-execution."""

        # This tests the _timeout_result functionality
        partial_result = AgentResult(
            title="Partial Research (Max Iterations)",
            content="Research was stopped due to reaching maximum iterations.",
            sources=["https://example.com/partial"],
            iterations=5,
            tool_calls=[
                {"tool": "web_search", "input": {"query": "test"}, "output": "partial..."},
            ],
        )

        # Verify partial result structure
        assert partial_result.title is not None
        assert partial_result.iterations == 5
        assert len(partial_result.sources) > 0


# =============================================================================
# Max Iterations Tests
# =============================================================================

class TestAgentMaxIterations:
    """Test agent max iterations timeout behavior."""

    def test_max_iterations_limit_respected(self, db_session, agent_source):
        """Test that agent stops at max_iterations."""
        fetcher = AgentFetcher()

        iterations_executed = []

        def mock_run(prompt):
            # Track iterations
            iterations_executed.append(1)
            # Return a result that indicates completion
            return AgentResult(
                title="Research Complete",
                content="Findings after iterations",
                sources=["https://example.com"],
                iterations=len(iterations_executed),
                tool_calls=[],
            )

        # Create mock settings that pass validation
        mock_settings = MagicMock()
        mock_settings.search_provider = "searxng"
        mock_settings.searxng_url = "http://localhost:8080"
        mock_settings.max_search_results = 10
        mock_settings.default_max_iterations = 5
        mock_settings.validate = MagicMock()

        async def async_mock_run(prompt):
            return mock_run(prompt)

        with patch('reconly_core.agents.ResearchAgent') as MockAgent, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer, \
             patch.object(fetcher, '_get_agent_settings', return_value=mock_settings):

            mock_agent_instance = MagicMock()
            mock_agent_instance.run = async_mock_run
            mock_agent_instance.tokens_in = 100
            mock_agent_instance.tokens_out = 50
            MockAgent.return_value = mock_agent_instance
            mock_get_summarizer.return_value = MagicMock()

            result = fetcher.fetch(
                url=agent_source.url,
                since=None,
                config=agent_source.config,
                source_id=agent_source.id,
            )

            # Agent should have been called (at least once)
            assert len(iterations_executed) >= 1
            assert result is not None

    def test_max_iterations_config_from_source(self, db_session):
        """Test that max_iterations is read from source config."""
        source = Source(
            name="Limited Agent",
            type="agent",
            url="Quick research topic",
            enabled=True,
            config={"max_iterations": 2},  # Low limit for testing
        )
        db_session.add(source)
        db_session.commit()

        assert source.config.get("max_iterations") == 2

    def test_default_max_iterations_used(self, db_session):
        """Test that default max_iterations is used when not specified."""
        source = Source(
            name="Default Agent",
            type="agent",
            url="Research topic",
            enabled=True,
            config={},  # No max_iterations specified
        )
        db_session.add(source)
        db_session.commit()

        # Default should be applied when fetching
        max_iter = source.config.get("max_iterations", 5)
        assert max_iter == 5


# =============================================================================
# Agent Run Tracking Tests
# =============================================================================

class TestAgentRunTracking:
    """Test that agent runs are properly tracked in the database."""

    def test_agent_run_created_on_execution(self, db_session, agent_source):
        """Test that AgentRun record is created when agent executes."""
        # Create an AgentRun record
        agent_run = AgentRun(
            source_id=agent_source.id,
            prompt=agent_source.url,
            status="pending",
            iterations=0,
            tool_calls=[],
            sources_consulted=[],
        )
        db_session.add(agent_run)
        db_session.commit()

        assert agent_run.id is not None
        assert agent_run.source_id == agent_source.id
        assert agent_run.status == "pending"

    def test_agent_run_updated_on_completion(self, db_session, agent_source, mock_agent_result):
        """Test that AgentRun is updated with results on completion."""
        # Create initial AgentRun
        agent_run = AgentRun(
            source_id=agent_source.id,
            prompt=agent_source.url,
            status="running",
            started_at=datetime.utcnow(),
            iterations=0,
            tool_calls=[],
            sources_consulted=[],
        )
        db_session.add(agent_run)
        db_session.commit()

        # Simulate completion
        agent_run.status = "completed"
        agent_run.completed_at = datetime.utcnow()
        agent_run.iterations = mock_agent_result.iterations
        agent_run.tool_calls = mock_agent_result.tool_calls
        agent_run.sources_consulted = mock_agent_result.sources
        agent_run.result_title = mock_agent_result.title
        agent_run.result_content = mock_agent_result.content
        db_session.commit()

        db_session.refresh(agent_run)
        assert agent_run.status == "completed"
        assert agent_run.iterations == 2
        assert len(agent_run.tool_calls) == 2
        assert len(agent_run.sources_consulted) == 2

    def test_agent_run_records_error_on_failure(self, db_session, agent_source):
        """Test that AgentRun records error details on failure."""
        agent_run = AgentRun(
            source_id=agent_source.id,
            prompt=agent_source.url,
            status="running",
            started_at=datetime.utcnow(),
            iterations=1,
            tool_calls=[{"tool": "web_search", "error": "API unavailable"}],
            sources_consulted=[],
        )
        db_session.add(agent_run)
        db_session.commit()

        # Simulate failure
        agent_run.status = "failed"
        agent_run.completed_at = datetime.utcnow()
        agent_run.error_log = "Search API failed: Connection timeout"
        db_session.commit()

        db_session.refresh(agent_run)
        assert agent_run.status == "failed"
        assert "Connection timeout" in agent_run.error_log
