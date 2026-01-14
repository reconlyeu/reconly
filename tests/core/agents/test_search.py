"""Tests for search provider integration.

Tests cover:
- Brave Search API provider
- SearXNG provider
- Search dispatcher (web_search)
- Result formatting
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
)
from reconly_core.agents.search.brave import (
    brave_search,
    BraveAuthError,
    BraveRateLimitError,
    BraveTimeoutError,
    BRAVE_SEARCH_URL,
)
from reconly_core.agents.search.searxng import (
    searxng_search,
    SearXNGConnectionError,
    SearXNGInvalidResponseError,
    SearXNGTimeoutError,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def brave_settings() -> AgentSettings:
    """Create settings configured for Brave Search."""
    return AgentSettings(
        search_provider="brave",
        brave_api_key="test-api-key-12345",
        max_search_results=5,
    )


@pytest.fixture
def searxng_settings() -> AgentSettings:
    """Create settings configured for SearXNG."""
    return AgentSettings(
        search_provider="searxng",
        searxng_url="http://localhost:8080",
        max_search_results=5,
    )


@pytest.fixture
def mock_brave_response() -> dict:
    """Sample Brave Search API response."""
    return {
        "web": {
            "results": [
                {
                    "title": "Python Async Tutorial",
                    "url": "https://example.com/python-async",
                    "description": "Learn async/await patterns in Python",
                },
                {
                    "title": "Asyncio Documentation",
                    "url": "https://docs.python.org/3/library/asyncio.html",
                    "description": "Official Python asyncio documentation",
                },
                {
                    "title": "Async Python Best Practices",
                    "url": "https://example.com/async-best-practices",
                    "description": "Tips for writing clean async code",
                },
            ]
        }
    }


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
# Brave Search Tests
# =============================================================================


class TestBraveSearch:
    """Tests for Brave Search API provider."""

    @pytest.mark.asyncio
    async def test_brave_search_success(self, brave_settings, mock_brave_response):
        """Successful Brave search returns parsed results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_brave_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await brave_search("python async", brave_settings)

            assert len(results) == 3
            assert results[0].title == "Python Async Tutorial"
            assert results[0].url == "https://example.com/python-async"
            assert results[0].snippet == "Learn async/await patterns in Python"

    @pytest.mark.asyncio
    async def test_brave_search_calls_correct_endpoint(self, brave_settings, mock_brave_response):
        """Brave search calls the correct API endpoint with proper headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_brave_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await brave_search("test query", brave_settings)

            mock_instance.get.assert_called_once()
            call_args = mock_instance.get.call_args

            assert call_args.args[0] == BRAVE_SEARCH_URL
            assert call_args.kwargs["headers"]["X-Subscription-Token"] == "test-api-key-12345"
            assert call_args.kwargs["params"]["q"] == "test query"
            assert call_args.kwargs["params"]["count"] == 5

    @pytest.mark.asyncio
    async def test_brave_search_missing_api_key(self):
        """Brave search raises error when API key is missing."""
        settings = AgentSettings(
            search_provider="brave",
            brave_api_key=None,
        )

        with pytest.raises(BraveAuthError, match="API key is required"):
            await brave_search("test", settings)

    @pytest.mark.asyncio
    async def test_brave_search_auth_error_401(self, brave_settings):
        """Brave search raises BraveAuthError on 401 response."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(BraveAuthError, match="Invalid API key"):
                await brave_search("test", brave_settings)

    @pytest.mark.asyncio
    async def test_brave_search_auth_error_403(self, brave_settings):
        """Brave search raises BraveAuthError on 403 response."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(BraveAuthError, match="lacks required permissions"):
                await brave_search("test", brave_settings)

    @pytest.mark.asyncio
    async def test_brave_search_rate_limit_error(self, brave_settings):
        """Brave search raises BraveRateLimitError on 429 response."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(BraveRateLimitError, match="Rate limit exceeded"):
                await brave_search("test", brave_settings)

    @pytest.mark.asyncio
    async def test_brave_search_timeout(self, brave_settings):
        """Brave search raises BraveTimeoutError on timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Connection timed out")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(BraveTimeoutError, match="timed out"):
                await brave_search("test", brave_settings)

    @pytest.mark.asyncio
    async def test_brave_search_empty_results(self, brave_settings):
        """Brave search handles empty results gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await brave_search("obscure query", brave_settings)

            assert results == []

    @pytest.mark.asyncio
    async def test_brave_search_missing_web_key(self, brave_settings):
        """Brave search handles missing 'web' key in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            results = await brave_search("test", brave_settings)

            assert results == []


# =============================================================================
# SearXNG Search Tests
# =============================================================================


class TestSearXNGSearch:
    """Tests for SearXNG provider."""

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
# Search Dispatcher Tests
# =============================================================================


class TestWebSearch:
    """Tests for the web_search dispatcher function."""

    @pytest.mark.asyncio
    async def test_web_search_routes_to_brave(self, brave_settings, mock_brave_response):
        """web_search routes to Brave when search_provider is 'brave'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_brave_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_search("python async", brave_settings)

            assert "Search Results:" in result
            assert "Python Async Tutorial" in result
            assert "https://example.com/python-async" in result

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
    async def test_web_search_invalid_provider(self):
        """web_search raises ValueError for unknown provider."""
        settings = AgentSettings(
            search_provider="google",  # Invalid
            brave_api_key="key",
        )

        with pytest.raises(ValueError, match="Unknown search provider"):
            await web_search("test", settings)

    @pytest.mark.asyncio
    async def test_web_search_wraps_provider_errors(self, brave_settings):
        """web_search wraps provider errors in WebSearchError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebSearchError, match="Search failed"):
                await web_search("test", brave_settings)


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
