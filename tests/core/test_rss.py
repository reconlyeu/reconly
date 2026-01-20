"""Tests for RSS feed fetching."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from reconly_core.fetchers.rss import RSSFetcher


class TestRSSFetcher:
    """Test suite for RSSFetcher class."""

    @pytest.fixture(autouse=True)
    def disable_age_limit(self, monkeypatch):
        """Disable the first-run age limit for tests with mock data."""
        monkeypatch.setenv('RSS_FIRST_RUN_MAX_AGE_DAYS', '0')

    @pytest.fixture
    def rss_fetcher(self):
        """Create RSSFetcher instance for testing."""
        return RSSFetcher()

    @pytest.fixture
    def mock_rss_feed(self):
        """Mock RSS 2.0 feed structure."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test RSS Feed'}

        entry = Mock()
        # Configure get() method to return dict-style values
        entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/article1',
            'title': 'Test Article'
        }.get(k, default))
        entry.summary = 'This is a test article description'
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        entry.author = 'John Doe'
        entry.content = None
        entry.description = None

        mock_feed.entries = [entry]
        return mock_feed

    @pytest.fixture
    def mock_atom_feed(self):
        """Mock Atom 1.0 feed structure."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Atom Feed'}

        entry = Mock()
        # Configure get() method to return dict-style values
        entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/atom-article',
            'title': 'Atom Article'
        }.get(k, default))

        # Atom uses content field
        content_obj = Mock()
        content_obj.value = 'This is atom content'
        entry.content = [content_obj]
        entry.summary = None
        entry.description = None

        entry.updated_parsed = (2025, 12, 31, 10, 30, 0, 0, 0, 0)
        entry.author = 'Jane Smith'

        mock_feed.entries = [entry]
        return mock_feed

    def test_fetch_rss_feed_success(self, rss_fetcher, mock_rss_feed):
        """WHEN a valid RSS 2.0 feed is provided
        THEN all articles are extracted with title, link, description, and publication date."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            articles = rss_fetcher.fetch('https://example.com/feed')

            assert len(articles) == 1
            article = articles[0]
            assert article['url'] == 'https://example.com/article1'
            assert article['title'] == 'Test Article'
            assert article['content'] == 'This is a test article description'
            assert article['published'] == '2025-12-30T12:00:00'
            assert article['author'] == 'John Doe'
            assert article['source_type'] == 'rss'
            assert article['feed_url'] == 'https://example.com/feed'
            assert article['feed_title'] == 'Test RSS Feed'

    def test_fetch_atom_feed_success(self, rss_fetcher, mock_atom_feed):
        """WHEN a valid Atom 1.0 feed is provided
        THEN all entries are extracted with correct field mapping."""
        with patch('feedparser.parse', return_value=mock_atom_feed):
            articles = rss_fetcher.fetch('https://example.com/atom')

            assert len(articles) == 1
            article = articles[0]
            assert article['url'] == 'https://example.com/atom-article'
            assert article['title'] == 'Atom Article'
            assert article['content'] == 'This is atom content'
            assert article['published'] == '2025-12-31T10:30:00'
            assert article['source_type'] == 'rss'

    def test_fetch_invalid_xml(self, rss_fetcher):
        """WHEN invalid XML is provided
        THEN appropriate error is raised with descriptive message."""
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("Invalid XML")
        mock_feed.entries = []

        with patch('feedparser.parse', return_value=mock_feed):
            with pytest.raises(Exception) as exc_info:
                rss_fetcher.fetch('https://example.com/invalid')

            assert "Failed to parse RSS feed" in str(exc_info.value)

    def test_fetch_missing_required_fields(self, rss_fetcher):
        """WHEN feed entries lack required fields (title/link)
        THEN entries are processed with default values."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        entry = Mock()
        # Missing link and title - should use defaults
        entry.get = Mock(side_effect=lambda k, default=None: default)
        entry.summary = 'Content without title'
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        entry.author = None
        entry.content = None
        entry.description = None

        mock_feed.entries = [entry]

        with patch('feedparser.parse', return_value=mock_feed):
            articles = rss_fetcher.fetch('https://example.com/feed')

            assert len(articles) == 1
            assert articles[0]['title'] == 'No title'
            assert articles[0]['url'] == 'https://example.com/feed'

    def test_fetch_html_entities_decoded(self, rss_fetcher):
        """WHEN feed contains HTML entities in content
        THEN entities are correctly handled (feedparser handles this)."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        entry = Mock()
        entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/article',
            'title': 'Article with &amp; entities'
        }.get(k, default))
        entry.summary = 'Content with &lt;tags&gt; and &quot;quotes&quot;'
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        entry.author = None
        entry.content = None
        entry.description = None

        mock_feed.entries = [entry]

        with patch('feedparser.parse', return_value=mock_feed):
            articles = rss_fetcher.fetch('https://example.com/feed')

            # feedparser automatically decodes entities, so we just verify it works
            assert len(articles) == 1
            assert articles[0]['title'] == 'Article with &amp; entities'

    def test_fetch_with_since_parameter(self, rss_fetcher):
        """WHEN feed contains items older than 'since' parameter
        THEN those items are excluded from results."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        # Old article (before 'since')
        old_entry = Mock()
        old_entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/old',
            'title': 'Old Article'
        }.get(k, default))
        old_entry.summary = 'Old content'
        old_entry.published_parsed = (2025, 12, 25, 12, 0, 0, 0, 0, 0)
        old_entry.author = None
        old_entry.content = None
        old_entry.description = None

        # New article (after 'since')
        new_entry = Mock()
        new_entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/new',
            'title': 'New Article'
        }.get(k, default))
        new_entry.summary = 'New content'
        new_entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        new_entry.author = None
        new_entry.content = None
        new_entry.description = None

        mock_feed.entries = [old_entry, new_entry]

        with patch('feedparser.parse', return_value=mock_feed):
            since_date = datetime(2025, 12, 28, 0, 0, 0)
            articles = rss_fetcher.fetch('https://example.com/feed', since=since_date)

            # Only new article should be returned
            assert len(articles) == 1
            assert articles[0]['title'] == 'New Article'

    def test_extract_date_from_various_fields(self, rss_fetcher):
        """WHEN entry has date in different fields
        THEN date is extracted correctly."""
        # Test with published field
        entry = Mock()
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        date = rss_fetcher._extract_date(entry)
        assert date == datetime(2025, 12, 30, 12, 0, 0)

        # Test with updated field when published is missing
        entry = Mock()
        entry.published_parsed = None
        entry.updated_parsed = (2025, 12, 31, 10, 30, 0, 0, 0, 0)
        date = rss_fetcher._extract_date(entry)
        assert date == datetime(2025, 12, 31, 10, 30, 0)

    def test_extract_content_priority(self, rss_fetcher):
        """WHEN entry has content in multiple fields
        THEN content field takes priority over summary."""
        entry = Mock()
        content_obj = Mock()
        content_obj.value = 'Content from content field'
        entry.content = [content_obj]
        entry.summary = 'Content from summary field'
        entry.description = 'Content from description field'

        content = rss_fetcher._extract_content(entry)
        assert content == 'Content from content field'

    def test_extract_author_various_fields(self, rss_fetcher):
        """WHEN author information is in different fields
        THEN author is extracted correctly."""
        # Test with author field
        entry = Mock()
        entry.author = 'John Doe'
        entry.author_detail = None
        entry.dc_creator = None
        author = rss_fetcher._extract_author(entry)
        assert author == 'John Doe'

        # Test with author_detail when author is missing
        entry = Mock()
        entry.author = None
        entry.author_detail = {'name': 'Jane Smith'}
        entry.dc_creator = None
        author = rss_fetcher._extract_author(entry)
        assert author == 'Jane Smith'

    def test_is_rss_url(self, rss_fetcher):
        """WHEN URL is checked for RSS indicators
        THEN correct identification is returned."""
        assert rss_fetcher.is_rss_url('https://example.com/feed') is True
        assert rss_fetcher.is_rss_url('https://example.com/rss') is True
        assert rss_fetcher.is_rss_url('https://example.com/atom.xml') is True
        assert rss_fetcher.is_rss_url('https://example.com/feed.xml') is True
        assert rss_fetcher.is_rss_url('https://example.com/blog') is False
        assert rss_fetcher.is_rss_url('https://example.com/') is False

    def test_fetch_network_error(self, rss_fetcher):
        """WHEN network error occurs during fetch
        THEN exception is raised with error message."""
        with patch('feedparser.parse', side_effect=Exception("Network error")):
            with pytest.raises(Exception) as exc_info:
                rss_fetcher.fetch('https://example.com/feed')

            assert "Failed to fetch RSS feed" in str(exc_info.value)
            assert "Network error" in str(exc_info.value)

    def test_fetch_multiple_entries(self, rss_fetcher):
        """WHEN feed contains multiple entries
        THEN all entries are returned."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        entries = []
        for i in range(5):
            entry = Mock()
            entry.get = Mock(side_effect=lambda k, default=None, i=i: {
                'link': f'https://example.com/article{i}',
                'title': f'Article {i}'
            }.get(k, default))
            entry.summary = f'Content {i}'
            entry.published_parsed = (2025, 12, 30, 12, i, 0, 0, 0, 0)
            entry.author = f'Author {i}'
            entry.content = None
            entry.description = None
            entries.append(entry)

        mock_feed.entries = entries

        with patch('feedparser.parse', return_value=mock_feed):
            articles = rss_fetcher.fetch('https://example.com/feed')

            assert len(articles) == 5
            # Articles are sorted by date descending (newest first)
            # Entry 4 has the latest time (minute=4), so it comes first
            for i, article in enumerate(articles):
                expected_idx = 4 - i  # Reverse order: 4, 3, 2, 1, 0
                assert article['title'] == f'Article {expected_idx}'
                assert article['author'] == f'Author {expected_idx}'

    def test_first_run_age_limit(self, rss_fetcher, monkeypatch):
        """WHEN fetching a feed for the first time (since=None)
        AND RSS_FIRST_RUN_MAX_AGE_DAYS is set
        THEN only articles within the age limit are returned."""
        from datetime import timedelta

        # Set age limit to 1 day
        monkeypatch.setenv('RSS_FIRST_RUN_MAX_AGE_DAYS', '1')

        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        now = datetime.now()
        entries = []

        # Create article from 6 hours ago (should be included)
        recent_entry = Mock()
        recent_time = now - timedelta(hours=6)
        recent_entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/recent',
            'title': 'Recent Article'
        }.get(k, default))
        recent_entry.summary = 'Recent content'
        recent_entry.published_parsed = recent_time.timetuple()[:9]
        recent_entry.author = 'Author'
        recent_entry.content = None
        recent_entry.description = None
        entries.append(recent_entry)

        # Create article from 3 days ago (should be filtered out)
        old_entry = Mock()
        old_time = now - timedelta(days=3)
        old_entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/old',
            'title': 'Old Article'
        }.get(k, default))
        old_entry.summary = 'Old content'
        old_entry.published_parsed = old_time.timetuple()[:9]
        old_entry.author = 'Author'
        old_entry.content = None
        old_entry.description = None
        entries.append(old_entry)

        mock_feed.entries = entries

        with patch('feedparser.parse', return_value=mock_feed):
            # First run (since=None) should apply age limit
            articles = rss_fetcher.fetch('https://example.com/feed')

            assert len(articles) == 1
            assert articles[0]['title'] == 'Recent Article'

    def test_first_run_age_limit_zero_fetches_all(self, rss_fetcher, monkeypatch):
        """WHEN RSS_FIRST_RUN_MAX_AGE_DAYS=0
        THEN all articles are fetched regardless of age."""
        from datetime import timedelta

        # Set age limit to 0 (disabled)
        monkeypatch.setenv('RSS_FIRST_RUN_MAX_AGE_DAYS', '0')

        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        now = datetime.now()

        # Create article from 30 days ago
        old_entry = Mock()
        old_time = now - timedelta(days=30)
        old_entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/old',
            'title': 'Old Article'
        }.get(k, default))
        old_entry.summary = 'Old content'
        old_entry.published_parsed = old_time.timetuple()[:9]
        old_entry.author = 'Author'
        old_entry.content = None
        old_entry.description = None

        mock_feed.entries = [old_entry]

        with patch('feedparser.parse', return_value=mock_feed):
            articles = rss_fetcher.fetch('https://example.com/feed')

            assert len(articles) == 1
            assert articles[0]['title'] == 'Old Article'


