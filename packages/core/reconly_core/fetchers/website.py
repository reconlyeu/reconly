"""Website content fetcher module."""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from datetime import datetime

from reconly_core.fetchers.base import BaseFetcher
from reconly_core.fetchers.registry import register_fetcher


@register_fetcher('website')
class WebsiteFetcher(BaseFetcher):
    """Fetches and extracts content from websites."""

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
            content = ""
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_='content') or
                soup.find('div', id='content') or
                soup.find('body')
            )

            if main_content:
                # Get text and clean it up
                content = main_content.get_text(separator='\n', strip=True)
                # Remove excessive newlines
                content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())

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
