"""Tests for feed tracking."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from freezegun import freeze_time
from reconly_core.tracking import FeedTracker


class TestFeedTracker:
    """Test suite for FeedTracker class."""

    @pytest.fixture
    def temp_tracking_file(self):
        """Create a temporary tracking file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = Path(f.name)
        yield temp_file
        if temp_file.exists():
            temp_file.unlink()

    def test_initialization(self, temp_tracking_file):
        """WHEN FeedTracker is initialized
        THEN tracking file and directory are created."""
        tracker = FeedTracker(str(temp_tracking_file))
        assert tracker.tracking_file.parent.exists()
        assert tracker.data == {}

    def test_update_and_get_last_read(self, temp_tracking_file):
        """WHEN last read is updated
        THEN timestamp is stored and can be retrieved."""
        tracker = FeedTracker(str(temp_tracking_file))

        timestamp = datetime(2025, 12, 30, 10, 30, 0)
        tracker.update_last_read('https://example.com/feed', timestamp)

        retrieved = tracker.get_last_read('https://example.com/feed')
        assert retrieved == timestamp

    def test_get_last_read_nonexistent(self, temp_tracking_file):
        """WHEN feed hasn't been read before
        THEN None is returned."""
        tracker = FeedTracker(str(temp_tracking_file))
        result = tracker.get_last_read('https://nonexistent.com/feed')
        assert result is None

    @freeze_time("2025-12-31 10:00:00")
    def test_update_last_read_default_timestamp(self, temp_tracking_file):
        """WHEN no timestamp is provided
        THEN current time is used."""
        tracker = FeedTracker(str(temp_tracking_file))
        tracker.update_last_read('https://example.com/feed')

        retrieved = tracker.get_last_read('https://example.com/feed')
        assert retrieved == datetime(2025, 12, 31, 10, 0, 0)

    def test_persistence(self, temp_tracking_file):
        """WHEN data is saved
        THEN it persists across instances."""
        tracker1 = FeedTracker(str(temp_tracking_file))
        timestamp = datetime(2025, 12, 30, 10, 30, 0)
        tracker1.update_last_read('https://example.com/feed', timestamp)

        # Create new instance with same file
        tracker2 = FeedTracker(str(temp_tracking_file))
        retrieved = tracker2.get_last_read('https://example.com/feed')
        assert retrieved == timestamp

    def test_get_feed_info(self, temp_tracking_file):
        """WHEN feed info is requested
        THEN all tracking data is returned."""
        tracker = FeedTracker(str(temp_tracking_file))
        timestamp = datetime(2025, 12, 30, 10, 30, 0)
        tracker.update_last_read('https://example.com/feed', timestamp)

        info = tracker.get_feed_info('https://example.com/feed')
        assert 'last_read' in info
        assert 'updated_at' in info

    def test_get_all_feeds(self, temp_tracking_file):
        """WHEN all feeds are requested
        THEN dictionary with all feeds is returned."""
        tracker = FeedTracker(str(temp_tracking_file))

        tracker.update_last_read('https://feed1.com/rss')
        tracker.update_last_read('https://feed2.com/rss')

        all_feeds = tracker.get_all_feeds()
        assert len(all_feeds) == 2
        assert 'https://feed1.com/rss' in all_feeds
        assert 'https://feed2.com/rss' in all_feeds

    def test_reset_feed(self, temp_tracking_file):
        """WHEN feed is reset
        THEN its tracking data is removed."""
        tracker = FeedTracker(str(temp_tracking_file))

        tracker.update_last_read('https://feed1.com/rss')
        tracker.update_last_read('https://feed2.com/rss')

        tracker.reset_feed('https://feed1.com/rss')

        all_feeds = tracker.get_all_feeds()
        assert len(all_feeds) == 1
        assert 'https://feed1.com/rss' not in all_feeds
        assert 'https://feed2.com/rss' in all_feeds

    def test_reset_all(self, temp_tracking_file):
        """WHEN all feeds are reset
        THEN all tracking data is cleared."""
        tracker = FeedTracker(str(temp_tracking_file))

        tracker.update_last_read('https://feed1.com/rss')
        tracker.update_last_read('https://feed2.com/rss')

        tracker.reset_all()

        all_feeds = tracker.get_all_feeds()
        assert len(all_feeds) == 0

    def test_corrupted_file_recovery(self, temp_tracking_file):
        """WHEN tracking file is corrupted
        THEN tracker starts fresh."""
        # Write invalid JSON to file
        temp_tracking_file.write_text("invalid json{{{")

        tracker = FeedTracker(str(temp_tracking_file))
        assert tracker.data == {}

    def test_missing_file(self, temp_tracking_file):
        """WHEN tracking file doesn't exist
        THEN it's created on first use."""
        # Remove file if it exists
        if temp_tracking_file.exists():
            temp_tracking_file.unlink()

        tracker = FeedTracker(str(temp_tracking_file))
        tracker.update_last_read('https://example.com/feed')

        assert temp_tracking_file.exists()