class TestRSSFetcherFullContent:
    """Test suite for fetch_full_content functionality."""

    @pytest.fixture(autouse=True)
    def disable_age_limit(self, monkeypatch):
        """Disable the first-run age limit for tests."""
        monkeypatch.setenv('RSS_FIRST_RUN_MAX_AGE_DAYS', '0')

    @pytest.fixture
    def rss_fetcher(self):
        """Create RSSFetcher instance for testing."""
        return RSSFetcher()

    @pytest.fixture
    def mock_rss_feed(self):
        """Mock RSS feed with articles that have links."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test RSS Feed'}

        entry = Mock()
        entry.get = Mock(side_effect=lambda k, default=None: {
            'link': 'https://example.com/article1',
            'title': 'Test Article'
        }.get(k, default))
        entry.summary = 'This is the RSS summary/description'
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        entry.author = 'John Doe'
        entry.content = None
        entry.description = None

        mock_feed.entries = [entry]
        return mock_feed

    def test_fetch_without_full_content_does_not_scrape(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=False (default)
        THEN articles have 'content' from RSS summary
        AND articles do NOT have 'full_content' field."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=False)

            assert len(articles) == 1
            article = articles[0]
            assert article['content'] == 'This is the RSS summary/description'
            assert 'full_content' not in article

    def test_fetch_with_full_content_adds_full_content_field(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=True
        THEN articles have both 'content' (RSS summary) and 'full_content' (scraped)
        AND full_content contains the scraped article text."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            # Mock WebsiteFetcher.fetch() to return full content
            mock_website_content = [{
                'url': 'https://example.com/article1',
                'title': 'Test Article',
                'content': 'This is the full scraped article content with much more detail.',
                'source_type': 'website'
            }]

            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', return_value=mock_website_content):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                article = articles[0]
                # Should have both RSS summary and full content
                assert article['content'] == 'This is the RSS summary/description'
                assert article['full_content'] == 'This is the full scraped article content with much more detail.'
                assert article['url'] == 'https://example.com/article1'

    def test_fetch_full_content_graceful_fallback_on_exception(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=True AND WebsiteFetcher raises exception (403, timeout, etc.)
        THEN articles still have 'content' from RSS summary
        AND articles do NOT have 'full_content' field (graceful fallback)
        AND feed run continues successfully."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            # Mock WebsiteFetcher.fetch() to raise an exception
            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', side_effect=Exception('HTTP 403 Forbidden')):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                article = articles[0]
                # Should still have RSS summary
                assert article['content'] == 'This is the RSS summary/description'
                # Should NOT have full_content field due to scraping failure
                assert 'full_content' not in article
                # Feed run should succeed despite scraping failure
                assert article['title'] == 'Test Article'

    def test_fetch_full_content_ignores_empty_content(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=True AND WebsiteFetcher returns empty content
        THEN articles have 'content' from RSS summary
        AND articles do NOT have 'full_content' field."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            # Mock WebsiteFetcher.fetch() to return empty content
            mock_website_content = [{
                'url': 'https://example.com/article1',
                'title': 'Test Article',
                'content': '',  # Empty content
                'source_type': 'website'
            }]

            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', return_value=mock_website_content):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                article = articles[0]
                # Should have RSS summary
                assert article['content'] == 'This is the RSS summary/description'
                # Should NOT add empty full_content
                assert 'full_content' not in article

    def test_fetch_full_content_ignores_none_content(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=True AND WebsiteFetcher returns None as content
        THEN articles do NOT have 'full_content' field."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            # Mock WebsiteFetcher.fetch() to return None content
            mock_website_content = [{
                'url': 'https://example.com/article1',
                'title': 'Test Article',
                'content': None,
                'source_type': 'website'
            }]

            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', return_value=mock_website_content):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                article = articles[0]
                assert 'full_content' not in article

    def test_fetch_full_content_handles_empty_response_list(self, rss_fetcher, mock_rss_feed):
        """WHEN fetch_full_content=True AND WebsiteFetcher returns empty list
        THEN articles do NOT have 'full_content' field."""
        with patch('feedparser.parse', return_value=mock_rss_feed):
            # Mock WebsiteFetcher.fetch() to return empty list
            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', return_value=[]):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                article = articles[0]
                assert 'full_content' not in article

    def test_fetch_full_content_processes_multiple_articles(self, rss_fetcher):
        """WHEN fetch_full_content=True AND feed has multiple articles
        THEN each article is scraped independently
        AND successful scrapes add full_content while failures fall back gracefully."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        # Create 3 entries
        entries = []
        for i in range(3):
            entry = Mock()
            entry.get = Mock(side_effect=lambda k, default=None, i=i: {
                'link': f'https://example.com/article{i}',
                'title': f'Article {i}'
            }.get(k, default))
            entry.summary = f'RSS summary {i}'
            entry.published_parsed = (2025, 12, 30, 12, i, 0, 0, 0, 0)
            entry.author = 'Author'
            entry.content = None
            entry.description = None
            entries.append(entry)

        mock_feed.entries = entries

        with patch('feedparser.parse', return_value=mock_feed):
            # Mock WebsiteFetcher to succeed for article0, fail for article1, return empty for article2
            def mock_website_fetch(url):
                if 'article0' in url:
                    return [{'url': url, 'title': 'Article 0', 'content': 'Full content 0'}]
                elif 'article1' in url:
                    raise Exception('403 Forbidden')
                else:  # article2
                    return [{'url': url, 'title': 'Article 2', 'content': ''}]

            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', side_effect=mock_website_fetch):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 3

                # Article 0: should have full_content (successful scrape)
                article0 = next(a for a in articles if a['title'] == 'Article 0')
                assert article0['content'] == 'RSS summary 0'
                assert article0['full_content'] == 'Full content 0'

                # Article 1: should NOT have full_content (scraping failed)
                article1 = next(a for a in articles if a['title'] == 'Article 1')
                assert article1['content'] == 'RSS summary 1'
                assert 'full_content' not in article1

                # Article 2: should NOT have full_content (empty content)
                article2 = next(a for a in articles if a['title'] == 'Article 2')
                assert article2['content'] == 'RSS summary 2'
                assert 'full_content' not in article2

    def test_fetch_full_content_with_missing_link_uses_feed_url(self, rss_fetcher):
        """WHEN fetch_full_content=True AND article has no link
        THEN article URL falls back to feed URL
        AND scraping is attempted with feed URL (though likely returns empty)."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}

        entry = Mock()
        # Entry without link - will fall back to feed URL
        entry.get = Mock(side_effect=lambda k, default=None: {
            'title': 'Article Without Link'
        }.get(k, default))
        entry.summary = 'RSS summary'
        entry.published_parsed = (2025, 12, 30, 12, 0, 0, 0, 0, 0)
        entry.author = None
        entry.content = None
        entry.description = None

        mock_feed.entries = [entry]

        with patch('feedparser.parse', return_value=mock_feed):
            # Mock WebsiteFetcher to return empty content (feed URL likely isn't a valid article)
            with patch('reconly_core.fetchers.website.WebsiteFetcher.fetch', return_value=[]):
                articles = rss_fetcher.fetch('https://example.com/feed', fetch_full_content=True)

                assert len(articles) == 1
                # Article URL should fall back to feed URL when link is missing
                assert articles[0]['url'] == 'https://example.com/feed'
                # Should have RSS summary
                assert articles[0]['content'] == 'RSS summary'
                # Should NOT have full_content (empty response from WebsiteFetcher)
                assert 'full_content' not in articles[0]
