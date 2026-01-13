"""Feed tracking system to avoid processing duplicate articles."""
import json
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path


class FeedTracker:
    """Tracks processed feeds to avoid duplicate processing."""

    def __init__(self, tracking_file: str = None):
        """
        Initialize the feed tracker.

        Args:
            tracking_file: Path to the tracking JSON file
                          (default: data/processed_feeds.json)
        """
        if tracking_file is None:
            # Default to data/processed_feeds.json in project root
            project_root = Path(__file__).parent.parent
            tracking_file = project_root / 'data' / 'processed_feeds.json'

        self.tracking_file = Path(tracking_file)
        self._ensure_data_dir()
        self.data = self._load_tracking_data()

    def _ensure_data_dir(self):
        """Ensure the data directory exists."""
        self.tracking_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_tracking_data(self) -> Dict:
        """Load tracking data from JSON file."""
        if not self.tracking_file.exists():
            return {}

        try:
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            return {}

    def _save_tracking_data(self):
        """Save tracking data to JSON file."""
        try:
            with open(self.tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise Exception(f"Failed to save tracking data: {str(e)}")

    def get_last_read(self, feed_url: str) -> Optional[datetime]:
        """
        Get the last read timestamp for a feed.

        Args:
            feed_url: URL of the feed

        Returns:
            datetime of last read, or None if feed hasn't been read before
        """
        feed_data = self.data.get(feed_url)
        if not feed_data:
            return None

        last_read_str = feed_data.get('last_read')
        if not last_read_str:
            return None

        try:
            return datetime.fromisoformat(last_read_str)
        except ValueError:
            return None

    def update_last_read(self, feed_url: str, timestamp: datetime = None):
        """
        Update the last read timestamp for a feed.

        Args:
            feed_url: URL of the feed
            timestamp: Timestamp to set (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        if feed_url not in self.data:
            self.data[feed_url] = {}

        self.data[feed_url]['last_read'] = timestamp.isoformat()
        self.data[feed_url]['updated_at'] = datetime.now().isoformat()

        self._save_tracking_data()

    def get_feed_info(self, feed_url: str) -> Dict:
        """
        Get all tracking information for a feed.

        Args:
            feed_url: URL of the feed

        Returns:
            Dictionary with tracking info (empty dict if not tracked)
        """
        return self.data.get(feed_url, {})

    def get_all_feeds(self) -> Dict:
        """
        Get tracking data for all feeds.

        Returns:
            Dictionary mapping feed URLs to their tracking data
        """
        return self.data.copy()

    def reset_feed(self, feed_url: str):
        """
        Reset tracking for a specific feed.

        Args:
            feed_url: URL of the feed to reset
        """
        if feed_url in self.data:
            del self.data[feed_url]
            self._save_tracking_data()

    def reset_all(self):
        """Reset tracking for all feeds."""
        self.data = {}
        self._save_tracking_data()
