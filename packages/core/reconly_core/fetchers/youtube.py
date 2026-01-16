"""YouTube transcript fetcher module.

Supports both individual video URLs and channel URLs. When given a channel URL,
fetches transcripts for recent videos from the channel's RSS feed.
"""
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from reconly_core.fetchers.base import BaseFetcher, ValidationResult
from reconly_core.fetchers.registry import register_fetcher

logger = logging.getLogger(__name__)


# YouTube channel RSS feed URL template
YOUTUBE_CHANNEL_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


@register_fetcher('youtube')
class YouTubeFetcher(BaseFetcher):
    """Fetches transcripts from YouTube videos and channels."""

    def __init__(self):
        pass

    @staticmethod
    def is_channel_url(url: str) -> bool:
        """
        Detect whether a YouTube URL points to a channel.

        Args:
            url: YouTube URL to check

        Returns:
            True if URL is a channel URL, False otherwise
        """
        channel_patterns = [
            r'youtube\.com/channel/UC[a-zA-Z0-9_-]+',  # /channel/UCxxxxx
            r'youtube\.com/@[a-zA-Z0-9_.-]+',          # /@username (handle)
            r'youtube\.com/c/[a-zA-Z0-9_.-]+',         # /c/customname (legacy)
            r'youtube\.com/user/[a-zA-Z0-9_.-]+',      # /user/username (legacy)
        ]

        for pattern in channel_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if not found
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def extract_channel_id(url: str) -> Optional[str]:
        """
        Extract channel ID from various YouTube channel URL formats.

        For /channel/UCxxx URLs, extracts ID directly.
        For /@username, /c/, /user/ URLs, fetches page to resolve channel ID.

        Args:
            url: YouTube channel URL

        Returns:
            Channel ID (UCxxxxx format) or None if not found
        """
        # Direct channel ID from /channel/ URL
        match = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]+)', url, re.IGNORECASE)
        if match:
            return match.group(1)

        # For handle (@), custom (/c/), and user (/user/) URLs, we need to fetch the page
        if re.search(r'youtube\.com/(@|c/|user/)', url, re.IGNORECASE):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Look for channel ID in page content
                # YouTube embeds it in various meta tags and data
                patterns = [
                    r'"channelId":"(UC[a-zA-Z0-9_-]+)"',
                    r'channel_id=([^"&]+)',
                    r'"externalId":"(UC[a-zA-Z0-9_-]+)"',
                ]

                for pattern in patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        return match.group(1)

            except Exception as e:
                logger.warning(f"Failed to resolve channel ID from URL {url}: {e}")

        return None

    def _fetch_channel_rss(
        self,
        channel_id: str,
        since: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch video list from a YouTube channel's RSS feed.

        Args:
            channel_id: YouTube channel ID (UCxxxxx format)
            since: Only return videos published after this datetime

        Returns:
            List of video metadata dicts with url, title, video_id, published, channel_title
        """
        rss_url = YOUTUBE_CHANNEL_RSS_URL.format(channel_id=channel_id)

        try:
            feed = feedparser.parse(rss_url)

            if feed.bozo and not feed.entries:
                raise Exception(f"Failed to parse YouTube channel RSS: {feed.bozo_exception}")

            videos = []
            channel_title = feed.feed.get('title', 'Unknown Channel')

            for entry in feed.entries:
                # Extract video ID from link
                video_url = entry.get('link', '')
                video_id = self.extract_video_id(video_url)

                if not video_id:
                    continue

                # Parse publication date
                published_dt = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published_dt = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass

                # Skip if video is older than 'since' parameter
                if since and published_dt and published_dt <= since:
                    continue

                videos.append({
                    'url': video_url,
                    'video_id': video_id,
                    'title': entry.get('title', f'Video {video_id}'),
                    'published': published_dt.isoformat() if published_dt else None,
                    'channel_id': channel_id,
                    'channel_title': channel_title,
                })

            return videos

        except Exception as e:
            raise Exception(f"Failed to fetch YouTube channel RSS: {str(e)}")

    def _fetch_video_title(self, video_id: str) -> Optional[str]:
        """
        Fetch video title using YouTube's oEmbed API.

        Args:
            video_id: YouTube video ID

        Returns:
            Video title or None if fetch fails
        """
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('title')
        except Exception as e:
            logger.warning(f"Failed to fetch video title for {video_id}: {e}")
            return None

    def _fetch_video_transcript(
        self,
        video_id: str,
        languages: List[str]
    ) -> Optional[Dict]:
        """
        Fetch transcript for a single video.

        Args:
            video_id: YouTube video ID
            languages: Preferred language codes

        Returns:
            Dict with content and language, or None if transcript unavailable
        """
        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, languages=tuple(languages))
            content = '\n'.join([snippet.text for snippet in transcript.snippets])

            return {
                'content': content,
                'language': transcript.language
            }
        except Exception as e:
            logger.warning(f"Failed to fetch transcript for video {video_id}: {e}")
            return None

    def _fetch_channel(
        self,
        url: str,
        since: Optional[datetime] = None,
        languages: Optional[List[str]] = None,
        max_items: int = 5
    ) -> List[Dict]:
        """
        Fetch transcripts for recent videos from a YouTube channel.

        Args:
            url: YouTube channel URL
            since: Only fetch videos published after this datetime
            languages: Preferred language codes
            max_items: Maximum number of videos to fetch per run (default: 5)

        Returns:
            List of video transcript dicts
        """
        if languages is None:
            languages = ['de', 'en']

        # Extract channel ID
        channel_id = self.extract_channel_id(url)
        if not channel_id:
            raise ValueError(f"Could not extract channel ID from URL: {url}")

        # Fetch video list from RSS
        videos = self._fetch_channel_rss(channel_id, since=since)

        if not videos:
            return []

        # Limit number of videos to process per run
        if len(videos) > max_items:
            logger.info(f"Limiting channel fetch from {len(videos)} to {max_items} videos")
            videos = videos[:max_items]

        results = []
        for video in videos:
            # Fetch transcript
            transcript_data = self._fetch_video_transcript(video['video_id'], languages)

            if transcript_data is None:
                # Skip videos without transcripts
                logger.info(f"Skipping video {video['video_id']} - no transcript available")
                continue

            results.append({
                'url': video['url'],
                'video_id': video['video_id'],
                'title': video['title'],
                'content': transcript_data['content'],
                'source_type': 'youtube',
                'language': transcript_data['language'],
                'published': video['published'],
                'channel_id': video['channel_id'],
                'channel_title': video['channel_title'],
                'image_url': f"https://img.youtube.com/vi/{video['video_id']}/maxresdefault.jpg",
            })

        return results

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        languages: Optional[List[str]] = None,
        max_items: int = 5
    ) -> List[Dict]:
        """
        Fetch transcript(s) from a YouTube video or channel.

        For video URLs: Returns list with single transcript dict.
        For channel URLs: Returns list of transcript dicts for recent videos.

        Args:
            url: YouTube video or channel URL
            since: For channels, only fetch videos after this datetime
            languages: List of preferred language codes (default: ['de', 'en'])
            max_items: For channels, max videos to fetch per run (default: 5)

        Returns:
            List of dictionaries, each containing:
            - url: Video URL
            - video_id: YouTube video ID
            - title: Video title
            - content: Transcript text
            - source_type: 'youtube'
            - language: Transcript language
            - published: Publication datetime (ISO format, channels only)
            - channel_id: Channel ID (channels only)
            - channel_title: Channel name (channels only)
        """
        if languages is None:
            languages = ['de', 'en']

        # Check if this is a channel URL
        if self.is_channel_url(url):
            return self._fetch_channel(url, since=since, languages=languages, max_items=max_items)

        # Single video - extract video ID
        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        try:
            # Initialize API instance
            api = YouTubeTranscriptApi()

            # Fetch transcript with language preferences
            transcript = api.fetch(video_id, languages=tuple(languages))

            # Extract text from transcript snippets
            content = '\n'.join([snippet.text for snippet in transcript.snippets])

            # Fetch actual video title via oEmbed API
            title = self._fetch_video_title(video_id) or f"YouTube Video {video_id}"

            # Return as list for consistent interface
            return [{
                'url': url,
                'video_id': video_id,
                'title': title,
                'content': content,
                'source_type': 'youtube',
                'language': transcript.language,
                'image_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            }]

        except Exception as e:
            raise Exception(f"Failed to fetch YouTube transcript: {str(e)}")

    def get_source_type(self) -> str:
        """Get the source type identifier."""
        return 'youtube'

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the given URL."""
        return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()

    def get_description(self) -> str:
        """Get a human-readable description of this fetcher."""
        return 'YouTube video and channel transcript fetcher'

    def validate(
        self,
        url: str,
        config: Optional[Dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate YouTube URL and optionally test video/channel accessibility.

        Validates:
        - URL is a valid YouTube URL (youtube.com or youtu.be)
        - URL matches expected video, channel, or playlist patterns
        - Video/channel is accessible (if test_fetch=True)
        - Transcript is available (if test_fetch=True and URL is a video)

        Args:
            url: YouTube URL to validate
            config: Additional configuration (e.g., language preferences)
            test_fetch: If True, verify video/channel accessibility
            timeout: Timeout in seconds for test fetch

        Returns:
            ValidationResult with:
            - valid: True if URL is a valid YouTube URL
            - errors: List of error messages
            - warnings: List of warning messages
            - url_type: 'video', 'channel', or 'playlist'
            - test_item_count: Number of videos found (for channels, if test_fetch=True)
        """
        # Run base validation first
        result = super().validate(url, config, test_fetch, timeout)
        if not result.valid:
            return result

        # Check if URL is a YouTube URL
        if not self.can_handle(url):
            result.add_error(
                "URL is not a valid YouTube URL. "
                "Expected youtube.com or youtu.be domain."
            )
            return result

        # Detect URL type
        url_type = self._detect_url_type(url)
        result.url_type = url_type

        if url_type == 'video':
            video_id = self.extract_video_id(url)
            if not video_id:
                result.add_error(
                    "Could not extract video ID from URL. "
                    "Please check the URL format."
                )
                return result

            # Test fetch for video
            if test_fetch:
                result = self._validate_video(url, video_id, config, timeout, result)

        elif url_type == 'channel':
            # Warn that channel ID extraction may require network call
            result.add_warning(
                "Channel URL detected. Channel ID extraction may require "
                "additional network requests for @username or /c/ URLs."
            )

            if test_fetch:
                result = self._validate_channel(url, config, timeout, result)

        elif url_type == 'playlist':
            result.add_warning(
                "Playlist URL detected. Playlist support is limited."
            )

        else:
            result.add_error(
                "Could not determine YouTube URL type. "
                "Expected video, channel, or playlist URL."
            )

        return result

    def _detect_url_type(self, url: str) -> Optional[str]:
        """
        Detect the type of YouTube URL.

        Args:
            url: YouTube URL to check

        Returns:
            'video', 'channel', 'playlist', or None if unknown
        """
        # Check for video URL first
        if self.extract_video_id(url):
            return 'video'

        # Check for channel URL
        if self.is_channel_url(url):
            return 'channel'

        # Check for playlist URL
        if 'playlist?list=' in url or '/playlist/' in url:
            return 'playlist'

        return None

    def _validate_video(
        self,
        url: str,
        video_id: str,
        config: Optional[Dict[str, Any]],
        timeout: int,
        result: ValidationResult,
    ) -> ValidationResult:
        """
        Validate a video URL by checking if transcript is available.

        Args:
            url: Original video URL
            video_id: Extracted video ID
            config: Configuration with language preferences
            timeout: Request timeout
            result: ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        try:
            start_time = time.time()

            # First check if video exists via oEmbed
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=timeout)

            elapsed_ms = (time.time() - start_time) * 1000
            result.response_time_ms = round(elapsed_ms, 2)

            if response.status_code == 404:
                result.add_error(
                    f"Video not found (ID: {video_id}). "
                    "The video may be private, deleted, or the URL is incorrect."
                )
                return result
            elif response.status_code != 200:
                result.add_warning(
                    f"Could not verify video existence (HTTP {response.status_code})"
                )

            # Try to get transcript availability
            try:
                languages = config.get('languages', ['de', 'en']) if config else ['de', 'en']
                api = YouTubeTranscriptApi()
                transcript_list = api.list(video_id)

                # Check if any requested language is available
                available_languages = [t.language_code for t in transcript_list]
                matching_langs = [lang for lang in languages if lang in available_languages]

                if not matching_langs:
                    result.add_warning(
                        f"No transcript in requested languages ({', '.join(languages)}). "
                        f"Available: {', '.join(available_languages[:5])}"
                        + ("..." if len(available_languages) > 5 else "")
                    )
                else:
                    result.test_item_count = 1  # One video validated

            except Exception as e:
                # Transcript check failed - this is a warning, not error
                # Video may still be processable
                error_msg = str(e)
                if 'disabled' in error_msg.lower():
                    result.add_warning(
                        "Transcripts are disabled for this video."
                    )
                elif 'no transcript' in error_msg.lower():
                    result.add_warning(
                        "No transcripts available for this video."
                    )
                else:
                    result.add_warning(
                        f"Could not verify transcript availability: {error_msg}"
                    )

        except requests.Timeout:
            result.add_error(
                f"Request timed out after {timeout} seconds. "
                "YouTube may be slow or unreachable."
            )
        except requests.RequestException as e:
            result.add_error(f"Failed to validate video: {str(e)}")

        return result

    def _validate_channel(
        self,
        url: str,
        config: Optional[Dict[str, Any]],
        timeout: int,
        result: ValidationResult,
    ) -> ValidationResult:
        """
        Validate a channel URL by checking if channel exists and has videos.

        Args:
            url: Original channel URL
            config: Configuration (not used)
            timeout: Request timeout
            result: ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        try:
            start_time = time.time()

            # Try to extract channel ID
            channel_id = self.extract_channel_id(url)

            elapsed_ms = (time.time() - start_time) * 1000
            result.response_time_ms = round(elapsed_ms, 2)

            if not channel_id:
                result.add_error(
                    "Could not extract channel ID from URL. "
                    "The channel may not exist or the URL format is not supported."
                )
                return result

            # Try to fetch channel RSS feed
            rss_url = YOUTUBE_CHANNEL_RSS_URL.format(channel_id=channel_id)
            feed = feedparser.parse(rss_url)

            if feed.bozo and not feed.entries:
                result.add_warning(
                    "Could not fetch channel feed. "
                    "Channel may be empty or have restricted access."
                )
            elif feed.entries:
                result.test_item_count = len(feed.entries)
                if len(feed.entries) == 0:
                    result.add_warning(
                        "Channel exists but has no public videos."
                    )

        except Exception as e:
            result.add_error(f"Failed to validate channel: {str(e)}")

        return result
