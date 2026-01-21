"""Tests for search provider integration.

Tests cover:
- SearXNG provider (class-based and legacy wrapper)
- Search dispatcher (web_search)
- Result formatting
- Retry logic
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from reconly_core.agents.settings import AgentSettings
from reconly_core.agents.search import (
    web_search,
    format_search_results,
    SearchResult,
    WebSearchError,
    SearXNGProvider,
    get_search_provider,
    list_providers,
    SEARCH_PROVIDERS,
)
from reconly_core.agents.search.searxng import (
    searxng_search,
    SearXNGConnectionError,
    SearXNGInvalidResponseError,
    SearXNGTimeoutError,
    SearXNGSearchError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def searxng_settings() -> AgentSettings:
    """Create settings configured for SearXNG."""
    return AgentSettings(
        search_provider="searxng",
        searxng_url="http://localhost:8080",
        max_search_results=5,
    )


@pytest.fixture
def mock_searxng_response() -> dict:
    """Sample SearXNG JSON response."""
    return {
        "results": [
            {
                "title": "FastAPI Documentation",
                "url": "https://fastapi.tiangolo.com",
                "content": "FastAPI framework for building APIs with Python",
            },
            {
                "title": "HTTPX Library",
                "url": "https://www.python-httpx.org",
                "content": "A next-generation HTTP client for Python",
            },
            {
                "title": "Async Python Guide",
                "url": "https://example.com/async-guide",
                "content": "Complete guide to async programming",
            },
        ]
    }


# =============================================================================
# Provider Registry Tests
# =============================================================================


class TestProviderRegistry:
    """Tests for the search provider registry."""

    def test_searxng_is_registered(self):
        """SearXNG should be registered in SEARCH_PROVIDERS."""
        assert "searxng" in SEARCH_PROVIDERS
        assert SEARCH_PROVIDERS["searxng"] is SearXNGProvider

    def test_duckduckgo_is_registered(self):
        """DuckDuckGo should be registered in SEARCH_PROVIDERS."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        assert "duckduckgo" in SEARCH_PROVIDERS
        assert SEARCH_PROVIDERS["duckduckgo"] is DuckDuckGoProvider

    def test_tavily_is_registered(self):
        """Tavily should be registered in SEARCH_PROVIDERS."""
        from reconly_core.agents.search.tavily import TavilyProvider

        assert "tavily" in SEARCH_PROVIDERS
        assert SEARCH_PROVIDERS["tavily"] is TavilyProvider

    def test_list_providers_returns_all(self):
        """list_providers should return all three providers."""
        providers = list_providers()
        assert "searxng" in providers
        assert "duckduckgo" in providers
        assert "tavily" in providers

    def test_get_search_provider_returns_instance(self, searxng_settings):
        """get_search_provider should return a configured provider instance."""
        provider = get_search_provider("searxng", searxng_settings)
        assert isinstance(provider, SearXNGProvider)
        assert provider.base_url == "http://localhost:8080"

    def test_get_duckduckgo_provider(self):
        """get_search_provider should return DuckDuckGoProvider instance."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        settings = AgentSettings(search_provider="duckduckgo")
        provider = get_search_provider("duckduckgo", settings)
        assert isinstance(provider, DuckDuckGoProvider)

    def test_get_tavily_provider(self):
        """get_search_provider should return TavilyProvider instance."""
        from reconly_core.agents.search.tavily import TavilyProvider

        settings = AgentSettings(
            search_provider="tavily",
            tavily_api_key="test-key",
        )
        provider = get_search_provider("tavily", settings)
        assert isinstance(provider, TavilyProvider)

    def test_get_search_provider_unknown_raises_error(self, searxng_settings):
        """get_search_provider should raise ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unknown search provider"):
            get_search_provider("unknown", searxng_settings)


# =============================================================================
# SearXNG Provider Class Tests
# =============================================================================


