"""Tests for web fetch tool.

Tests cover:
- Successful URL fetching and content extraction
- HTTP error handling (404, 403, etc.)
- Timeout handling
- Content truncation
- Result formatting
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from reconly_core.agents.fetch import (
    web_fetch,
    format_fetch_result,
    FetchResult,
    WebFetchError,
    WebFetchTimeoutError,
    WebFetchHTTPError,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_CONTENT_LENGTH,
    _extract_content,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_html() -> bytes:
    """Simple HTML page for testing."""
    return b"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page Title</title>
    </head>
    <body>
        <header>Site Header</header>
        <nav>Navigation Menu</nav>
        <main>
            <h1>Main Content</h1>
            <p>This is the main content of the page.</p>
            <p>It has multiple paragraphs.</p>
        </main>
        <footer>Site Footer</footer>
    </body>
    </html>
    """


@pytest.fixture
def article_html() -> bytes:
    """HTML page with article content."""
    return b"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Article Title</title>
        <script>console.log('should be removed');</script>
        <style>.hidden { display: none; }</style>
    </head>
    <body>
        <header>Header</header>
        <article>
            <h1>The Article Headline</h1>
            <p>First paragraph of the article.</p>
            <p>Second paragraph with more details.</p>
        </article>
        <aside>Sidebar content</aside>
    </body>
    </html>
    """


@pytest.fixture
def minimal_html() -> bytes:
    """Minimal HTML without common containers."""
    return b"""
    <html>
    <body>
        <p>Just some body text.</p>
        <p>Nothing fancy here.</p>
    </body>
    </html>
    """


@pytest.fixture
def long_content_html() -> bytes:
    """HTML with content exceeding default max length."""
    content = "X" * 10000
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Long Page</title></head>
    <body>
        <main>{content}</main>
    </body>
    </html>
    """.encode()


# =============================================================================
# Content Extraction Tests
# =============================================================================


class TestExtractContent:
    """Tests for _extract_content helper function."""

    def test_extract_title(self, simple_html):
        """Extracts title from HTML."""
        title, _ = _extract_content(simple_html)
        assert title == "Test Page Title"

    def test_extract_main_content(self, simple_html):
        """Extracts content from <main> element."""
        _, content = _extract_content(simple_html)
        assert "Main Content" in content
        assert "main content of the page" in content
        assert "multiple paragraphs" in content

    def test_removes_header_and_footer(self, simple_html):
        """Header, footer, and nav content is removed."""
        _, content = _extract_content(simple_html)
        assert "Site Header" not in content
        assert "Site Footer" not in content
        assert "Navigation Menu" not in content

    def test_removes_script_and_style(self, article_html):
        """Script and style elements are removed."""
        _, content = _extract_content(article_html)
        assert "should be removed" not in content
        assert ".hidden" not in content

    def test_removes_aside_content(self, article_html):
        """Aside content is removed."""
        _, content = _extract_content(article_html)
        assert "Sidebar content" not in content

    def test_extract_article_content(self, article_html):
        """Extracts content from <article> element when no <main>."""
        _, content = _extract_content(article_html)
        assert "Article Headline" in content
        assert "First paragraph" in content
        assert "Second paragraph" in content

    def test_falls_back_to_body(self, minimal_html):
        """Falls back to body content when no semantic containers."""
        _, content = _extract_content(minimal_html)
        assert "Just some body text" in content
        assert "Nothing fancy here" in content

    def test_no_title_returns_default(self):
        """Returns 'No title' when title tag is missing."""
        html = b"<html><body><p>Content</p></body></html>"
        title, _ = _extract_content(html)
        assert title == "No title"

    def test_empty_html(self):
        """Handles empty HTML gracefully."""
        title, content = _extract_content(b"")
        assert title == "No title"
        assert content == ""

    def test_cleans_excessive_whitespace(self):
        """Removes excessive whitespace and empty lines."""
        html = b"""
        <html>
        <body>
            <main>
                <p>Line one</p>


                <p>Line two</p>
            </main>
        </body>
        </html>
        """
        _, content = _extract_content(html)
        # Should not have excessive blank lines
        lines = content.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]
        assert len(non_empty_lines) == len(lines)


# =============================================================================
# Web Fetch Success Tests
# =============================================================================


class TestWebFetchSuccess:
    """Tests for successful web_fetch operations."""

    @pytest.mark.asyncio
    async def test_fetch_returns_result(self, simple_html):
        """Successful fetch returns FetchResult."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = simple_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_fetch("https://example.com/page")

            assert isinstance(result, FetchResult)
            assert result.url == "https://example.com/page"
            assert result.title == "Test Page Title"
            assert "Main Content" in result.content
            assert result.truncated is False

    @pytest.mark.asyncio
    async def test_fetch_sends_correct_headers(self, simple_html):
        """Fetch sends appropriate headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = simple_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await web_fetch("https://example.com/page")

            call_args = mock_instance.get.call_args
            headers = call_args.kwargs["headers"]

            assert "User-Agent" in headers
            assert "text/html" in headers["Accept"]

    @pytest.mark.asyncio
    async def test_fetch_follows_redirects(self, simple_html):
        """Fetch is configured to follow redirects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = simple_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await web_fetch("https://example.com/page")

            call_args = mock_instance.get.call_args
            assert call_args.kwargs["follow_redirects"] is True

    @pytest.mark.asyncio
    async def test_fetch_uses_custom_timeout(self, simple_html):
        """Fetch uses provided timeout value."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = simple_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await web_fetch("https://example.com/page", timeout=60.0)

            call_args = mock_instance.get.call_args
            assert call_args.kwargs["timeout"] == 60.0


