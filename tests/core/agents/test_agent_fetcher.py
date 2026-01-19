"""Tests for AgentFetcher integration.

Tests cover:
- AgentFetcher registration and interface
- fetch() method with mocked ResearchAgent
- Config schema and max_iterations handling
- Result formatting and metadata
- Error handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reconly_core.fetchers import (
    get_fetcher,
    list_fetchers,
    is_fetcher_registered,
)
from reconly_core.fetchers.agent import AgentFetcher
from reconly_core.agents.schema import AgentResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def agent_fetcher():
    """Create an AgentFetcher instance for testing."""
    return AgentFetcher()


@pytest.fixture
def mock_agent_result():
    """Create a mock AgentResult for testing."""
    return AgentResult(
        title="Test Research Findings",
        content="## Summary\n\nResearch findings here...",
        sources=["https://example.com/article1", "https://example.com/article2"],
        iterations=3,
        tool_calls=[
            {"tool": "web_search", "input": {"query": "test"}, "output": "results..."},
            {"tool": "web_fetch", "input": {"url": "https://example.com"}, "output": "content..."},
        ],
    )


# =============================================================================
# Registration Tests
# =============================================================================


class TestAgentFetcherRegistration:
    """Tests for AgentFetcher registration in the registry."""

    def test_agent_fetcher_registered(self):
        """Test that agent fetcher is registered."""
        assert 'agent' in list_fetchers()
        assert is_fetcher_registered('agent')

    def test_get_fetcher_agent(self):
        """Test getting agent fetcher via factory."""
        fetcher = get_fetcher('agent')
        assert fetcher.get_source_type() == 'agent'
        assert hasattr(fetcher, 'fetch')

    def test_agent_fetcher_instance_type(self):
        """Test that get_fetcher returns AgentFetcher instance."""
        fetcher = get_fetcher('agent')
        assert isinstance(fetcher, AgentFetcher)


# =============================================================================
# Interface Tests
# =============================================================================


class TestAgentFetcherInterface:
    """Tests that AgentFetcher implements BaseFetcher interface."""

    def test_get_source_type(self, agent_fetcher):
        """Test that get_source_type returns 'agent'."""
        assert agent_fetcher.get_source_type() == 'agent'

    def test_can_handle_returns_false(self, agent_fetcher):
        """Test that can_handle returns False (inherits base class default)."""
        # Agent sources use explicit typing, not URL detection
        assert agent_fetcher.can_handle('https://example.com') is False
        assert agent_fetcher.can_handle('agent://topic') is False

    def test_get_description(self, agent_fetcher):
        """Test that get_description returns non-empty string."""
        desc = agent_fetcher.get_description()
        assert isinstance(desc, str)
        assert 'agent' in desc.lower() or 'research' in desc.lower()

    def test_get_config_schema(self, agent_fetcher):
        """Test that get_config_schema returns schema with fields."""
        schema = agent_fetcher.get_config_schema()
        assert schema is not None
        assert hasattr(schema, 'fields')


# =============================================================================
# Config Schema Tests
# =============================================================================


class TestAgentFetcherConfigSchema:
    """Tests for AgentFetcher configuration schema."""

    def test_schema_has_max_iterations_field(self, agent_fetcher):
        """Test that config schema includes max_iterations."""
        schema = agent_fetcher.get_config_schema()
        field_keys = [f.key for f in schema.fields]
        assert 'max_iterations' in field_keys

    def test_max_iterations_field_properties(self, agent_fetcher):
        """Test max_iterations field has correct properties."""
        schema = agent_fetcher.get_config_schema()
        max_iter_field = next(f for f in schema.fields if f.key == 'max_iterations')

        assert max_iter_field.type == 'integer'
        assert max_iter_field.default == 5
        assert max_iter_field.editable is True
        assert max_iter_field.label is not None


# =============================================================================
# Fetch Method Tests (with mocks)
# =============================================================================


class TestAgentFetcherFetch:
    """Tests for fetch() method with mocked dependencies."""

    @patch('reconly_core.fetchers.agent.AgentFetcher._run_agent')
    def test_fetch_returns_list(self, mock_run_agent, agent_fetcher, mock_agent_result):
        """Test that fetch returns a list."""
        mock_run_agent.return_value = {
            'url': 'agent://test',
            'title': mock_agent_result.title,
            'content': mock_agent_result.content,
            'source_type': 'agent',
            'metadata': {},
        }

        result = agent_fetcher.fetch("Test research topic")

        assert isinstance(result, list)
        assert len(result) == 1

    @patch('reconly_core.fetchers.agent.AgentFetcher._run_agent')
    def test_fetch_result_structure(self, mock_run_agent, agent_fetcher):
        """Test that fetch result has required fields."""
        mock_run_agent.return_value = {
            'url': 'agent://test-topic',
            'title': 'Research Title',
            'content': 'Research content',
            'source_type': 'agent',
            'metadata': {
                'iterations': 3,
                'tool_calls': [],
                'sources': [],
                'tokens_in': 100,
                'tokens_out': 50,
            },
        }

        result = agent_fetcher.fetch("Test topic")
        item = result[0]

        assert 'url' in item
        assert 'title' in item
        assert 'content' in item
        assert 'source_type' in item
        assert item['source_type'] == 'agent'

    @patch('reconly_core.fetchers.agent.AgentFetcher._run_agent')
    def test_fetch_includes_metadata(self, mock_run_agent, agent_fetcher):
        """Test that fetch result includes metadata."""
        mock_run_agent.return_value = {
            'url': 'agent://test',
            'title': 'Title',
            'content': 'Content',
            'source_type': 'agent',
            'metadata': {
                'iterations': 3,
                'tool_calls': [{'tool': 'web_search'}],
                'sources': ['https://example.com'],
                'tokens_in': 500,
                'tokens_out': 200,
            },
        }

        result = agent_fetcher.fetch("Test")
        metadata = result[0]['metadata']

        assert 'iterations' in metadata
        assert 'tool_calls' in metadata
        assert 'sources' in metadata
        assert 'tokens_in' in metadata
        assert 'tokens_out' in metadata

    @patch('reconly_core.fetchers.agent.AgentFetcher._run_agent')
    def test_fetch_passes_config(self, mock_run_agent, agent_fetcher):
        """Test that fetch passes config to _run_agent."""
        mock_run_agent.return_value = {
            'url': 'agent://test',
            'title': 'Title',
            'content': 'Content',
            'source_type': 'agent',
            'metadata': {},
        }

        agent_fetcher.fetch("Test", config={'max_iterations': 10})

        mock_run_agent.assert_called_once()
        call_args = mock_run_agent.call_args
        assert call_args.kwargs['config'] == {'max_iterations': 10}

    @patch('reconly_core.fetchers.agent.AgentFetcher._run_agent')
    def test_fetch_ignores_since_and_max_items(self, mock_run_agent, agent_fetcher):
        """Test that fetch ignores since and max_items parameters."""
        from datetime import datetime

        mock_run_agent.return_value = {
            'url': 'agent://test',
            'title': 'Title',
            'content': 'Content',
            'source_type': 'agent',
            'metadata': {},
        }

        # These parameters should be accepted but ignored
        result = agent_fetcher.fetch(
            "Test topic",
            since=datetime.now(),
            max_items=10,
        )

        assert len(result) == 1


# =============================================================================
# Result Formatting Tests
# =============================================================================


class TestResultFormatting:
    """Tests for _format_result method."""

    def test_format_result_synthetic_url(self, agent_fetcher, mock_agent_result):
        """Test that _format_result creates synthetic URL."""
        mock_agent = MagicMock()
        mock_agent.total_tokens_in = 100
        mock_agent.total_tokens_out = 50

        result = agent_fetcher._format_result(
            "Test research topic",
            mock_agent_result,
            mock_agent,
        )

        assert result['url'].startswith('agent://')
        assert 'Test' in result['url']

    def test_format_result_sanitizes_url(self, agent_fetcher, mock_agent_result):
        """Test that _format_result sanitizes special characters in URL."""
        mock_agent = MagicMock()
        mock_agent.total_tokens_in = 100
        mock_agent.total_tokens_out = 50

        result = agent_fetcher._format_result(
            "Test/with/slashes and spaces",
            mock_agent_result,
            mock_agent,
        )

        assert '/' not in result['url'].replace('agent://', '')
        assert ' ' not in result['url']

    def test_format_result_truncates_long_prompts(self, agent_fetcher, mock_agent_result):
        """Test that _format_result truncates long prompts in URL."""
        mock_agent = MagicMock()
        mock_agent.total_tokens_in = 100
        mock_agent.total_tokens_out = 50

        long_prompt = "A" * 100  # 100 characters
        result = agent_fetcher._format_result(
            long_prompt,
            mock_agent_result,
            mock_agent,
        )

        # URL should be truncated to ~50 chars of prompt
        url_without_prefix = result['url'].replace('agent://', '')
        assert len(url_without_prefix) <= 50

    def test_format_result_includes_agent_result_data(self, agent_fetcher, mock_agent_result):
        """Test that _format_result includes data from AgentResult."""
        mock_agent = MagicMock()
        mock_agent.total_tokens_in = 100
        mock_agent.total_tokens_out = 50

        result = agent_fetcher._format_result(
            "Test",
            mock_agent_result,
            mock_agent,
        )

        assert result['title'] == mock_agent_result.title
        assert result['content'] == mock_agent_result.content
        assert result['source_type'] == 'agent'
        assert result['metadata']['iterations'] == mock_agent_result.iterations
        assert result['metadata']['sources'] == mock_agent_result.sources
        assert result['metadata']['tool_calls'] == mock_agent_result.tool_calls

    def test_format_result_includes_token_tracking(self, agent_fetcher, mock_agent_result):
        """Test that _format_result includes token counts from agent."""
        mock_agent = MagicMock()
        mock_agent.total_tokens_in = 500
        mock_agent.total_tokens_out = 200

        result = agent_fetcher._format_result(
            "Test",
            mock_agent_result,
            mock_agent,
        )

        assert result['metadata']['tokens_in'] == 500
        assert result['metadata']['tokens_out'] == 200


# =============================================================================
# Agent Settings Tests
# =============================================================================


class TestAgentSettings:
    """Tests for _get_agent_settings method."""

    def test_get_agent_settings_defaults(self, agent_fetcher):
        """Test that _get_agent_settings returns defaults when env not set."""
        with patch.dict('os.environ', {}, clear=True):
            settings = agent_fetcher._get_agent_settings()

            assert settings.search_provider == 'brave'
            assert settings.searxng_url == 'http://localhost:8080'
            assert settings.max_search_results == 10
            assert settings.default_max_iterations == 5

    def test_get_agent_settings_from_env(self, agent_fetcher):
        """Test that _get_agent_settings reads from environment."""
        env_vars = {
            'AGENT_SEARCH_PROVIDER': 'searxng',
            'BRAVE_API_KEY': 'test-key',
            'SEARXNG_URL': 'http://searx.local',
            'AGENT_MAX_SEARCH_RESULTS': '20',
            'AGENT_DEFAULT_MAX_ITERATIONS': '10',
        }

        with patch.dict('os.environ', env_vars, clear=True):
            settings = agent_fetcher._get_agent_settings()

            assert settings.search_provider == 'searxng'
            assert settings.brave_api_key == 'test-key'
            assert settings.searxng_url == 'http://searx.local'
            assert settings.max_search_results == 20
            assert settings.default_max_iterations == 10


# =============================================================================
# Integration Tests (with more extensive mocking)
# =============================================================================


class TestAgentFetcherIntegration:
    """Integration tests with mocked ResearchAgent."""

    @pytest.mark.asyncio
    async def test_run_agent_creates_research_agent(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent creates and runs ResearchAgent."""
        with patch(
            'reconly_core.agents.ResearchAgent'
        ) as mock_agent_class, patch(
            'reconly_core.providers.factory.get_summarizer'
        ) as mock_get_summarizer, patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_get_summarizer.return_value = mock_summarizer

            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent.total_tokens_in = 100
            mock_agent.total_tokens_out = 50
            mock_agent_class.return_value = mock_agent

            # Run
            await agent_fetcher._run_agent("Test topic", {})

            # Verify
            mock_agent_class.assert_called_once_with(
                summarizer=mock_summarizer,
                settings=mock_settings,
                max_iterations=5,
            )
            mock_agent.run.assert_called_once_with("Test topic")

    @pytest.mark.asyncio
    async def test_run_agent_respects_config_max_iterations(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent uses max_iterations from config."""
        with patch(
            'reconly_core.agents.ResearchAgent'
        ) as mock_agent_class, patch(
            'reconly_core.providers.factory.get_summarizer'
        ), patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent.total_tokens_in = 100
            mock_agent.total_tokens_out = 50
            mock_agent_class.return_value = mock_agent

            # Run with custom max_iterations
            await agent_fetcher._run_agent("Test", {'max_iterations': 10})

            # Verify custom value was used
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args.kwargs
            assert call_kwargs['max_iterations'] == 10

    @pytest.mark.asyncio
    async def test_run_agent_returns_formatted_result(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent returns properly formatted result."""
        with patch(
            'reconly_core.agents.ResearchAgent'
        ) as mock_agent_class, patch(
            'reconly_core.providers.factory.get_summarizer'
        ), patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent.total_tokens_in = 100
            mock_agent.total_tokens_out = 50
            mock_agent_class.return_value = mock_agent

            result = await agent_fetcher._run_agent("Test topic", {})

            assert result['url'].startswith('agent://')
            assert result['title'] == mock_agent_result.title
            assert result['content'] == mock_agent_result.content
            assert result['source_type'] == 'agent'
            assert result['metadata']['tokens_in'] == 100
            assert result['metadata']['tokens_out'] == 50
