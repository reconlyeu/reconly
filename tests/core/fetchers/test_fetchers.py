"""Tests for fetcher factory and built-in fetchers."""
import pytest
from reconly_core.fetchers import get_fetcher, list_fetchers, is_fetcher_registered


class TestBuiltInFetchersRegistered:
    """Test that built-in fetchers are properly registered."""

    def test_rss_fetcher_registered(self):
        """Test that RSS fetcher is registered."""
        assert 'rss' in list_fetchers()
        assert is_fetcher_registered('rss')

    def test_youtube_fetcher_registered(self):
        """Test that YouTube fetcher is registered."""
        assert 'youtube' in list_fetchers()
        assert is_fetcher_registered('youtube')

    def test_website_fetcher_registered(self):
        """Test that website fetcher is registered."""
        assert 'website' in list_fetchers()
        assert is_fetcher_registered('website')


class TestFetcherFactory:
    """Tests for fetcher factory functions."""

    def test_get_fetcher_rss(self):
        """Test getting RSS fetcher."""
        fetcher = get_fetcher('rss')
        assert fetcher.get_source_type() == 'rss'
        assert hasattr(fetcher, 'fetch')

    def test_get_fetcher_youtube(self):
        """Test getting YouTube fetcher."""
        fetcher = get_fetcher('youtube')
        assert fetcher.get_source_type() == 'youtube'
        assert hasattr(fetcher, 'fetch')

    def test_get_fetcher_website(self):
        """Test getting website fetcher."""
        fetcher = get_fetcher('website')
        assert fetcher.get_source_type() == 'website'
        assert hasattr(fetcher, 'fetch')

    def test_get_fetcher_unknown_raises(self):
        """Test that get_fetcher raises for unknown source type."""
        with pytest.raises(ValueError) as exc_info:
            get_fetcher('unknown-source')

        assert 'unknown-source' in str(exc_info.value).lower()


class TestRSSFetcherInterface:
    """Test that RSSFetcher implements BaseFetcher interface."""

    def test_has_fetch_method(self):
        """Test that RSSFetcher has fetch method."""
        fetcher = get_fetcher('rss')
        assert hasattr(fetcher, 'fetch')
        assert callable(fetcher.fetch)

    def test_has_get_source_type_method(self):
        """Test that RSSFetcher has get_source_type method."""
        fetcher = get_fetcher('rss')
        assert hasattr(fetcher, 'get_source_type')
        assert fetcher.get_source_type() == 'rss'

    def test_has_can_handle_method(self):
        """Test that RSSFetcher has can_handle method."""
        fetcher = get_fetcher('rss')
        assert hasattr(fetcher, 'can_handle')

    def test_can_handle_rss_urls(self):
        """Test that RSSFetcher can handle RSS URLs."""
        fetcher = get_fetcher('rss')
        assert fetcher.can_handle('https://example.com/feed')
        assert fetcher.can_handle('https://example.com/rss')
        assert fetcher.can_handle('https://example.com/atom.xml')
        assert not fetcher.can_handle('https://example.com/page')

    def test_get_description(self):
        """Test that RSSFetcher has description."""
        fetcher = get_fetcher('rss')
        desc = fetcher.get_description()
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestYouTubeFetcherInterface:
    """Test that YouTubeFetcher implements BaseFetcher interface."""

    def test_has_fetch_method(self):
        """Test that YouTubeFetcher has fetch method."""
        fetcher = get_fetcher('youtube')
        assert hasattr(fetcher, 'fetch')
        assert callable(fetcher.fetch)

    def test_has_get_source_type_method(self):
        """Test that YouTubeFetcher has get_source_type method."""
        fetcher = get_fetcher('youtube')
        assert hasattr(fetcher, 'get_source_type')
        assert fetcher.get_source_type() == 'youtube'

    def test_has_can_handle_method(self):
        """Test that YouTubeFetcher has can_handle method."""
        fetcher = get_fetcher('youtube')
        assert hasattr(fetcher, 'can_handle')

    def test_can_handle_youtube_urls(self):
        """Test that YouTubeFetcher can handle YouTube URLs."""
        fetcher = get_fetcher('youtube')
        assert fetcher.can_handle('https://www.youtube.com/watch?v=abc123')
        assert fetcher.can_handle('https://youtu.be/abc123')
        assert fetcher.can_handle('https://www.youtube.com/channel/UCxxx')
        assert not fetcher.can_handle('https://example.com/video')

    def test_get_description(self):
        """Test that YouTubeFetcher has description."""
        fetcher = get_fetcher('youtube')
        desc = fetcher.get_description()
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestWebsiteFetcherInterface:
    """Test that WebsiteFetcher implements BaseFetcher interface."""

    def test_has_fetch_method(self):
        """Test that WebsiteFetcher has fetch method."""
        fetcher = get_fetcher('website')
        assert hasattr(fetcher, 'fetch')
        assert callable(fetcher.fetch)

    def test_has_get_source_type_method(self):
        """Test that WebsiteFetcher has get_source_type method."""
        fetcher = get_fetcher('website')
        assert hasattr(fetcher, 'get_source_type')
        assert fetcher.get_source_type() == 'website'

    def test_has_can_handle_method(self):
        """Test that WebsiteFetcher has can_handle method."""
        fetcher = get_fetcher('website')
        assert hasattr(fetcher, 'can_handle')

    def test_can_handle_website_urls(self):
        """Test that WebsiteFetcher can handle regular website URLs."""
        fetcher = get_fetcher('website')
        assert fetcher.can_handle('https://example.com/article')
        assert fetcher.can_handle('http://blog.example.com/post')
        # Should not handle URLs that other fetchers handle
        assert not fetcher.can_handle('https://www.youtube.com/watch?v=abc')

    def test_get_description(self):
        """Test that WebsiteFetcher has description."""
        fetcher = get_fetcher('website')
        desc = fetcher.get_description()
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestListFetchers:
    """Test list_fetchers function."""

    def test_returns_list(self):
        """Test that list_fetchers returns a list."""
        fetchers = list_fetchers()
        assert isinstance(fetchers, list)

    def test_contains_all_builtin_fetchers(self):
        """Test that list contains all built-in fetchers."""
        fetchers = list_fetchers()
        assert 'rss' in fetchers
        assert 'youtube' in fetchers
        assert 'website' in fetchers

    def test_at_least_three_fetchers(self):
        """Test that there are at least 3 built-in fetchers."""
        fetchers = list_fetchers()
        assert len(fetchers) >= 3
