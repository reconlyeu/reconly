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
        mock_summarizer = MagicMock()
        mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}

        result = agent_fetcher._format_result(
            "Test research topic",
            mock_agent_result,
            "simple",
            mock_summarizer,
        )

        assert result['url'].startswith('agent://')
        assert 'Test' in result['url']

    def test_format_result_sanitizes_url(self, agent_fetcher, mock_agent_result):
        """Test that _format_result sanitizes special characters in URL."""
        mock_summarizer = MagicMock()
        mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}

        result = agent_fetcher._format_result(
            "Test/with/slashes and spaces",
            mock_agent_result,
            "simple",
            mock_summarizer,
        )

        # URL format is agent://YYYY-MM-DD/sanitized-topic
        # The date prefix has a single / separator, but the topic portion should have
        # slashes and spaces replaced with dashes
        url_without_scheme = result['url'].replace('agent://', '')
        # Split off the date prefix (YYYY-MM-DD/) and check the topic part
        parts = url_without_scheme.split('/', 1)
        assert len(parts) == 2, f"Expected date/topic format, got: {url_without_scheme}"
        topic_part = parts[1]
        assert '/' not in topic_part
        assert ' ' not in result['url']

    def test_format_result_truncates_long_prompts(self, agent_fetcher, mock_agent_result):
        """Test that _format_result truncates long prompts in URL."""
        mock_summarizer = MagicMock()
        mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}

        long_prompt = "A" * 100  # 100 characters
        result = agent_fetcher._format_result(
            long_prompt,
            mock_agent_result,
            "simple",
            mock_summarizer,
        )

        # URL format is agent://YYYY-MM-DD/truncated-topic
        # The topic portion (after date prefix) should be truncated to ~50 chars
        url_without_scheme = result['url'].replace('agent://', '')
        parts = url_without_scheme.split('/', 1)
        assert len(parts) == 2, f"Expected date/topic format, got: {url_without_scheme}"
        topic_part = parts[1]
        assert len(topic_part) <= 50

    def test_format_result_includes_agent_result_data(self, agent_fetcher, mock_agent_result):
        """Test that _format_result includes data from AgentResult."""
        mock_summarizer = MagicMock()
        mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}

        result = agent_fetcher._format_result(
            "Test",
            mock_agent_result,
            "simple",
            mock_summarizer,
        )

        assert result['title'] == mock_agent_result.title
        assert result['content'] == mock_agent_result.content
        assert result['source_type'] == 'agent'
        assert result['metadata']['iterations'] == mock_agent_result.iterations
        assert result['metadata']['sources'] == mock_agent_result.sources
        assert result['metadata']['tool_calls'] == mock_agent_result.tool_calls

    def test_format_result_includes_strategy_metadata(self, agent_fetcher, mock_agent_result):
        """Test that _format_result includes strategy and LLM metadata."""
        mock_summarizer = MagicMock()
        mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}

        result = agent_fetcher._format_result(
            "Test",
            mock_agent_result,
            "comprehensive",
            mock_summarizer,
        )

        assert result['metadata']['research_strategy'] == 'comprehensive'
        assert result['metadata']['llm_provider'] == 'openai'
        assert result['metadata']['llm_model'] == 'gpt-4'


# =============================================================================
# Agent Settings Tests
# =============================================================================


class TestAgentSettings:
    """Tests for _get_agent_settings method."""

    def test_get_agent_settings_defaults(self, agent_fetcher):
        """Test that _get_agent_settings returns defaults when env not set."""
        with patch.dict('os.environ', {}, clear=True):
            settings = agent_fetcher._get_agent_settings()

            assert settings.search_provider == 'duckduckgo'
            assert settings.searxng_url == 'http://localhost:8080'
            assert settings.max_search_results == 10
            assert settings.default_max_iterations == 5

    def test_get_agent_settings_from_env(self, agent_fetcher):
        """Test that _get_agent_settings reads from environment."""
        env_vars = {
            'AGENT_SEARCH_PROVIDER': 'searxng',
            'SEARXNG_URL': 'http://searx.local',
            'AGENT_MAX_SEARCH_RESULTS': '20',
            'AGENT_DEFAULT_MAX_ITERATIONS': '10',
        }

        with patch.dict('os.environ', env_vars, clear=True):
            settings = agent_fetcher._get_agent_settings()

            assert settings.search_provider == 'searxng'
            assert settings.searxng_url == 'http://searx.local'
            assert settings.max_search_results == 20
            assert settings.default_max_iterations == 10


