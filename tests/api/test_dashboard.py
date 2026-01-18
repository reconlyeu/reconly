"""Tests for Dashboard API routes."""
from datetime import datetime, timedelta

import pytest
from reconly_core.database.models import Digest, Feed, FeedRun, Source


@pytest.fixture
def sample_source(test_db):
    """Create a sample source for testing."""
    source = Source(
        name="Test Source",
        type="rss",
        url="https://example.com/feed.xml"
    )
    test_db.add(source)
    test_db.commit()
    test_db.refresh(source)
    return source


@pytest.fixture
def sample_feed(test_db, sample_source):
    """Create a sample feed for testing."""
    feed = Feed(
        name="Test Feed",
        schedule_enabled=True,
        last_run_at=datetime.utcnow()
    )
    test_db.add(feed)
    test_db.commit()
    test_db.refresh(feed)
    return feed


@pytest.fixture
def sample_digest(test_db):
    """Create a sample digest for testing."""
    digest = Digest(
        url="https://example.com/article",
        title="Test Article",
        content="This is test content.",
        summary="Test summary.",
        source_type="rss",
        language="en",
        estimated_cost=0.001
    )
    test_db.add(digest)
    test_db.commit()
    test_db.refresh(digest)
    return digest


@pytest.fixture
def sample_feed_run(test_db, sample_feed):
    """Create a sample completed feed run."""
    feed_run = FeedRun(
        feed_id=sample_feed.id,
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        digests_created=1
    )
    test_db.add(feed_run)
    test_db.commit()
    test_db.refresh(feed_run)
    return feed_run


@pytest.mark.api
class TestDashboardStats:
    """Test suite for /api/v1/dashboard/stats endpoint."""

    def test_get_dashboard_stats_empty(self, client):
        """Test dashboard stats when no data exists."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["sources_count"] == 0
        assert data["feeds_count"] == 0
        assert data["digests_count"] == 0
        assert data["tokens_today"] == 0
        assert data["tokens_week"] == 0
        assert data["success_rate"] == 0

    def test_get_dashboard_stats_with_data(self, client, sample_source, sample_feed, sample_digest):
        """Test dashboard stats with sample data."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["sources_count"] == 1
        assert data["feeds_count"] == 1
        assert data["digests_count"] == 1


@pytest.mark.api
class TestDashboardInsights:
    """Test suite for /api/v1/dashboard/insights endpoint."""

    def test_get_insights_empty(self, client):
        """Test insights endpoint when no data exists."""
        response = client.get("/api/v1/dashboard/insights")
        assert response.status_code == 200
        data = response.json()
        assert data["new_today"] == 0
        assert data["new_this_week"] == 0
        assert data["total_digests"] == 0
        assert data["feeds_healthy"] == 0
        assert data["feeds_failing"] == 0
        assert data["last_sync_at"] is None
        assert "daily_counts" in data
        assert len(data["daily_counts"]) == 7

    def test_get_insights_with_digest(self, client, sample_digest):
        """Test insights endpoint with a digest."""
        response = client.get("/api/v1/dashboard/insights")
        assert response.status_code == 200
        data = response.json()
        assert data["new_today"] == 1
        assert data["new_this_week"] == 1
        assert data["total_digests"] == 1

    def test_get_insights_with_feed_run(self, client, sample_feed, sample_feed_run):
        """Test insights endpoint shows last sync time."""
        response = client.get("/api/v1/dashboard/insights")
        assert response.status_code == 200
        data = response.json()
        assert data["last_sync_at"] is not None
        assert data["feeds_healthy"] == 1
        assert data["feeds_failing"] == 0

    def test_get_insights_response_structure(self, client):
        """Test that insights response has all required fields."""
        response = client.get("/api/v1/dashboard/insights")
        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "new_today", "new_this_week", "total_digests",
            "feeds_healthy", "feeds_failing", "last_sync_at",
            "daily_counts", "change_today", "change_week"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