# =============================================================================
# Content Truncation Tests
# =============================================================================


class TestContentTruncation:
    """Tests for content truncation behavior."""

    @pytest.mark.asyncio
    async def test_truncates_long_content(self, long_content_html):
        """Content exceeding max length is truncated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = long_content_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_fetch("https://example.com/long")

            assert result.truncated is True
            assert len(result.content) == DEFAULT_MAX_CONTENT_LENGTH

    @pytest.mark.asyncio
    async def test_custom_max_length(self, long_content_html):
        """Respects custom max_content_length parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = long_content_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_fetch(
                "https://example.com/long",
                max_content_length=1000,
            )

            assert result.truncated is True
            assert len(result.content) == 1000

    @pytest.mark.asyncio
    async def test_no_truncation_under_limit(self, simple_html):
        """Content under max length is not truncated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = simple_html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await web_fetch("https://example.com/short")

            assert result.truncated is False


# =============================================================================
# HTTP Error Tests
# =============================================================================


class TestWebFetchHTTPErrors:
    """Tests for HTTP error handling."""

    @pytest.mark.asyncio
    async def test_404_raises_http_error(self):
        """404 response raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/missing")

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_403_raises_http_error(self):
        """403 response raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/forbidden")

            assert exc_info.value.status_code == 403
            assert "forbidden" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_401_raises_http_error(self):
        """401 response raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/auth")

            assert exc_info.value.status_code == 401
            assert "authentication" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_429_raises_http_error(self):
        """429 rate limit response raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/ratelimit")

            assert exc_info.value.status_code == 429
            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_500_raises_http_error(self):
        """500 server error raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/error")

            assert exc_info.value.status_code == 500
            assert "server error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_503_raises_http_error(self):
        """503 service unavailable raises WebFetchHTTPError."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchHTTPError) as exc_info:
                await web_fetch("https://example.com/unavailable")

            assert exc_info.value.status_code == 503


# =============================================================================
# Timeout Tests
# =============================================================================


class TestWebFetchTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        """Request timeout raises WebFetchTimeoutError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Connection timed out")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchTimeoutError) as exc_info:
                await web_fetch("https://example.com/slow")

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_includes_duration(self):
        """Timeout error message includes timeout duration."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchTimeoutError) as exc_info:
                await web_fetch("https://example.com/slow", timeout=15.0)

            assert "15" in str(exc_info.value)


# =============================================================================
# Connection Error Tests
# =============================================================================


class TestWebFetchConnectionErrors:
    """Tests for connection error handling."""

    @pytest.mark.asyncio
    async def test_connection_error_raises_fetch_error(self):
        """Connection error raises WebFetchError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchError) as exc_info:
                await web_fetch("https://example.com/unreachable")

            assert "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_dns_error_raises_fetch_error(self):
        """DNS resolution error raises WebFetchError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.RequestError(
                "DNS resolution failed",
                request=MagicMock(),
            )
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with pytest.raises(WebFetchError):
                await web_fetch("https://nonexistent.invalid/page")


# =============================================================================
# Format Result Tests
# =============================================================================


class TestFormatFetchResult:
    """Tests for format_fetch_result function."""

    def test_format_basic_result(self):
        """Formats basic result as markdown."""
        result = FetchResult(
            url="https://example.com/article",
            title="Test Article Title",
            content="This is the article content.\nWith multiple lines.",
            truncated=False,
        )

        formatted = format_fetch_result(result)

        assert "# Test Article Title" in formatted
        assert "URL: https://example.com/article" in formatted
        assert "This is the article content." in formatted
        assert "With multiple lines." in formatted
        assert "[Content truncated]" not in formatted

    def test_format_truncated_result(self):
        """Indicates when content is truncated."""
        result = FetchResult(
            url="https://example.com/long",
            title="Long Article",
            content="Truncated content here...",
            truncated=True,
        )

        formatted = format_fetch_result(result)

        assert "[Content truncated]" in formatted

    def test_format_empty_content(self):
        """Handles empty content gracefully."""
        result = FetchResult(
            url="https://example.com/empty",
            title="Empty Page",
            content="",
            truncated=False,
        )

        formatted = format_fetch_result(result)

        assert "# Empty Page" in formatted
        assert "URL: https://example.com/empty" in formatted

    def test_format_preserves_special_characters(self):
        """Preserves special characters in title and content."""
        result = FetchResult(
            url="https://example.com/special",
            title="Python & JavaScript: A <Comparison>",
            content="Use ** for bold and __ for italic.",
            truncated=False,
        )

        formatted = format_fetch_result(result)

        assert "Python & JavaScript: A <Comparison>" in formatted
        assert "** for bold" in formatted


# =============================================================================
# Default Values Tests
# =============================================================================


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_timeout_value(self):
        """Default timeout is 30 seconds."""
        assert DEFAULT_TIMEOUT == 30.0

    def test_default_max_content_length(self):
        """Default max content length is 8000 characters."""
        assert DEFAULT_MAX_CONTENT_LENGTH == 8000
