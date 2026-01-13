"""Web content fetch tool for AI agents.

Fetches and extracts text content from URLs for LLM consumption.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30.0

# Default max content length to return (characters)
DEFAULT_MAX_CONTENT_LENGTH = 8000

# User agent for requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class WebFetchError(Exception):
    """Base exception for web fetch errors."""


class WebFetchTimeoutError(WebFetchError):
    """Raised when fetch times out."""


class WebFetchHTTPError(WebFetchError):
    """Raised for HTTP errors (404, 403, etc.)."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FetchResult:
    """Result of fetching a URL.

    Attributes:
        url: The URL that was fetched
        title: The page title (or "No title" if none found)
        content: The extracted text content
        truncated: Whether the content was truncated to max length
    """

    url: str
    title: str
    content: str
    truncated: bool = False


async def web_fetch(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
) -> FetchResult:
    """Fetch and extract content from a URL.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_content_length: Max characters to return (truncate if longer)

    Returns:
        FetchResult with title and extracted content

    Raises:
        WebFetchTimeoutError: If request times out
        WebFetchHTTPError: For HTTP errors (404, 403, etc.)
        WebFetchError: For other fetch failures
    """
    logger.debug("Fetching URL", extra={"url": url, "timeout": timeout})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                timeout=timeout,
                follow_redirects=True,
            )

            # Handle HTTP errors with descriptive messages
            status = response.status_code
            error_messages = {
                401: "Authentication required",
                403: "Access forbidden",
                404: "Page not found",
                410: "Page no longer exists",
                429: "Rate limited by server",
            }

            if status in error_messages:
                raise WebFetchHTTPError(error_messages[status], status)
            if status >= 500:
                raise WebFetchHTTPError(f"Server error: {status}", status)

            response.raise_for_status()

            # Extract content
            title, content = _extract_content(response.content)

            # Truncate if needed
            truncated = False
            if len(content) > max_content_length:
                content = content[:max_content_length]
                truncated = True

            logger.debug(
                "Fetch completed",
                extra={
                    "url": url,
                    "title": title,
                    "content_length": len(content),
                    "truncated": truncated,
                },
            )

            return FetchResult(
                url=url,
                title=title,
                content=content,
                truncated=truncated,
            )

    except httpx.TimeoutException as e:
        logger.warning("Fetch timeout", extra={"url": url})
        raise WebFetchTimeoutError(f"Request timed out after {timeout}s") from e

    except httpx.HTTPStatusError as e:
        logger.error(
            "Fetch HTTP error",
            extra={"url": url, "status_code": e.response.status_code},
        )
        raise WebFetchHTTPError(
            f"HTTP error: {e.response.status_code}", e.response.status_code
        ) from e

    except WebFetchError:
        # Re-raise our own errors without wrapping
        raise

    except httpx.RequestError as e:
        logger.error("Fetch request error", extra={"url": url, "error": str(e)})
        raise WebFetchError(f"Request failed: {e}") from e

    except Exception as e:
        logger.error("Unexpected fetch error", extra={"url": url, "error": str(e)})
        raise WebFetchError(f"Fetch failed: {e}") from e


def _extract_content(html_content: bytes) -> tuple[str, str]:
    """Extract title and main content from HTML.

    Args:
        html_content: Raw HTML bytes

    Returns:
        Tuple of (title, content)
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    # Get title
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else "No title"

    # Get main content - try different common content containers
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_="content")
        or soup.find("div", id="content")
        or soup.find("div", class_="post")
        or soup.find("div", class_="article")
        or soup.find("body")
    )

    content = ""
    if main_content:
        # Get text and clean it up
        content = main_content.get_text(separator="\n", strip=True)
        # Remove excessive newlines and whitespace
        content = "\n".join(
            line.strip() for line in content.split("\n") if line.strip()
        )

    return title, content


def format_fetch_result(result: FetchResult) -> str:
    """Format fetch result as markdown for LLM consumption.

    Args:
        result: The FetchResult to format

    Returns:
        Formatted markdown string
    """
    lines = [
        f"# {result.title}",
        f"URL: {result.url}",
        "",
        result.content,
    ]
    if result.truncated:
        lines.append("")
        lines.append("[Content truncated]")
    return "\n".join(lines)