# =============================================================================
# Integration Tests (with more extensive mocking)
# =============================================================================


class TestAgentFetcherIntegration:
    """Integration tests with mocked strategy pattern."""

    @pytest.mark.asyncio
    async def test_run_agent_uses_strategy_pattern(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent uses the strategy pattern."""
        with patch(
            'reconly_core.agents.strategies.get_strategy'
        ) as mock_get_strategy, patch(
            'reconly_core.providers.factory.get_summarizer'
        ) as mock_get_summarizer, patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings, patch.object(
            agent_fetcher, '_get_embedding_config'
        ) as mock_get_embedding_config:
            # Setup mocks
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_embedding_config = {'provider': 'ollama', 'model': 'bge-m3'}
            mock_get_embedding_config.return_value = mock_embedding_config

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_get_strategy.return_value = mock_strategy

            # Run
            await agent_fetcher._run_agent("Test topic", {})

            # Verify strategy was called with embedding_config
            mock_get_strategy.assert_called_once_with(
                'simple', summarizer=mock_summarizer, embedding_config=mock_embedding_config
            )
            mock_strategy.research.assert_called_once_with("Test topic", mock_settings, 5)

    @pytest.mark.asyncio
    async def test_run_agent_respects_config_strategy(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent uses research_strategy from config."""
        with patch(
            'reconly_core.agents.strategies.get_strategy'
        ) as mock_get_strategy, patch(
            'reconly_core.providers.factory.get_summarizer'
        ) as mock_get_summarizer, patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings, patch.object(
            agent_fetcher, '_get_embedding_config'
        ) as mock_get_embedding_config:
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_embedding_config = {'provider': 'ollama', 'model': 'bge-m3'}
            mock_get_embedding_config.return_value = mock_embedding_config

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_get_strategy.return_value = mock_strategy

            # Run with comprehensive strategy
            await agent_fetcher._run_agent("Test", {'research_strategy': 'comprehensive'})

            # Verify comprehensive strategy was requested with embedding_config
            mock_get_strategy.assert_called_once_with(
                'comprehensive', summarizer=mock_summarizer, embedding_config=mock_embedding_config
            )

    @pytest.mark.asyncio
    async def test_run_agent_respects_config_max_iterations(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent uses max_iterations from config."""
        with patch(
            'reconly_core.agents.strategies.get_strategy'
        ) as mock_get_strategy, patch(
            'reconly_core.providers.factory.get_summarizer'
        ) as mock_get_summarizer, patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_get_strategy.return_value = mock_strategy

            # Run with custom max_iterations
            await agent_fetcher._run_agent("Test", {'max_iterations': 10})

            # Verify custom value was passed to strategy
            mock_strategy.research.assert_called_once()
            call_args = mock_strategy.research.call_args
            assert call_args[0][2] == 10  # max_iterations is third positional arg

    @pytest.mark.asyncio
    async def test_run_agent_returns_formatted_result(self, agent_fetcher, mock_agent_result):
        """Test that _run_agent returns properly formatted result."""
        with patch(
            'reconly_core.agents.strategies.get_strategy'
        ) as mock_get_strategy, patch(
            'reconly_core.providers.factory.get_summarizer'
        ) as mock_get_summarizer, patch.object(
            agent_fetcher, '_get_agent_settings'
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_get_strategy.return_value = mock_strategy

            result = await agent_fetcher._run_agent("Test topic", {})

            assert result['url'].startswith('agent://')
            assert result['title'] == mock_agent_result.title
            assert result['content'] == mock_agent_result.content
            assert result['source_type'] == 'agent'
            assert result['metadata']['research_strategy'] == 'simple'
            assert result['metadata']['llm_provider'] == 'openai'
            assert result['metadata']['llm_model'] == 'gpt-4'


# =============================================================================
# Strategy-Specific Integration Tests
# =============================================================================


class TestAgentFetcherStrategyIntegration:
    """Tests for integration with different research strategies."""

    @pytest.mark.asyncio
    async def test_comprehensive_strategy_applies_config_overrides(
        self, agent_fetcher, mock_agent_result
    ):
        """Test that comprehensive strategy applies report_format and max_subtopics."""
        with (
            patch('reconly_core.agents.strategies.get_strategy') as mock_get_strategy,
            patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer,
            patch.object(agent_fetcher, '_get_agent_settings') as mock_get_settings,
        ):
            mock_settings = MagicMock()
            mock_settings.search_provider = 'duckduckgo'
            mock_settings.default_max_iterations = 5
            mock_settings.gptr_report_format = 'APA'
            mock_settings.gptr_max_subtopics = 3
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_strategy.estimate_cost_usd.return_value = 0.50
            mock_get_strategy.return_value = mock_strategy

            config = {
                'research_strategy': 'comprehensive',
                'report_format': 'IEEE',
                'max_subtopics': 5,
            }

            await agent_fetcher._run_agent("Test topic", config)

            # Verify settings were modified
            assert mock_settings.gptr_report_format == 'IEEE'
            assert mock_settings.gptr_max_subtopics == 5

    @pytest.mark.asyncio
    async def test_deep_strategy_uses_correct_timeout(
        self, agent_fetcher, mock_agent_result
    ):
        """Test that deep strategy uses the configured timeout."""
        from reconly_core.fetchers.agent import _get_strategy_timeouts

        with (
            patch('reconly_core.agents.strategies.get_strategy') as mock_get_strategy,
            patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer,
            patch.object(agent_fetcher, '_get_agent_settings') as mock_get_settings,
            patch.object(agent_fetcher, '_get_embedding_config') as mock_get_embedding_config,
            patch('asyncio.wait_for') as mock_wait_for,
        ):
            mock_settings = MagicMock()
            mock_settings.search_provider = 'duckduckgo'
            mock_settings.default_max_iterations = 5
            mock_settings.gptr_report_format = 'APA'
            mock_settings.gptr_max_subtopics = 3
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_embedding_config = {'provider': 'ollama', 'model': 'bge-m3'}
            mock_get_embedding_config.return_value = mock_embedding_config

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_strategy.estimate_cost_usd.return_value = 1.00
            mock_get_strategy.return_value = mock_strategy

            # Make wait_for return the result
            mock_wait_for.return_value = mock_agent_result

            await agent_fetcher._run_agent("Test topic", {'research_strategy': 'deep'})

            # Verify timeout uses the value from _get_strategy_timeouts
            mock_wait_for.assert_called_once()
            _, kwargs = mock_wait_for.call_args
            assert kwargs['timeout'] == _get_strategy_timeouts()['deep']

    @pytest.mark.asyncio
    async def test_search_provider_override_from_config(
        self, agent_fetcher, mock_agent_result
    ):
        """Test that search_provider can be overridden per-source."""
        with (
            patch('reconly_core.agents.strategies.get_strategy') as mock_get_strategy,
            patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer,
            patch.object(agent_fetcher, '_get_agent_settings') as mock_get_settings,
        ):
            mock_settings = MagicMock()
            mock_settings.search_provider = 'duckduckgo'  # Default
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_strategy.research = AsyncMock(return_value=mock_agent_result)
            mock_get_strategy.return_value = mock_strategy

            # Override search provider in config
            config = {'search_provider': 'tavily'}

            await agent_fetcher._run_agent("Test topic", config)

            # Verify search_provider was overridden
            assert mock_settings.search_provider == 'tavily'

    @pytest.mark.asyncio
    async def test_import_error_handling_for_gpt_researcher(
        self, agent_fetcher
    ):
        """Test that ImportError is raised when GPT Researcher not installed."""
        with (
            patch('reconly_core.agents.strategies.get_strategy') as mock_get_strategy,
            patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer,
            patch.object(agent_fetcher, '_get_agent_settings') as mock_get_settings,
        ):
            mock_settings = MagicMock()
            mock_settings.search_provider = 'duckduckgo'
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            # Simulate ImportError when getting comprehensive strategy
            mock_get_strategy.side_effect = ImportError(
                "GPT Researcher strategy requires the 'research' extra"
            )

            with pytest.raises(ImportError) as exc_info:
                await agent_fetcher._run_agent("Test", {'research_strategy': 'comprehensive'})

            assert 'research' in str(exc_info.value).lower()


# =============================================================================
# Timeout Error Tests
# =============================================================================


class TestAgentFetcherTimeoutHandling:
    """Tests for timeout handling in AgentFetcher."""

    @pytest.mark.asyncio
    async def test_timeout_error_includes_strategy_info(
        self, agent_fetcher
    ):
        """Test that TimeoutError includes strategy name and duration."""
        import asyncio as asyncio_module
        from reconly_core.fetchers.agent import _get_strategy_timeouts

        with (
            patch('reconly_core.agents.strategies.get_strategy') as mock_get_strategy,
            patch('reconly_core.providers.factory.get_summarizer') as mock_get_summarizer,
            patch.object(agent_fetcher, '_get_agent_settings') as mock_get_settings,
            patch.object(agent_fetcher, '_get_embedding_config') as mock_get_embedding_config,
            patch('asyncio.wait_for') as mock_wait_for,
        ):
            mock_settings = MagicMock()
            mock_settings.search_provider = 'duckduckgo'
            mock_settings.default_max_iterations = 5
            mock_settings.validate.return_value = None
            mock_get_settings.return_value = mock_settings

            mock_embedding_config = {'provider': 'ollama', 'model': 'bge-m3'}
            mock_get_embedding_config.return_value = mock_embedding_config

            mock_summarizer = MagicMock()
            mock_summarizer.get_model_info.return_value = {'provider': 'openai', 'model': 'gpt-4'}
            mock_get_summarizer.return_value = mock_summarizer

            mock_strategy = MagicMock()
            mock_get_strategy.return_value = mock_strategy

            # Simulate timeout
            mock_wait_for.side_effect = asyncio_module.TimeoutError()

            with pytest.raises(TimeoutError) as exc_info:
                await agent_fetcher._run_agent("Test", {'research_strategy': 'comprehensive'})

            error_msg = str(exc_info.value)
            assert 'comprehensive' in error_msg
            assert str(_get_strategy_timeouts()['comprehensive']) in error_msg


# =============================================================================
# Validation Tests for Strategy Fields
# =============================================================================


class TestAgentFetcherValidation:
    """Tests for config validation specific to strategy fields."""

    def test_validate_valid_research_strategy(self, agent_fetcher):
        """Test validation accepts valid research_strategy values."""
        from reconly_core.fetchers.agent import VALID_STRATEGIES

        for strategy in VALID_STRATEGIES:
            result = agent_fetcher.validate(
                "What are the latest developments in quantum computing?",
                config={'research_strategy': strategy}
            )
            # Should not have errors for valid strategy (may have warnings)
            strategy_errors = [e for e in result.errors if 'strategy' in e.lower()]
            assert len(strategy_errors) == 0, f"Strategy '{strategy}' should be valid"

    def test_validate_invalid_research_strategy(self, agent_fetcher):
        """Test validation rejects invalid research_strategy."""
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={'research_strategy': 'invalid_strategy'}
        )

        assert result.valid is False
        assert any('strategy' in err.lower() for err in result.errors)

    def test_validate_report_format_valid(self, agent_fetcher):
        """Test validation accepts valid report_format values."""
        from reconly_core.fetchers.agent import VALID_REPORT_FORMATS

        for fmt in VALID_REPORT_FORMATS:
            result = agent_fetcher.validate(
                "Test research topic for validation",
                config={'research_strategy': 'comprehensive', 'report_format': fmt}
            )
            format_errors = [e for e in result.errors if 'format' in e.lower()]
            assert len(format_errors) == 0, f"Format '{fmt}' should be valid"

    def test_validate_report_format_invalid(self, agent_fetcher):
        """Test validation rejects invalid report_format."""
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={'research_strategy': 'comprehensive', 'report_format': 'INVALID'}
        )

        assert result.valid is False
        assert any('format' in err.lower() for err in result.errors)

    def test_validate_max_subtopics_range(self, agent_fetcher):
        """Test validation enforces max_subtopics range (1-10)."""
        # Below range
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={'research_strategy': 'deep', 'max_subtopics': 0}
        )
        assert result.valid is False

        # Above range
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={'research_strategy': 'deep', 'max_subtopics': 15}
        )
        assert result.valid is False

        # Within range
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={'research_strategy': 'deep', 'max_subtopics': 5}
        )
        subtopic_errors = [e for e in result.errors if 'subtopic' in e.lower()]
        assert len(subtopic_errors) == 0

    def test_validate_warns_for_simple_strategy_options(self, agent_fetcher):
        """Test validation warns when comprehensive options used with simple strategy."""
        result = agent_fetcher.validate(
            "Test research topic for validation",
            config={
                'research_strategy': 'simple',
                'report_format': 'APA',
                'max_subtopics': 5,
            }
        )

        # Should have warnings about options being ignored
        assert len(result.warnings) >= 1
        warning_text = ' '.join(result.warnings).lower()
        assert 'ignored' in warning_text or 'simple' in warning_text


# =============================================================================
# Config Schema Tests for Strategy Fields
# =============================================================================


class TestAgentFetcherConfigSchemaStrategy:
    """Tests for strategy-related config schema fields."""

    def test_schema_has_research_strategy_field(self, agent_fetcher):
        """Test config schema includes research_strategy."""
        schema = agent_fetcher.get_config_schema()
        field_keys = [f.key for f in schema.fields]
        assert 'research_strategy' in field_keys

    def test_research_strategy_field_properties(self, agent_fetcher):
        """Test research_strategy field has correct properties."""
        schema = agent_fetcher.get_config_schema()
        strategy_field = next(f for f in schema.fields if f.key == 'research_strategy')

        assert strategy_field.type == 'select'
        assert strategy_field.default == 'simple'
        assert strategy_field.editable is True

    def test_schema_has_report_format_field(self, agent_fetcher):
        """Test config schema includes report_format."""
        schema = agent_fetcher.get_config_schema()
        field_keys = [f.key for f in schema.fields]
        assert 'report_format' in field_keys

    def test_report_format_field_properties(self, agent_fetcher):
        """Test report_format field has correct properties."""
        schema = agent_fetcher.get_config_schema()
        format_field = next(f for f in schema.fields if f.key == 'report_format')

        assert format_field.type == 'select'
        assert format_field.default == 'APA'

    def test_schema_has_max_subtopics_field(self, agent_fetcher):
        """Test config schema includes max_subtopics."""
        schema = agent_fetcher.get_config_schema()
        field_keys = [f.key for f in schema.fields]
        assert 'max_subtopics' in field_keys

    def test_max_subtopics_field_properties(self, agent_fetcher):
        """Test max_subtopics field has correct properties."""
        schema = agent_fetcher.get_config_schema()
        subtopics_field = next(f for f in schema.fields if f.key == 'max_subtopics')

        assert subtopics_field.type == 'integer'
        assert subtopics_field.default == 3

    def test_schema_has_search_provider_field(self, agent_fetcher):
        """Test config schema includes search_provider for per-source override."""
        schema = agent_fetcher.get_config_schema()
        field_keys = [f.key for f in schema.fields]
        assert 'search_provider' in field_keys
