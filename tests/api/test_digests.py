"""Tests for Digests API routes."""
import pytest
from reconly_core.database.models import Digest


@pytest.fixture
def sample_digest(test_db):
    """Create a sample digest for testing."""
    digest = Digest(
        url="https://example.com/article",
        title="Test Article",
        content="This is the full content of the test article.",
        summary="This is a summary of the test article.",
        source_type="rss",
        feed_url="https://example.com/feed.xml",
        feed_title="Example Feed",
        author="Test Author",
        provider="ollama",
        language="en",
        estimated_cost=0.001,
        tags=[]
    )
    test_db.add(digest)
    test_db.commit()
    test_db.refresh(digest)
    return digest


@pytest.mark.api
class TestDigestsAPI:
    """Test suite for /api/v1/digests endpoints."""

    def test_list_digests_empty(self, client):
        """Test listing digests when none exist."""
        response = client.get("/api/v1/digests")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["digests"] == []

    def test_list_digests(self, client, sample_digest):
        """Test listing digests."""
        response = client.get("/api/v1/digests")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["digests"]) == 1
        assert data["digests"][0]["title"] == "Test Article"

    def test_list_digests_with_limit(self, client, test_db):
        """Test listing digests with limit parameter."""
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

        # Request with limit
        response = client.get("/api/v1/digests?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["digests"]) == 5

    def test_list_digests_without_trailing_slash(self, client, sample_digest):
        """Test that digests endpoint works without trailing slash."""
        response = client.get("/api/v1/digests")
        assert response.status_code == 200

    def test_get_digest(self, client, sample_digest):
        """Test getting a specific digest."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_digest.id
        assert data["title"] == "Test Article"
        assert data["summary"] == "This is a summary of the test article."

    def test_get_digest_not_found(self, client):
        """Test getting non-existent digest."""
        response = client.get("/api/v1/digests/99999")
        assert response.status_code == 404

    def test_delete_digest(self, client, sample_digest):
        """Test deleting a digest."""
        response = client.delete(f"/api/v1/digests/{sample_digest.id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get(f"/api/v1/digests/{sample_digest.id}")
        assert response.status_code == 404

    def test_delete_digest_not_found(self, client):
        """Test deleting non-existent digest."""
        response = client.delete("/api/v1/digests/99999")
        assert response.status_code == 404


@pytest.mark.api
class TestDigestsResponseFormat:
    """Test that digests API returns correct response format."""

    def test_list_response_has_total_and_digests(self, client, sample_digest):
        """Verify list response has 'total' and 'digests' keys."""
        response = client.get("/api/v1/digests")
        assert response.status_code == 200
        data = response.json()

        # Must have these exact keys
        assert "total" in data
        assert "digests" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["digests"], list)

    def test_digest_response_structure(self, client, sample_digest):
        """Verify individual digest has expected fields."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}")
        assert response.status_code == 200
        data = response.json()

        # Check required fields exist
        expected_fields = [
            "id", "url", "title", "content", "summary",
            "source_type", "created_at"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
