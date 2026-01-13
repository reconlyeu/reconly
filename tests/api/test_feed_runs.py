"""Tests for Feed Runs API routes."""
import pytest


@pytest.mark.api
class TestFeedRunsAPI:
    """Test suite for /api/v1/feed-runs endpoints."""

    def test_list_feed_runs_empty(self, client):
        """Test listing feed runs when none exist."""
        response = client.get("/api/v1/feed-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_feed_runs(self, client, sample_feed_run):
        """Test listing feed runs."""
        response = client.get("/api/v1/feed-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "completed"

    def test_list_feed_runs_includes_feed_name(self, client, sample_feed_run):
        """Test that listed feed runs include feed_name."""
        response = client.get("/api/v1/feed-runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        # Feed name should be included via join
        assert data["items"][0]["feed_name"] == "Test Feed"

    def test_list_feed_runs_includes_trace_id(self, client, sample_feed_run):
        """Test that listed feed runs include trace_id."""
        response = client.get("/api/v1/feed-runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["trace_id"] == "test-trace-id-12345"

    def test_list_feed_runs_filter_by_status(self, client, sample_feed_run, sample_failed_feed_run):
        """Test filtering feed runs by status."""
        # Filter completed
        response = client.get("/api/v1/feed-runs?status=completed")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "completed"

        # Filter failed
        response = client.get("/api/v1/feed-runs?status=failed")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "failed"

    def test_list_feed_runs_filter_by_feed_id(self, client, sample_feed, sample_feed_run):
        """Test filtering feed runs by feed_id."""
        response = client.get(f"/api/v1/feed-runs?feed_id={sample_feed.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["feed_id"] == sample_feed.id

        # Non-existent feed
        response = client.get("/api/v1/feed-runs?feed_id=99999")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_feed_runs_pagination(self, client, sample_feed_run, sample_failed_feed_run):
        """Test feed runs pagination."""
        # Limit to 1
        response = client.get("/api/v1/feed-runs?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1

        # Offset
        response = client.get("/api/v1/feed-runs?limit=1&offset=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1

    def test_get_feed_run(self, client, sample_feed_run):
        """Test getting a specific feed run."""
        response = client.get(f"/api/v1/feed-runs/{sample_feed_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_feed_run.id
        assert data["status"] == "completed"
        assert data["feed_name"] == "Test Feed"
        assert data["trace_id"] == "test-trace-id-12345"

    def test_get_feed_run_includes_digests_count(self, client, sample_feed_run):
        """Test that feed run detail includes digests_count."""
        response = client.get(f"/api/v1/feed-runs/{sample_feed_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "digests_count" in data
        assert data["digests_count"] == 0  # No digests created in test

    def test_get_feed_run_includes_duration(self, client, sample_feed_run):
        """Test that feed run detail includes duration_seconds."""
        response = client.get(f"/api/v1/feed-runs/{sample_feed_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "duration_seconds" in data
        # Should be approximately 5 minutes (300 seconds)
        assert data["duration_seconds"] is not None
        assert 250 <= data["duration_seconds"] <= 350

    def test_get_feed_run_not_found(self, client):
        """Test getting non-existent feed run."""
        response = client.get("/api/v1/feed-runs/99999")
        assert response.status_code == 404

    def test_get_feed_run_with_error_details(self, client, sample_failed_feed_run):
        """Test getting a failed feed run with error_details."""
        response = client.get(f"/api/v1/feed-runs/{sample_failed_feed_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_details"] is not None
        assert "errors" in data["error_details"]
        assert len(data["error_details"]["errors"]) == 1
        assert data["error_details"]["errors"][0]["error_type"] == "FetchError"

    def test_get_feed_run_sources(self, client, sample_feed_run):
        """Test getting sources for a feed run."""
        response = client.get(f"/api/v1/feed-runs/{sample_feed_run.id}/sources")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == sample_feed_run.id
        assert "sources" in data
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source_name"] == "Test RSS Feed"
        assert data["sources"][0]["status"] == "success"

    def test_get_feed_run_sources_not_found(self, client):
        """Test getting sources for non-existent feed run."""
        response = client.get("/api/v1/feed-runs/99999/sources")
        assert response.status_code == 404

    def test_get_feed_run_digests(self, client, sample_feed_run):
        """Test getting digests for a feed run."""
        response = client.get(f"/api/v1/feed-runs/{sample_feed_run.id}/digests")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0  # No digests created in test

    def test_get_feed_run_digests_not_found(self, client):
        """Test getting digests for non-existent feed run."""
        response = client.get("/api/v1/feed-runs/99999/digests")
        assert response.status_code == 404
