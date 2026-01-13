"""YouTube transcript fetcher module.

Supports both individual video URLs and channel URLs. When given a channel URL,
fetches transcripts for recent videos from the channel's RSS feed.
"""
from youtube_transcript_api import YouTubeTranscriptApi
from typing import Dict, List, Optional
from datetime import datetime
import re
import logging
import feedparser
import requests

from reconly_core.fetchers.base import BaseFetcher
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