@pytest.mark.api
class TestDashboardDigests:
    """Test suite for /api/v1/dashboard/digests endpoint."""

    def test_get_dashboard_digests_empty(self, client):
        """Test dashboard digests when none exist."""
        response = client.get("/api/v1/dashboard/digests")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["digests"] == []

    def test_get_dashboard_digests(self, client, sample_digest):
        """Test dashboard digests with data."""
        response = client.get("/api/v1/dashboard/digests")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["digests"]) == 1
        assert data["digests"][0]["title"] == "Test Article"

    def test_get_dashboard_digests_with_limit(self, client, test_db):
        """Test dashboard digests limit parameter."""
        # Create multiple digests
        for i in range(10):
            digest = Digest(
                url=f"https://example.com/article-{i}",
                title=f"Article {i}",
                content=f"Content {i}",
                summary=f"Summary {i}",
                source_type="rss",
                language="en",
                estimated_cost=0.001
            )
            test_db.add(digest)
        test_db.commit()

        response = client.get("/api/v1/dashboard/digests?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["digests"]) == 5

    def test_get_dashboard_digests_filter_today(self, client, test_db):
        """Test dashboard digests with 'today' filter."""
        # Create a digest from yesterday
        old_digest = Digest(
            url="https://example.com/old-article",
            title="Old Article",
            content="Old content",
            summary="Old summary",
            source_type="rss",
            language="en",
            estimated_cost=0.001,
            created_at=datetime.utcnow() - timedelta(hours=48)
        )
        test_db.add(old_digest)

        # Create a digest from today
        new_digest = Digest(
            url="https://example.com/new-article",
            title="New Article",
            content="New content",
            summary="New summary",
            source_type="rss",
            language="en",
            estimated_cost=0.001
        )
        test_db.add(new_digest)
        test_db.commit()

        response = client.get("/api/v1/dashboard/digests?since=today")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["digests"][0]["title"] == "New Article"

    def test_get_dashboard_digests_filter_week(self, client, sample_digest):
        """Test dashboard digests with 'week' filter."""
        response = client.get("/api/v1/dashboard/digests?since=week")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_get_dashboard_digests_filter_all(self, client, sample_digest):
        """Test dashboard digests with 'all' filter."""
        response = client.get("/api/v1/dashboard/digests?since=all")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


@pytest.mark.api
class TestDashboardFeeds:
    """Test suite for /api/v1/dashboard/feeds endpoint."""

    def test_get_dashboard_feeds_empty(self, client):
        """Test dashboard feeds when none exist."""
        response = client.get("/api/v1/dashboard/feeds")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_dashboard_feeds(self, client, sample_feed):
        """Test dashboard feeds with data."""
        response = client.get("/api/v1/dashboard/feeds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Feed"

    def test_get_dashboard_feeds_excludes_never_run(self, client, test_db):
        """Test that feeds with no runs are excluded."""
        # Create a feed that was never run
        feed = Feed(
            name="Never Run Feed",
            schedule_enabled=True,
            last_run_at=None
        )
        test_db.add(feed)
        test_db.commit()

        response = client.get("/api/v1/dashboard/feeds")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_dashboard_feeds_with_limit(self, client, test_db):
        """Test dashboard feeds limit parameter."""
        # Create multiple feeds with runs
        for i in range(10):
            feed = Feed(
                name=f"Feed {i}",
                schedule_enabled=True,
                last_run_at=datetime.utcnow() - timedelta(minutes=i)
            )
            test_db.add(feed)
        test_db.commit()

        response = client.get("/api/v1/dashboard/feeds?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_dashboard_feeds_ordered_by_last_run(self, client, test_db):
        """Test that feeds are ordered by last_run_at descending."""
        # Create feeds with different run times
        older_feed = Feed(
            name="Older Feed",
            schedule_enabled=True,
            last_run_at=datetime.utcnow() - timedelta(hours=2)
        )
        newer_feed = Feed(
            name="Newer Feed",
            schedule_enabled=True,
            last_run_at=datetime.utcnow()
        )
        test_db.add(older_feed)
        test_db.add(newer_feed)
        test_db.commit()

        response = client.get("/api/v1/dashboard/feeds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "Newer Feed"
        assert data[1]["name"] == "Older Feed"
