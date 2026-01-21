"""Website content fetcher module."""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from reconly_core.fetchers.base import BaseFetcher, ValidationResult
from reconly_core.fetchers.metadata import FetcherMetadata
from reconly_core.fetchers.registry import register_fetcher


@register_fetcher('website')
class WebsiteFetcher(BaseFetcher):
    """Fetches and extracts content from websites."""

    metadata = FetcherMetadata(
        name='website',
        display_name='Website',
        description='Scrape content from web pages',
        icon='mdi:web',
        url_schemes=['http', 'https'],
        supports_incremental=False,
        supports_validation=True,
        supports_test_fetch=True,
    )

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch content from a website URL.

        Args:
            url: The URL to fetch content from
            since: Ignored for websites (single page fetch)
            max_items: Ignored for websites (single page fetch)

        Returns:
            List containing a single dictionary with 'title', 'content', 'url', and 'source_type' keys
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "No title"

            # Get main content - try different common content containers
            # Order matters: more specific selectors first, then broader ones
            content = ""

            # Try specific blog/article content selectors first (most likely to have actual content)
            content_selectors = [
                # Common blog content classes
                ('div', {'class_': 'post-content'}),
                ('div', {'class_': 'entry-content'}),
                ('div', {'class_': 'article-content'}),
                ('div', {'class_': 'blog-content'}),
                ('div', {'class_': 'markdown-body'}),  # GitHub, tech blogs
                ('div', {'class_': 'prose'}),  # Tailwind prose class
                ('div', {'class_': 'content-body'}),
                # Hugging Face specific
                ('div', {'class_': 'container'}),
                # Generic semantic elements
                ('article', {}),
                ('main', {}),
                # Generic content divs
                ('div', {'class_': 'content'}),
                ('div', {'id': 'content'}),
                ('div', {'class_': 'post'}),
                ('div', {'id': 'post'}),
                # ARIA role
                ('div', {'attrs': {'role': 'main'}}),
            ]

            # Find the best content container (prefer ones with more text)
            best_content = ""

            for tag, attrs in content_selectors:
                if 'attrs' in attrs:
                    element = soup.find(tag, attrs=attrs['attrs'])
                else:
                    element = soup.find(tag, **attrs) if attrs else soup.find(tag)

                if element:
                    text = element.get_text(separator='\n', strip=True)
                    # Use this element if it has more content than what we found so far
                    # Minimum threshold of 100 chars to avoid picking up headers/navs
                    if len(text) > len(best_content) and len(text) > 100:
                        best_content = text

            # Fall back to body if no good content found
            if not best_content:
                body = soup.find('body')
                if body:
                    best_content = body.get_text(separator='\n', strip=True)

            if best_content:
                # Remove excessive newlines
                content = '\n'.join(line.strip() for line in best_content.split('\n') if line.strip())

            return [{
                'url': url,
                'title': title_text,
                'content': content,
                'source_type': 'website'
            }]

        except requests.RequestException as e:
            raise Exception(f"Failed to fetch website: {str(e)}")

    def get_source_type(self) -> str:
        """Get the source type identifier."""
        return 'website'

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the given URL.

        Returns True for URLs that look like regular web pages
        (not RSS feeds, YouTube, etc.).
        """
        url_lower = url.lower()

        # Exclude URLs handled by other fetchers
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return False
        if any(x in url_lower for x in ['/feed', '/rss', '/atom', '.xml']):
            return False

        # Accept HTTP/HTTPS URLs
        return url_lower.startswith('http://') or url_lower.startswith('https://')

    def get_description(self) -> str:
        """Get a human-readable description of this fetcher."""
        return 'Website content extractor'

    def __del__(self):
        """Close the session."""
        if hasattr(self, 'session'):
            self.session.close()

    def validate(
        self,
        url: str,
        config: Optional[Dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate website URL and optionally test accessibility.

        Validates:
        - Basic URL format (via base class)
        - URL is not handled by other fetchers (YouTube, RSS)
        - Website is reachable (if test_fetch=True via HEAD request)
        - Website returns valid content-type (if test_fetch=True)

        Args:
            url: Website URL to validate
            config: Additional configuration (not used for websites)
            test_fetch: If True, perform HEAD request to verify accessibility
            timeout: Timeout in seconds for test request

        Returns:
            ValidationResult with:
            - valid: True if URL is valid for website fetching
            - errors: List of error messages
            - warnings: List of warning messages
            - response_time_ms: Response time in milliseconds (if test_fetch=True)
        """
        # Run base validation first
        result = super().validate(url, config, test_fetch, timeout)
        if not result.valid:
            return result

        # Check if URL should be handled by another fetcher
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            result.add_warning(
                "This URL appears to be a YouTube URL. "
                "Consider using the 'youtube' source type instead."
            )

        if any(x in url_lower for x in ['/feed', '/rss', '/atom', '.xml']):
            result.add_warning(
                "This URL appears to be an RSS/Atom feed. "
                "Consider using the 'rss' source type instead."
            )

        result.url_type = 'website'

        # If test_fetch is enabled, perform HEAD request
        if test_fetch:
            try:
                start_time = time.time()

                # Use HEAD request for quick validation (no body download)
                response = self.session.head(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                )

                elapsed_ms = (time.time() - start_time) * 1000
                result.response_time_ms = round(elapsed_ms, 2)

                # Check response status
                if response.status_code >= 400:
                    if response.status_code == 401:
                        result.add_error(
                            "Website requires authentication (HTTP 401). "
                            "Authentication is not currently supported."
                        )
                    elif response.status_code == 403:
                        result.add_error(
                            "Access to website is forbidden (HTTP 403). "
                            "The site may block automated access."
                        )
                    elif response.status_code == 404:
                        result.add_error(
                            "Page not found (HTTP 404). "
                            "Please verify the URL is correct."
                        )
                    elif response.status_code >= 500:
                        result.add_warning(
                            f"Server error (HTTP {response.status_code}). "
                            "The site may be temporarily unavailable."
                        )
                    else:
                        result.add_error(
                            f"Website returned error status (HTTP {response.status_code})"
                        )
                    return result

                # Check content-type if available
                content_type = response.headers.get('Content-Type', '').lower()
                if content_type:
                    if 'text/html' not in content_type and 'text/plain' not in content_type:
                        if 'application/json' in content_type:
                            result.add_warning(
                                "URL returns JSON content. "
                                "Website fetcher works best with HTML pages."
                            )
                        elif 'application/xml' in content_type or 'text/xml' in content_type:
                            result.add_warning(
                                "URL returns XML content. "
                                "This might be an RSS feed - consider using 'rss' type."
                            )
                        elif 'application/pdf' in content_type:
                            result.add_error(
                                "URL returns PDF content. "
                                "PDF files are not currently supported."
                            )
                        elif content_type.startswith('image/'):
                            result.add_error(
                                "URL returns image content. "
                                "Images cannot be processed as website content."
                            )
                        else:
                            result.add_warning(
                                f"Unexpected content type: {content_type}. "
                                "Website extraction may not work correctly."
                            )

                # Check for redirects
                if response.history:
                    final_url = response.url
                    result.add_warning(
                        f"URL redirected to: {final_url}"
                    )

                # Mark as successfully validated
                result.test_item_count = 1

            except requests.Timeout:
                result.add_error(
                    f"Request timed out after {timeout} seconds. "
                    "Website may be slow or unreachable."
                )
            except requests.ConnectionError:
                result.add_error(
                    "Could not connect to website. "
                    "Please check the URL and network connectivity."
                )
            except requests.RequestException as e:
                result.add_error(f"Failed to validate website: {str(e)}")

        return result
