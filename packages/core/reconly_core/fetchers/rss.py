"""RSS feed fetcher module."""
import os
import time
import feedparser
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser

from reconly_core.fetchers.base import BaseFetcher, ValidationResult
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

    def validate(
        self,
        url: str,
        config: Optional[Dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate RSS feed URL and optionally test feed accessibility.

        Validates:
        - Basic URL format (via base class)
        - URL appears to be an RSS/Atom feed
        - Feed is parseable (if test_fetch=True)
        - Feed contains valid entries (if test_fetch=True)

        Args:
            url: RSS feed URL to validate
            config: Additional configuration (not used for RSS)
            test_fetch: If True, attempt to parse the feed
            timeout: Timeout in seconds for test fetch

        Returns:
            ValidationResult with:
            - valid: True if feed URL is valid
            - errors: List of error messages
            - warnings: List of warning messages (e.g., feed format issues)
            - test_item_count: Number of entries found (if test_fetch=True)
            - response_time_ms: Parse time in milliseconds (if test_fetch=True)
            - url_type: 'rss' or 'atom' (if test_fetch=True and detected)
        """
        # Run base validation first
        result = super().validate(url, config, test_fetch, timeout)
        if not result.valid:
            return result

        # Check if URL looks like an RSS feed
        if not self.is_rss_url(url):
            result.add_warning(
                "URL doesn't appear to be an RSS/Atom feed "
                "(missing /feed, /rss, .xml, etc.). "
                "Feed may still work if it returns valid RSS/Atom content."
            )

        # If test_fetch is enabled, try to parse the feed
        if test_fetch:
            try:
                start_time = time.time()

                # feedparser doesn't have native timeout, but we can set request_headers
                # Use a simple timeout by setting agent timeout
                feed = feedparser.parse(
                    url,
                    request_headers={'User-Agent': 'Reconly/1.0'},
                )

                elapsed_ms = (time.time() - start_time) * 1000
                result.response_time_ms = round(elapsed_ms, 2)

                # Check for parse errors
                if feed.bozo:
                    # bozo_exception indicates parsing issues
                    exception_msg = str(feed.bozo_exception) if feed.bozo_exception else "Unknown error"

                    # Some bozo exceptions are warnings (still parseable)
                    if feed.entries:
                        result.add_warning(
                            f"Feed parsed with warnings: {exception_msg}"
                        )
                    else:
                        result.add_error(
                            f"Failed to parse RSS feed: {exception_msg}"
                        )
                        return result

                # Check for entries
                if not feed.entries:
                    result.add_warning(
                        "Feed contains no entries. "
                        "This may be normal for a new feed."
                    )
                else:
                    result.test_item_count = len(feed.entries)

                # Detect feed type
                feed_type = feed.version if hasattr(feed, 'version') else None
                if feed_type:
                    if 'atom' in feed_type.lower():
                        result.url_type = 'atom'
                    elif 'rss' in feed_type.lower():
                        result.url_type = 'rss'
                    else:
                        result.url_type = feed_type

                    # Warn about deprecated versions
                    deprecated_versions = ['rss090', 'rss091', 'rss10']
                    if any(v in feed_type.lower() for v in deprecated_versions):
                        result.add_warning(
                            f"Feed uses deprecated format ({feed_type}). "
                            "Consider using RSS 2.0 or Atom 1.0."
                        )

            except Exception as e:
                result.add_error(f"Failed to fetch RSS feed: {str(e)}")

        return result
