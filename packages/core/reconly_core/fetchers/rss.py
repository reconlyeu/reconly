"""RSS feed fetcher module."""
import os
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dateutil import parser as date_parser

from reconly_core.fetchers.base import BaseFetcher
from reconly_core.fetchers.registry import register_fetcher


# Default age limit for first run (when no tracking data exists)
# Prevents fetching hundreds of old articles on first feed run
DEFAULT_FIRST_RUN_MAX_AGE_DAYS = 3


def get_first_run_max_age_days() -> int:
    """Get the max age in days for first run from env or default."""
    env_value = os.environ.get('RSS_FIRST_RUN_MAX_AGE_DAYS')
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass
    return DEFAULT_FIRST_RUN_MAX_AGE_DAYS


@register_fetcher('rss')
class RSSFetcher(BaseFetcher):
    """Fetches and parses RSS/Atom feeds."""

    def __init__(self):
        pass

    def fetch(
        self,
        feed_url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Fetch articles from an RSS/Atom feed.

        Args:
            feed_url: URL of the RSS/Atom feed
            since: Only return articles published after this datetime (optional).
                   If None (first run), defaults to RSS_FIRST_RUN_MAX_AGE_DAYS ago.
            max_items: Maximum number of articles to return (optional).
                       Applied after date filtering, newest first.

        Returns:
            List of article dictionaries, each containing:
            - url: Article URL
            - title: Article title
            - content: Article description/content
            - published: Publication datetime (ISO format string)
            - author: Author name (if available)
            - source_type: 'rss'
            - feed_url: Original feed URL
        """
        try:
            # Apply default age limit for first run (when since=None)
            if since is None:
                max_age_days = get_first_run_max_age_days()
                if max_age_days > 0:
                    since = datetime.now() - timedelta(days=max_age_days)
                # If max_age_days is 0, since remains None (fetch all)

            # Parse the feed
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                raise Exception(f"Failed to parse RSS feed: {feed.bozo_exception}")

            articles = []

            for entry in feed.entries:
                # Extract publication date
                published_dt = self._extract_date(entry)

                # Skip if article is older than 'since' parameter
                if since and published_dt and published_dt <= since:
                    continue

                # Extract content (try multiple fields)
                content = self._extract_content(entry)

                # Extract article URL
                article_url = entry.get('link', feed_url)

                # Extract author
                author = self._extract_author(entry)

                # Build article dictionary
                article = {
                    'url': article_url,
                    'title': entry.get('title', 'No title'),
                    'content': content,
                    'published': published_dt.isoformat() if published_dt else None,
                    'author': author,
                    'source_type': 'rss',
                    'feed_url': feed_url,
                    'feed_title': feed.feed.get('title', 'Unknown Feed')
                }

                articles.append(article)

            # Sort by published date (newest first) and apply max_items limit
            articles.sort(
                key=lambda a: a.get('published') or '',
                reverse=True
            )

            if max_items and len(articles) > max_items:
                articles = articles[:max_items]

            return articles

        except Exception as e:
            raise Exception(f"Failed to fetch RSS feed: {str(e)}")

    def _extract_date(self, entry) -> Optional[datetime]:
        """Extract and parse publication date from entry."""
        # Try different date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except:
                        pass

        # Try string fields as fallback
        string_fields = ['published', 'updated', 'created']
        for field in string_fields:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                if date_str:
                    try:
                        return date_parser.parse(date_str)
                    except:
                        pass

        return None

    def _extract_content(self, entry) -> str:
        """Extract content from entry, trying multiple fields."""
        # Try content field (Atom)
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].value

        # Try summary field (RSS)
        if hasattr(entry, 'summary') and entry.summary:
            return entry.summary

        # Try description field
        if hasattr(entry, 'description') and entry.description:
            return entry.description

        # Fallback to title if no content available
        return entry.get('title', 'No content available')

    def _extract_author(self, entry) -> Optional[str]:
        """Extract author from entry."""
        # Try author field
        if hasattr(entry, 'author') and entry.author:
            return entry.author

        # Try author_detail
        if hasattr(entry, 'author_detail') and entry.author_detail:
            return entry.author_detail.get('name')

        # Try dc:creator (Dublin Core)
        if hasattr(entry, 'dc_creator') and entry.dc_creator:
            return entry.dc_creator

        return None

    def get_source_type(self) -> str:
        """Get the source type identifier."""
        return 'rss'

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the given URL."""
        return self.is_rss_url(url)

    def get_description(self) -> str:
        """Get a human-readable description of this fetcher."""
        return 'RSS/Atom feed fetcher'

    @staticmethod
    def is_rss_url(url: str) -> bool:
        """
        Check if URL is likely an RSS/Atom feed.

        Args:
            url: URL to check

        Returns:
            True if URL appears to be an RSS/Atom feed
        """
        rss_indicators = [
            '/feed', '/rss', '/atom', '.xml',
            'feed.xml', 'rss.xml', 'atom.xml'
        ]

        url_lower = url.lower()
        return any(indicator in url_lower for indicator in rss_indicators)
