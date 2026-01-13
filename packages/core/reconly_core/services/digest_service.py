"""Core business logic for digest processing."""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from reconly_core.fetchers.website import WebsiteFetcher
from reconly_core.fetchers.youtube import YouTubeFetcher
from reconly_core.fetchers.rss import RSSFetcher
from reconly_core.summarizers import get_summarizer
from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.tracking import FeedTracker
from reconly_core.database import DigestDB

logger = logging.getLogger(__name__)


@dataclass
class ProcessOptions:
    """Options for processing a URL."""
    language: str = 'de'
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    enable_fallback: bool = True
    save: bool = False
    tags: Optional[List[str]] = None
    reset_tracking: bool = False
    user_id: Optional[int] = None  # Associate digest with user
    auto_embed: bool = False  # Automatically embed digest for RAG after save


@dataclass
class DigestResult:
    """Result of processing a URL."""
    success: bool
    url: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    digest_id: Optional[int] = None


class DigestService:
    """Service for processing individual digests."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize digest service.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.db: Optional[DigestDB] = None
        self.tracker = FeedTracker()

    def _get_db(self) -> DigestDB:
        """Get or create database instance."""
        if self.db is None:
            self.db = DigestDB(database_url=self.database_url)
        return self.db

    def _detect_source_type(self, url: str) -> str:
        """
        Detect source type from URL.

        Args:
            url: URL to check

        Returns:
            Source type: 'youtube', 'rss', or 'website'
        """
        if 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'
        elif RSSFetcher.is_rss_url(url):
            return 'rss'
        else:
            return 'website'

    def _get_summarizer(self, options: ProcessOptions) -> BaseSummarizer:
        """
        Get summarizer instance based on options.

        Args:
            options: Process options

        Returns:
            Summarizer instance
        """
        return get_summarizer(
            provider=options.provider,
            api_key=options.api_key,
            model=options.model,
            enable_fallback=options.enable_fallback
        )

    def _save_to_database(
        self,
        result_data: Dict[str, Any],
        tags: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        auto_embed: bool = False,
    ) -> Optional[int]:
        """
        Save digest to database.

        Args:
            result_data: Result dictionary from summarizer
            tags: Tags to associate with digest
            user_id: User ID to associate with digest (optional)
            auto_embed: If True, trigger embedding for RAG after save

        Returns:
            Digest ID if saved, None otherwise
        """
        try:
            db = self._get_db()

            # Parse published_at if it exists
            published_at = None
            if 'published' in result_data and result_data['published']:
                try:
                    published_at = datetime.fromisoformat(result_data['published'])
                except Exception:
                    pass

            # Get provider info
            model_info = result_data.get('model_info', {})
            provider = model_info.get('provider', 'unknown')
            if 'model_key' in model_info:
                provider = f"{provider}-{model_info['model_key']}"

            # Prepare digest data
            digest_data = {
                'url': result_data['url'],
                'title': result_data['title'],
                'content': result_data.get('content', ''),
                'summary': result_data['summary'],
                'source_type': result_data['source_type'],
                'feed_url': result_data.get('feed_url'),
                'feed_title': result_data.get('feed_title'),
                'author': result_data.get('author'),
                'published_at': published_at,
                'provider': provider,
                'language': result_data.get('summary_language', 'de'),
                'estimated_cost': result_data.get('estimated_cost', 0.0),
                'user_id': user_id  # Add user association
            }

            # Save to database (optionally with auto-embedding)
            digest = db.save_digest(digest_data, tags=tags, auto_embed=auto_embed)
            return digest.id

        except Exception as e:
            # Log error but don't fail the entire operation
            logger.warning(f"Failed to save digest to database: {e}", exc_info=True)
            return None

    def process_url(self, url: str, options: ProcessOptions) -> DigestResult:
        """
        Process a single URL.

        Args:
            url: URL to process
            options: Processing options

        Returns:
            DigestResult with processing outcome
        """
        try:
            # Detect source type
            source_type = self._detect_source_type(url)

            # Get summarizer
            summarizer = self._get_summarizer(options)

            # Process based on source type
            if source_type == 'rss':
                return self._process_rss_feed(url, summarizer, options)
            elif source_type == 'youtube':
                return self._process_youtube(url, summarizer, options)
            else:
                return self._process_website(url, summarizer, options)

        except Exception as e:
            return DigestResult(
                success=False,
                url=url,
                error=str(e)
            )

    def _process_website(
        self,
        url: str,
        summarizer: BaseSummarizer,
        options: ProcessOptions
    ) -> DigestResult:
        """Process a website URL."""
        try:
            # Fetch content
            fetcher = WebsiteFetcher()
            content_data = fetcher.fetch(url)

            # Summarize
            result = summarizer.summarize(content_data, language=options.language)

            # Save if requested
            digest_id = None
            if options.save:
                digest_id = self._save_to_database(
                    result,
                    tags=options.tags,
                    user_id=options.user_id,
                    auto_embed=options.auto_embed,
                )

            return DigestResult(
                success=True,
                url=url,
                data=result,
                digest_id=digest_id
            )

        except Exception as e:
            return DigestResult(
                success=False,
                url=url,
                error=str(e)
            )

    def _process_youtube(
        self,
        url: str,
        summarizer: BaseSummarizer,
        options: ProcessOptions
    ) -> DigestResult:
        """Process a YouTube video or channel URL.

        For single videos: Returns single digest result.
        For channels: Returns result with multiple video digests.
        """
        try:
            fetcher = YouTubeFetcher()

            # Check if this is a channel URL
            is_channel = fetcher.is_channel_url(url)

            # Reset tracking if requested (for channels)
            if is_channel and options.reset_tracking:
                self.tracker.reset_feed(url)

            # Get last read timestamp for channels
            last_read = self.tracker.get_last_read(url) if is_channel else None

            # Fetch transcripts (returns list for both videos and channels)
            content_items = fetcher.fetch(url, since=last_read)

            if not content_items:
                if is_channel:
                    return DigestResult(
                        success=True,
                        url=url,
                        data={'videos': [], 'message': 'No new videos'}
                    )
                else:
                    return DigestResult(
                        success=False,
                        url=url,
                        error='No transcript available'
                    )

            # For single video, return simple result
            if not is_channel:
                content_data = content_items[0]
                result = summarizer.summarize(content_data, language=options.language)

                digest_id = None
                if options.save:
                    digest_id = self._save_to_database(
                    result,
                    tags=options.tags,
                    user_id=options.user_id,
                    auto_embed=options.auto_embed,
                )

                return DigestResult(
                    success=True,
                    url=url,
                    data=result,
                    digest_id=digest_id
                )

            # For channels, process each video like RSS
            results = []
            latest_timestamp = last_read

            for content_data in content_items:
                try:
                    result = summarizer.summarize(content_data, language=options.language)
                    results.append(result)

                    if options.save:
                        digest_id = self._save_to_database(
                    result,
                    tags=options.tags,
                    user_id=options.user_id,
                    auto_embed=options.auto_embed,
                )
                        result['digest_id'] = digest_id

                    # Track latest timestamp
                    if content_data.get('published'):
                        video_dt = datetime.fromisoformat(content_data['published'])
                        if latest_timestamp is None or video_dt > latest_timestamp:
                            latest_timestamp = video_dt

                except Exception as e:
                    results.append({
                        'url': content_data.get('url', ''),
                        'title': content_data.get('title', 'Unknown'),
                        'error': str(e),
                        'success': False
                    })

            # Update tracking with latest timestamp
            if latest_timestamp:
                self.tracker.update_last_read(url, latest_timestamp)

            return DigestResult(
                success=True,
                url=url,
                data={
                    'videos': results,
                    'count': len(results),
                    'last_read': last_read,
                    'new_last_read': latest_timestamp
                }
            )

        except Exception as e:
            return DigestResult(
                success=False,
                url=url,
                error=str(e)
            )

    def _process_rss_feed(
        self,
        url: str,
        summarizer: BaseSummarizer,
        options: ProcessOptions
    ) -> DigestResult:
        """
        Process an RSS feed.

        Note: Returns a result with multiple articles in data['articles'].
        """
        try:
            # Reset tracking if requested
            if options.reset_tracking:
                self.tracker.reset_feed(url)

            # Get last read timestamp
            last_read = self.tracker.get_last_read(url)

            # Fetch articles
            fetcher = RSSFetcher()
            articles = fetcher.fetch(url, since=last_read)

            if not articles:
                return DigestResult(
                    success=True,
                    url=url,
                    data={'articles': [], 'message': 'No new articles'}
                )

            # Process each article
            results = []
            latest_timestamp = last_read

            for article in articles:
                try:
                    # Summarize article
                    result = summarizer.summarize(article, language=options.language)
                    results.append(result)

                    # Save if requested
                    if options.save:
                        digest_id = self._save_to_database(
                    result,
                    tags=options.tags,
                    user_id=options.user_id,
                    auto_embed=options.auto_embed,
                )
                        result['digest_id'] = digest_id

                    # Track latest timestamp
                    if article['published']:
                        article_dt = datetime.fromisoformat(article['published'])
                        if latest_timestamp is None or article_dt > latest_timestamp:
                            latest_timestamp = article_dt

                except Exception as e:
                    results.append({
                        'url': article.get('url', ''),
                        'title': article.get('title', 'Unknown'),
                        'error': str(e),
                        'success': False
                    })

            # Update tracking with latest timestamp
            if latest_timestamp:
                self.tracker.update_last_read(url, latest_timestamp)

            return DigestResult(
                success=True,
                url=url,
                data={
                    'articles': results,
                    'count': len(results),
                    'last_read': last_read,
                    'new_last_read': latest_timestamp
                }
            )

        except Exception as e:
            return DigestResult(
                success=False,
                url=url,
                error=str(e)
            )

    def get_by_id(self, digest_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get a digest by ID.

        Args:
            digest_id: Digest ID
            user_id: User ID for filtering (optional)

        Returns:
            Digest dictionary or None if not found
        """
        db = self._get_db()
        digest = db.get_digest_by_id(digest_id, user_id=user_id)

        if digest:
            return digest.to_dict()
        return None

    def search_digests(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 10,
        user_id: Optional[int] = None
    ) -> List[Any]:
        """
        Search for digests in database.

        Args:
            query: Search query (full-text search)
            tags: Filter by tags
            source_type: Filter by source type
            limit: Maximum results
            user_id: User ID for filtering (optional)

        Returns:
            List of digest objects
        """
        db = self._get_db()
        return db.search_digests(
            query=query,
            tags=tags,
            source_type=source_type,
            limit=limit,
            user_id=user_id
        )

    def get_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get database statistics.

        Args:
            user_id: User ID for filtering (optional)

        Returns:
            Statistics dictionary
        """
        db = self._get_db()
        return db.get_statistics(user_id=user_id)

    def export_digests(
        self,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Export digests to dictionary format.

        Args:
            tags: Filter by tags
            source_type: Filter by source type
            limit: Maximum results

        Returns:
            List of digest dictionaries
        """
        db = self._get_db()
        results = db.search_digests(tags=tags, source_type=source_type, limit=limit)
        return db.export_to_dict(results)
