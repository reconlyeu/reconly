"""Tests for YouTube transcript fetching."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from reconly_core.fetchers.youtube import YouTubeFetcher


class TestYouTubeFetcher:
    """Test suite for YouTubeFetcher class."""

    @pytest.fixture
    def youtube_fetcher(self):
        """Create YouTubeFetcher instance for testing."""
        return YouTubeFetcher()

    # ===========================================
    # Video ID Extraction Tests
    # ===========================================

    @pytest.mark.parametrize("url,expected_id", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
    ])
    def test_extract_video_id_success(self, youtube_fetcher, url, expected_id):
        """WHEN various valid YouTube URL formats are provided
        THEN video ID is correctly extracted."""
        video_id = youtube_fetcher.extract_video_id(url)
        assert video_id == expected_id

    @pytest.mark.parametrize("url", [
        "https://example.com/video",
        "https://vimeo.com/123456",
        "not_a_url",
        "",
    ])
    def test_extract_video_id_invalid(self, youtube_fetcher, url):
        """WHEN invalid URL is provided
        THEN None is returned."""
        video_id = youtube_fetcher.extract_video_id(url)
        assert video_id is None

    # ===========================================
    # Channel URL Detection Tests
    # ===========================================

    @pytest.mark.parametrize("url,expected", [
        # Channel URLs - should return True
        ("https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxxx", True),
        ("https://youtube.com/channel/UC12345-_abc", True),
        ("https://www.youtube.com/@channelhandle", True),
        ("https://youtube.com/@My-Channel.name", True),
        ("https://www.youtube.com/c/customchannelname", True),
        ("https://youtube.com/c/MyChannel", True),
        ("https://www.youtube.com/user/oldusername", True),
        ("https://youtube.com/user/LegacyUser", True),
        # Video URLs - should return False
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False),
        ("https://youtu.be/dQw4w9WgXcQ", False),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", False),
        ("https://youtube.com/v/abc123", False),
        # Non-YouTube URLs - should return False
        ("https://example.com/channel/UC123", False),
        ("https://vimeo.com/@username", False),
    ])
    def test_is_channel_url(self, youtube_fetcher, url, expected):
        """WHEN various YouTube URL formats are provided
        THEN channel URLs are correctly detected."""
        result = youtube_fetcher.is_channel_url(url)
        assert result == expected

    # ===========================================
    # Channel ID Extraction Tests
    # ===========================================

    def test_extract_channel_id_from_channel_url(self, youtube_fetcher):
        """WHEN /channel/UCxxxxx URL format is provided
        THEN channel ID is extracted directly without HTTP request."""
        url = "https://www.youtube.com/channel/UCddiUEpeqJcYeBxX1IVBKvQ"
        channel_id = youtube_fetcher.extract_channel_id(url)
        assert channel_id == "UCddiUEpeqJcYeBxX1IVBKvQ"

    def test_extract_channel_id_from_handle_url(self, youtube_fetcher):
        """WHEN /@handle URL format is provided
        THEN page is fetched to resolve channel ID."""
        url = "https://www.youtube.com/@mkbhd"

        mock_response = Mock()
        mock_response.text = '{"channelId":"UCBJycsmduvYEL83R_U4JriQ"}'
        mock_response.raise_for_status = Mock()

        with patch('reconly_core.fetchers.youtube.requests.get', return_value=mock_response):
            channel_id = youtube_fetcher.extract_channel_id(url)
            assert channel_id == "UCBJycsmduvYEL83R_U4JriQ"

    def test_extract_channel_id_from_custom_url(self, youtube_fetcher):
        """WHEN /c/customname URL format is provided
        THEN page is fetched to resolve channel ID."""
        url = "https://www.youtube.com/c/GoogleDevelopers"

        mock_response = Mock()
        mock_response.text = '"externalId":"UC_x5XG1OV2P6uZZ5FSM9Ttw"'
        mock_response.raise_for_status = Mock()

        with patch('reconly_core.fetchers.youtube.requests.get', return_value=mock_response):
            channel_id = youtube_fetcher.extract_channel_id(url)
            assert channel_id == "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    def test_extract_channel_id_returns_none_for_video_url(self, youtube_fetcher):
        """WHEN video URL is provided
        THEN None is returned."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        channel_id = youtube_fetcher.extract_channel_id(url)
        assert channel_id is None

    # ===========================================
    # Video Transcript Fetch Tests (Updated for List Return)
    # ===========================================

    def test_fetch_transcript_success(self, youtube_fetcher):
        """WHEN valid video URL with available transcript is provided
        THEN transcript is fetched and returned as single-element list."""
        mock_snippet1 = Mock()
        mock_snippet1.text = "Hello world"

        mock_snippet2 = Mock()
        mock_snippet2.text = "This is a test transcript"

        mock_transcript = Mock()
        mock_transcript.snippets = [mock_snippet1, mock_snippet2]
        mock_transcript.language = "en"

        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.return_value = mock_transcript
            mock_api_class.return_value = mock_api

            results = youtube_fetcher.fetch('https://www.youtube.com/watch?v=dQw4w9WgXcQ')

            # Verify returns list with single element
            assert isinstance(results, list)
            assert len(results) == 1

            result = results[0]
            assert result['url'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
            assert result['video_id'] == 'dQw4w9WgXcQ'
            assert result['title'] == 'YouTube Video dQw4w9WgXcQ'
            assert result['content'] == 'Hello world\nThis is a test transcript'
            assert result['source_type'] == 'youtube'
            assert result['language'] == 'en'

            mock_api.fetch.assert_called_once_with('dQw4w9WgXcQ', languages=('de', 'en'))

    def test_fetch_with_custom_languages(self, youtube_fetcher):
        """WHEN custom language preferences are provided
        THEN API is called with those languages."""
        mock_snippet = Mock()
        mock_snippet.text = "Bonjour"

        mock_transcript = Mock()
        mock_transcript.snippets = [mock_snippet]
        mock_transcript.language = "fr"

        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.return_value = mock_transcript
            mock_api_class.return_value = mock_api

            results = youtube_fetcher.fetch(
                'https://www.youtube.com/watch?v=test123',
                languages=['fr', 'es']
            )

            assert results[0]['language'] == 'fr'
            mock_api.fetch.assert_called_once_with('test123', languages=('fr', 'es'))

    def test_fetch_invalid_url(self, youtube_fetcher):
        """WHEN URL does not contain valid video ID
        THEN ValueError is raised."""
        with pytest.raises(ValueError) as exc_info:
            youtube_fetcher.fetch('https://example.com/not-youtube')

        assert "Could not extract video ID from URL" in str(exc_info.value)

    def test_fetch_transcript_not_available(self, youtube_fetcher):
        """WHEN video has no transcript available
        THEN exception is raised with descriptive message."""
        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.side_effect = Exception("No transcript found")
            mock_api_class.return_value = mock_api

            with pytest.raises(Exception) as exc_info:
                youtube_fetcher.fetch('https://www.youtube.com/watch?v=dQw4w9WgXcQ')

            assert "Failed to fetch YouTube transcript" in str(exc_info.value)
            assert "No transcript found" in str(exc_info.value)

    def test_fetch_api_error(self, youtube_fetcher):
        """WHEN YouTube API returns an error
        THEN exception is raised and wrapped appropriately."""
        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.side_effect = Exception("API rate limit exceeded")
            mock_api_class.return_value = mock_api

            with pytest.raises(Exception) as exc_info:
                youtube_fetcher.fetch('https://youtu.be/test123')

            assert "Failed to fetch YouTube transcript" in str(exc_info.value)

    def test_fetch_empty_transcript(self, youtube_fetcher):
        """WHEN transcript exists but is empty
        THEN result contains empty content."""
        mock_transcript = Mock()
        mock_transcript.snippets = []
        mock_transcript.language = "en"

        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.return_value = mock_transcript
            mock_api_class.return_value = mock_api

            results = youtube_fetcher.fetch('https://www.youtube.com/watch?v=test')

            assert results[0]['content'] == ''
            assert results[0]['language'] == 'en'

    def test_fetch_with_special_characters_in_transcript(self, youtube_fetcher):
        """WHEN transcript contains special characters
        THEN they are preserved correctly."""
        mock_snippet1 = Mock()
        mock_snippet1.text = "Hello & welcome"

        mock_snippet2 = Mock()
        mock_snippet2.text = "Special chars: <>&\"'"

        mock_transcript = Mock()
        mock_transcript.snippets = [mock_snippet1, mock_snippet2]
        mock_transcript.language = "en"

        with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
            mock_api = Mock()
            mock_api.fetch.return_value = mock_transcript
            mock_api_class.return_value = mock_api

            results = youtube_fetcher.fetch('https://www.youtube.com/watch?v=test')

            expected_content = "Hello & welcome\nSpecial chars: <>&\"'"
            assert results[0]['content'] == expected_content

    # ===========================================
    # Channel Transcript Fetch Tests
    # ===========================================

    def test_fetch_channel_rss_success(self, youtube_fetcher):
        """WHEN channel RSS feed is fetched
        THEN video metadata is extracted correctly."""
        # Create mock feedparser response
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed.get.return_value = "Test Channel"

        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=abc123',
            'title': 'Test Video Title',
        }.get(k, d)
        mock_entry.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 0, 0)

        mock_feed.entries = [mock_entry]

        with patch('reconly_core.fetchers.youtube.feedparser.parse', return_value=mock_feed):
            videos = youtube_fetcher._fetch_channel_rss('UCtest123')

            assert len(videos) == 1
            assert videos[0]['video_id'] == 'abc123'
            assert videos[0]['title'] == 'Test Video Title'
            assert videos[0]['channel_id'] == 'UCtest123'

    def test_fetch_channel_rss_filters_by_since(self, youtube_fetcher):
        """WHEN since parameter is provided
        THEN only newer videos are returned."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed.get.return_value = "Test Channel"

        # Create entries with different dates
        old_entry = MagicMock()
        old_entry.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=old',
            'title': 'Old Video',
        }.get(k, d)
        old_entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 0, 0)

        new_entry = MagicMock()
        new_entry.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=new',
            'title': 'New Video',
        }.get(k, d)
        new_entry.published_parsed = (2024, 1, 20, 12, 0, 0, 0, 0, 0)

        mock_feed.entries = [old_entry, new_entry]

        with patch('reconly_core.fetchers.youtube.feedparser.parse', return_value=mock_feed):
            since = datetime(2024, 1, 10)
            videos = youtube_fetcher._fetch_channel_rss('UCtest123', since=since)

            assert len(videos) == 1
            assert videos[0]['video_id'] == 'new'

    def test_fetch_channel_returns_empty_when_no_rss(self, youtube_fetcher):
        """WHEN channel RSS returns empty feed
        THEN empty list is returned."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = []
        mock_feed.feed.get.return_value = "Empty Channel"

        with patch('reconly_core.fetchers.youtube.feedparser.parse', return_value=mock_feed):
            with patch.object(youtube_fetcher, 'extract_channel_id', return_value='UCtest123'):
                results = youtube_fetcher.fetch('https://www.youtube.com/channel/UCtest123')

                assert results == []

    def test_fetch_channel_skips_videos_without_transcripts(self, youtube_fetcher):
        """WHEN channel has videos without transcripts
        THEN those videos are skipped gracefully."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed.get.return_value = "Test Channel"

        mock_entry1 = MagicMock()
        mock_entry1.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=vid1',
            'title': 'Video 1 - Has Transcript',
        }.get(k, d)
        mock_entry1.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 0, 0)

        mock_entry2 = MagicMock()
        mock_entry2.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=vid2',
            'title': 'Video 2 - No Transcript',
        }.get(k, d)
        mock_entry2.published_parsed = (2024, 1, 16, 12, 0, 0, 0, 0, 0)

        mock_feed.entries = [mock_entry1, mock_entry2]

        mock_transcript = Mock()
        mock_transcript.snippets = [Mock(text="Hello")]
        mock_transcript.language = "en"

        def mock_fetch_video(video_id, languages):
            if video_id == 'vid1':
                return mock_transcript
            raise Exception("No transcript")

        with patch('reconly_core.fetchers.youtube.feedparser.parse', return_value=mock_feed):
            with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
                mock_api = Mock()
                mock_api.fetch.side_effect = mock_fetch_video
                mock_api_class.return_value = mock_api

                with patch.object(youtube_fetcher, 'extract_channel_id', return_value='UCtest123'):
                    results = youtube_fetcher.fetch('https://www.youtube.com/channel/UCtest123')

                    # Only video with transcript should be returned
                    assert len(results) == 1
                    assert results[0]['video_id'] == 'vid1'

    def test_fetch_channel_includes_channel_metadata(self, youtube_fetcher):
        """WHEN channel is fetched
        THEN results include channel ID and title."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed.get.return_value = "My Awesome Channel"

        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda k, d=None: {
            'link': 'https://www.youtube.com/watch?v=abc123',
            'title': 'Video Title',
        }.get(k, d)
        mock_entry.published_parsed = (2024, 1, 15, 12, 0, 0, 0, 0, 0)

        mock_feed.entries = [mock_entry]

        mock_transcript = Mock()
        mock_transcript.snippets = [Mock(text="Transcript content")]
        mock_transcript.language = "en"

        with patch('reconly_core.fetchers.youtube.feedparser.parse', return_value=mock_feed):
            with patch('reconly_core.fetchers.youtube.YouTubeTranscriptApi') as mock_api_class:
                mock_api = Mock()
                mock_api.fetch.return_value = mock_transcript
                mock_api_class.return_value = mock_api

                with patch.object(youtube_fetcher, 'extract_channel_id', return_value='UCmychannel'):
                    results = youtube_fetcher.fetch('https://www.youtube.com/@testchannel')

                    assert len(results) == 1
                    assert results[0]['channel_id'] == 'UCmychannel'
                    assert results[0]['channel_title'] == 'My Awesome Channel'
                    assert results[0]['published'] is not None
