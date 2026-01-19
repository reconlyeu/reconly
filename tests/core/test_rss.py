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