class TestSearXNGProvider:
    """Tests for SearXNGProvider class."""

    def test_provider_class_attributes(self):
        """SearXNGProvider should have correct class attributes."""
        assert SearXNGProvider.name == "searxng"
        assert SearXNGProvider.requires_api_key is False

    def test_provider_initialization(self):
        """SearXNGProvider should initialize with base_url."""
        provider = SearXNGProvider(base_url="http://localhost:8080")
        assert provider.base_url == "http://localhost:8080"

    def test_provider_normalizes_trailing_slash(self):
        """SearXNGProvider should normalize trailing slash in URL."""
        provider = SearXNGProvider(base_url="http://localhost:8080/")
        assert provider.base_url == "http://localhost:8080"

    def test_provider_raises_on_empty_url(self):
        """SearXNGProvider should raise error on empty URL."""
        with pytest.raises(SearXNGConnectionError, match="URL is required"):
            SearXNGProvider(base_url="")

    def test_get_config_schema(self):
        """SearXNGProvider.get_config_schema should return correct schema."""
        schema = SearXNGProvider.get_config_schema()
        assert "searxng_url" in schema
        assert schema["searxng_url"]["type"] == "string"
        assert schema["searxng_url"]["required"] is True
        assert schema["searxng_url"]["env_var"] == "SEARXNG_URL"

    @pytest.mark.asyncio
    async def test_provider_search_success(self, mock_searxng_response):
        """SearXNGProvider.search returns parsed results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            provider = SearXNGProvider(base_url="http://localhost:8080")
            results = await provider.search("fastapi", max_results=10)

            assert len(results) == 3
            assert results[0].title == "FastAPI Documentation"
            assert results[0].url == "https://fastapi.tiangolo.com"
            assert results[0].snippet == "FastAPI framework for building APIs with Python"


# =============================================================================
# SearXNG Search Tests (Legacy Wrapper)
# =============================================================================


class TestSearXNGSearch:
    """Tests for SearXNG provider (legacy wrapper)."""

    @pytest.mark.asyncio
    async def test_searxng_search_success(self, searxng_settings, mock_searxng_response):
        """Successful SearXNG search returns parsed results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await searxng_search("fastapi", searxng_settings)

            assert len(results) == 3
            assert results[0].title == "FastAPI Documentation"
            assert results[0].url == "https://fastapi.tiangolo.com"
            assert results[0].snippet == "FastAPI framework for building APIs with Python"

    @pytest.mark.asyncio
    async def test_searxng_search_calls_correct_endpoint(self, searxng_settings, mock_searxng_response):
        """SearXNG search calls the correct endpoint with proper params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await searxng_search("test query", searxng_settings)

            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args

            assert call_args.args[0] == "http://localhost:8080/search"
            assert call_args.kwargs["params"]["q"] == "test query"
            assert call_args.kwargs["params"]["format"] == "json"
            assert call_args.kwargs["params"]["categories"] == "general"

    @pytest.mark.asyncio
    async def test_searxng_search_normalizes_url(self, mock_searxng_response):
        """SearXNG search normalizes trailing slash in URL."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="http://localhost:8080/",  # Note trailing slash
            max_search_results=5,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await searxng_search("test", settings)

            call_args = mock_instance.get.call_args
            # Should not have double slash
            assert call_args.args[0] == "http://localhost:8080/search"

    @pytest.mark.asyncio
    async def test_searxng_search_missing_url(self):
        """SearXNG search raises error when URL is missing."""
        settings = AgentSettings(
            search_provider="searxng",
            searxng_url="",
        )

        with pytest.raises(SearXNGConnectionError, match="URL is required"):
            await searxng_search("test", settings)

    @pytest.mark.asyncio
    async def test_searxng_search_connection_error(self, searxng_settings):
        """SearXNG search raises SearXNGConnectionError on connection failure."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # Simulate connection error twice (initial + 1 retry)
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(SearXNGConnectionError, match="Failed to connect"):
                await searxng_search("test", searxng_settings)

    @pytest.mark.asyncio
    async def test_searxng_search_timeout(self, searxng_settings):
        """SearXNG search raises SearXNGTimeoutError on timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # Simulate timeout twice (initial + 1 retry)
            mock_instance.get.side_effect = httpx.TimeoutException("Request timed out")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(SearXNGTimeoutError, match="timed out"):
                await searxng_search("test", searxng_settings)

    @pytest.mark.asyncio
    async def test_searxng_search_invalid_json(self, searxng_settings):
        """SearXNG search raises SearXNGInvalidResponseError on invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(SearXNGInvalidResponseError, match="Failed to parse"):
                await searxng_search("test", searxng_settings)

    @pytest.mark.asyncio
    async def test_searxng_search_invalid_response_type(self, searxng_settings):
        """SearXNG search raises error when response is not a dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["not", "a", "dict"]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(SearXNGInvalidResponseError, match="Expected dict"):
                await searxng_search("test", searxng_settings)

    @pytest.mark.asyncio
    async def test_searxng_search_respects_max_results(self, searxng_settings):
        """SearXNG search respects max_search_results setting."""
        many_results = {
            "results": [
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": f"Content {i}"}
                for i in range(20)
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = many_results
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await searxng_search("test", searxng_settings)

            # Should be limited to max_search_results (5)
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_searxng_search_empty_results(self, searxng_settings):
        """SearXNG search handles empty results gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await searxng_search("obscure query", searxng_settings)

            assert results == []


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestRetryLogic:
    """Tests for SearXNG retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout_succeeds_on_second_attempt(self, mock_searxng_response):
        """Search should succeed on retry after initial timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("First attempt timeout")
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = mock_get
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                provider = SearXNGProvider(base_url="http://localhost:8080")
                results = await provider.search("test", max_results=10)

                assert len(results) == 3
                assert call_count == 2
                mock_sleep.assert_called_once_with(1.0)

    @pytest.mark.asyncio
    async def test_retry_on_connection_error_succeeds_on_second_attempt(self, mock_searxng_response):
        """Search should succeed on retry after initial connection error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("First attempt connection error")
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = mock_get
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                provider = SearXNGProvider(base_url="http://localhost:8080")
                results = await provider.search("test", max_results=10)

                assert len(results) == 3
                assert call_count == 2
                mock_sleep.assert_called_once_with(1.0)

    @pytest.mark.asyncio
    async def test_no_retry_on_invalid_response(self, searxng_settings):
        """Non-transient errors (like invalid response) should not be retried."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["not", "a", "dict"]
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = mock_get
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            provider = SearXNGProvider(base_url="http://localhost:8080")
            with pytest.raises(SearXNGInvalidResponseError):
                await provider.search("test", max_results=10)

            # Should only be called once (no retry for non-transient errors)
            assert call_count == 1


# =============================================================================
# Search Dispatcher Tests
# =============================================================================


class TestWebSearch:
    """Tests for the web_search dispatcher function."""

    @pytest.mark.asyncio
    async def test_web_search_routes_to_searxng(self, searxng_settings, mock_searxng_response):
        """web_search routes to SearXNG when search_provider is 'searxng'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_searxng_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_search("fastapi", searxng_settings)

            assert "Search Results:" in result
            assert "FastAPI Documentation" in result
            assert "https://fastapi.tiangolo.com" in result

    @pytest.mark.asyncio
    async def test_web_search_routes_to_duckduckgo(self):
        """web_search routes to DuckDuckGo when search_provider is 'duckduckgo'."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        settings = AgentSettings(search_provider="duckduckgo")

        mock_results = [
            SearchResult(
                title="DDG Result",
                url="https://example.com",
                snippet="DDG Snippet",
            )
        ]

        with patch.object(DuckDuckGoProvider, "_search_sync", return_value=mock_results):
            result = await web_search("test query", settings)

            assert "Search Results:" in result
            assert "DDG Result" in result
            assert "https://example.com" in result

    @pytest.mark.asyncio
    async def test_web_search_routes_to_tavily(self):
        """web_search routes to Tavily when search_provider is 'tavily'."""
        from reconly_core.agents.search.tavily import TavilyProvider

        settings = AgentSettings(
            search_provider="tavily",
            tavily_api_key="test-key",
        )

        mock_results = [
            SearchResult(
                title="Tavily Result",
                url="https://example.com",
                snippet="Tavily Snippet",
            )
        ]

        with patch.object(TavilyProvider, "_search_sync", return_value=mock_results):
            result = await web_search("AI research", settings)

            assert "Search Results:" in result
            assert "Tavily Result" in result
            assert "https://example.com" in result

    @pytest.mark.asyncio
    async def test_web_search_invalid_provider(self):
        """web_search raises ValueError for unknown provider."""
        settings = AgentSettings(
            search_provider="google",  # Invalid
            searxng_url="http://localhost:8080",
        )

        with pytest.raises(ValueError, match="Unknown search provider"):
            await web_search("test", settings)

    @pytest.mark.asyncio
    async def test_web_search_wraps_provider_errors(self, searxng_settings):
        """web_search wraps provider errors in WebSearchError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # Both attempts fail (initial + 1 retry)
            mock_instance.get.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebSearchError, match="Search failed"):
                await web_search("test", searxng_settings)


# =============================================================================
# Result Formatting Tests
# =============================================================================


class TestFormatSearchResults:
    """Tests for format_search_results function."""

    def test_format_empty_results(self):
        """format_search_results handles empty list."""
        result = format_search_results([])
        assert result == "No results found."

    def test_format_single_result(self):
        """format_search_results formats a single result."""
        results = [
            SearchResult(
                title="Test Title",
                snippet="Test snippet content",
                url="https://example.com/test",
            )
        ]

        formatted = format_search_results(results)

        assert "Search Results:" in formatted
        assert "1. **Test Title**" in formatted
        assert "URL: https://example.com/test" in formatted
        assert "Test snippet content" in formatted

    def test_format_multiple_results(self):
        """format_search_results formats multiple results with numbering."""
        results = [
            SearchResult(title="First", snippet="First snippet", url="https://example.com/1"),
            SearchResult(title="Second", snippet="Second snippet", url="https://example.com/2"),
            SearchResult(title="Third", snippet="Third snippet", url="https://example.com/3"),
        ]

        formatted = format_search_results(results)

        assert "1. **First**" in formatted
        assert "2. **Second**" in formatted
        assert "3. **Third**" in formatted

    def test_format_result_without_snippet(self):
        """format_search_results handles missing snippet gracefully."""
        results = [
            SearchResult(
                title="No Snippet",
                snippet="",
                url="https://example.com/no-snippet",
            )
        ]

        formatted = format_search_results(results)

        assert "1. **No Snippet**" in formatted
        assert "URL: https://example.com/no-snippet" in formatted
        # Should not have extra empty snippet line
        lines = formatted.split("\n")
        url_line_idx = next(i for i, line in enumerate(lines) if "URL:" in line)
        # Next non-empty line should be blank (section separator), not snippet
        assert lines[url_line_idx + 1] == ""

    def test_format_preserves_special_characters(self):
        """format_search_results preserves special characters in titles and snippets."""
        results = [
            SearchResult(
                title="C++ & Python: A <Comparison>",
                snippet="Learn how to use ** and other operators",
                url="https://example.com/cpp-python",
            )
        ]

        formatted = format_search_results(results)

        assert "C++ & Python: A <Comparison>" in formatted
        assert "** and other operators" in formatted


# =============================================================================
# DuckDuckGo Provider Tests
# =============================================================================


class TestDuckDuckGoProvider:
    """Tests for DuckDuckGoProvider class."""

    def test_provider_class_attributes(self):
        """DuckDuckGoProvider should have correct class attributes."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        assert DuckDuckGoProvider.name == "duckduckgo"
        assert DuckDuckGoProvider.requires_api_key is False

    def test_provider_initialization(self):
        """DuckDuckGoProvider should initialize without arguments."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        provider = DuckDuckGoProvider()
        assert provider is not None

    def test_get_config_schema_empty(self):
        """DuckDuckGoProvider.get_config_schema should return empty dict."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        schema = DuckDuckGoProvider.get_config_schema()
        assert schema == {}

    @pytest.mark.asyncio
    async def test_provider_search_success(self):
        """DuckDuckGoProvider.search returns parsed results."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        mock_results = [
            SearchResult(
                title="Result 1",
                url="https://example.com/1",
                snippet="Snippet 1",
            ),
            SearchResult(
                title="Result 2",
                url="https://example.com/2",
                snippet="Snippet 2",
            ),
        ]

        provider = DuckDuckGoProvider()
        with patch.object(provider, "_search_sync", return_value=mock_results):
            results = await provider.search("test query", max_results=10)

            assert len(results) == 2
            assert results[0].title == "Result 1"
            assert results[0].url == "https://example.com/1"
            assert results[0].snippet == "Snippet 1"

    @pytest.mark.asyncio
    async def test_provider_search_rate_limit_retry(self):
        """DuckDuckGoProvider should retry on rate limit errors."""
        from reconly_core.agents.search.duckduckgo import (
            DuckDuckGoProvider,
            DuckDuckGoRateLimitError,
        )

        call_count = 0

        def mock_search_sync(query, max_results):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DuckDuckGoRateLimitError("Rate limited")

            # Return results on third attempt
            return [
                SearchResult(
                    title="Result",
                    url="https://example.com",
                    snippet="Snippet",
                )
            ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            provider = DuckDuckGoProvider()
            with patch.object(provider, "_search_sync", side_effect=mock_search_sync):
                results = await provider.search("test", max_results=10)

                assert len(results) == 1
                assert call_count == 3  # 2 rate limits + 1 success

    @pytest.mark.asyncio
    async def test_provider_search_timeout(self):
        """DuckDuckGoProvider should raise timeout error."""
        from reconly_core.agents.search.duckduckgo import (
            DuckDuckGoProvider,
            DuckDuckGoTimeoutError,
        )
        import time

        provider = DuckDuckGoProvider(timeout=0.001)  # Very short timeout

        def slow_sync_operation(*args):
            # Synchronous sleep to block the executor
            time.sleep(1.0)

        with patch.object(provider, "_search_sync", side_effect=slow_sync_operation):
            with pytest.raises(DuckDuckGoTimeoutError, match="timed out"):
                await provider.search("test", max_results=10)

    @pytest.mark.asyncio
    async def test_provider_search_handles_none_results(self):
        """DuckDuckGoProvider should handle None results gracefully."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        provider = DuckDuckGoProvider()
        with patch.object(provider, "_search_sync", return_value=[]):
            results = await provider.search("test query", max_results=10)
            assert results == []

    @pytest.mark.asyncio
    async def test_provider_search_skips_invalid_results(self):
        """DuckDuckGoProvider should skip results without title or URL."""
        from reconly_core.agents.search.duckduckgo import DuckDuckGoProvider

        # Only valid result is returned by _search_sync (it filters internally)
        mock_results = [
            SearchResult(
                title="Valid",
                url="https://example.com",
                snippet="Snippet",
            )
        ]

        provider = DuckDuckGoProvider()
        with patch.object(provider, "_search_sync", return_value=mock_results):
            results = await provider.search("test query", max_results=10)

            # Should only include the valid result
            assert len(results) == 1
            assert results[0].title == "Valid"


# =============================================================================
# Tavily Provider Tests
# =============================================================================


class TestTavilyProvider:
    """Tests for TavilyProvider class."""

    def test_provider_class_attributes(self):
        """TavilyProvider should have correct class attributes."""
        from reconly_core.agents.search.tavily import TavilyProvider

        assert TavilyProvider.name == "tavily"
        assert TavilyProvider.requires_api_key is True

    def test_provider_initialization_with_api_key(self):
        """TavilyProvider should initialize with API key."""
        from reconly_core.agents.search.tavily import TavilyProvider

        provider = TavilyProvider(api_key="test-api-key")
        assert provider._api_key == "test-api-key"

    def test_provider_initialization_without_api_key_raises(self):
        """TavilyProvider should raise error without API key."""
        from reconly_core.agents.search.tavily import (
            TavilyProvider,
            TavilyAuthError,
        )

        with pytest.raises(TavilyAuthError, match="API key is required"):
            TavilyProvider(api_key="")

    def test_get_config_schema(self):
        """TavilyProvider.get_config_schema should return API key config."""
        from reconly_core.agents.search.tavily import TavilyProvider

        schema = TavilyProvider.get_config_schema()
        assert "tavily_api_key" in schema
        assert schema["tavily_api_key"]["required"] is True
        assert schema["tavily_api_key"]["secret"] is True
        assert schema["tavily_api_key"]["env_var"] == "TAVILY_API_KEY"

    @pytest.mark.asyncio
    async def test_provider_search_success(self):
        """TavilyProvider.search returns parsed results."""
        from reconly_core.agents.search.tavily import TavilyProvider

        mock_results = [
            SearchResult(
                title="AI News",
                url="https://ai.com/news",
                snippet="Latest AI developments",
            ),
            SearchResult(
                title="ML Guide",
                url="https://ml.com/guide",
                snippet="Machine learning guide",
            ),
        ]

        provider = TavilyProvider(api_key="test-key")
        with patch.object(provider, "_search_sync", return_value=mock_results):
            results = await provider.search("AI research", max_results=10)

            assert len(results) == 2
            assert results[0].title == "AI News"
            assert results[0].url == "https://ai.com/news"
            assert results[0].snippet == "Latest AI developments"

    @pytest.mark.asyncio
    async def test_provider_search_auth_error(self):
        """TavilyProvider should raise auth error for invalid API key."""
        from reconly_core.agents.search.tavily import (
            TavilyProvider,
            TavilyAuthError,
        )

        def mock_search_sync(*args):
            raise TavilyAuthError("Invalid Tavily API key")

        provider = TavilyProvider(api_key="invalid-key")
        with patch.object(provider, "_search_sync", side_effect=mock_search_sync):
            with pytest.raises(TavilyAuthError, match="Invalid"):
                await provider.search("test", max_results=10)

    @pytest.mark.asyncio
    async def test_provider_search_rate_limit_error(self):
        """TavilyProvider should raise rate limit error."""
        from reconly_core.agents.search.tavily import (
            TavilyProvider,
            TavilyRateLimitError,
        )

        def mock_search_sync(*args):
            raise TavilyRateLimitError("Tavily rate limit exceeded")

        provider = TavilyProvider(api_key="test-key")
        with patch.object(provider, "_search_sync", side_effect=mock_search_sync):
            with pytest.raises(TavilyRateLimitError, match="rate limit"):
                await provider.search("test", max_results=10)

    @pytest.mark.asyncio
    async def test_provider_search_timeout(self):
        """TavilyProvider should raise timeout error."""
        from reconly_core.agents.search.tavily import (
            TavilyProvider,
            TavilyTimeoutError,
        )
        import time

        provider = TavilyProvider(api_key="test-key", timeout=0.001)

        def slow_sync_operation(*args):
            # Synchronous sleep to block the executor
            time.sleep(1.0)

        with patch.object(provider, "_search_sync", side_effect=slow_sync_operation):
            with pytest.raises(TavilyTimeoutError, match="timed out"):
                await provider.search("test", max_results=10)

    @pytest.mark.asyncio
    async def test_provider_search_handles_empty_results(self):
        """TavilyProvider should handle empty results gracefully."""
        from reconly_core.agents.search.tavily import TavilyProvider

        provider = TavilyProvider(api_key="test-key")
        with patch.object(provider, "_search_sync", return_value=[]):
            results = await provider.search("obscure query", max_results=10)
            assert results == []

    @pytest.mark.asyncio
    async def test_provider_search_skips_invalid_results(self):
        """TavilyProvider should skip results without title or URL."""
        from reconly_core.agents.search.tavily import TavilyProvider

        # Only valid result is returned by _search_sync (it filters internally)
        mock_results = [
            SearchResult(
                title="Valid",
                url="https://example.com",
                snippet="Snippet",
            )
        ]

        provider = TavilyProvider(api_key="test-key")
        with patch.object(provider, "_search_sync", return_value=mock_results):
            results = await provider.search("test query", max_results=10)

            # Should only include the valid result
            assert len(results) == 1
            assert results[0].title == "Valid"
