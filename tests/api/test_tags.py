"""Tests for Tags API routes."""
import pytest
from reconly_core.database.models import Digest, Tag, DigestTag


@pytest.fixture
def sample_tags(test_db):
    """Create sample tags for testing."""
    tags = []
    for name in ["tech", "ai", "news", "python"]:
        tag = Tag(name=name)
        test_db.add(tag)
        tags.append(tag)
    test_db.commit()
    for tag in tags:
        test_db.refresh(tag)
    return tags


@pytest.fixture
def sample_digest_with_tags(test_db, sample_tags):
    """Create a sample digest with tags for testing."""
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
    )
    test_db.add(digest)
    test_db.flush()

    # Add some tags to the digest
    for tag in sample_tags[:2]:  # Add "tech" and "ai"
        digest_tag = DigestTag(digest_id=digest.id, tag_id=tag.id)
        test_db.add(digest_tag)

    test_db.commit()
    test_db.refresh(digest)
    return digest


@pytest.mark.api
class TestTagsAPI:
    """Test suite for /api/v1/tags/ endpoints."""

    def test_list_tags_empty(self, client):
        """Test listing tags when none exist."""
        response = client.get("/api/v1/tags/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["tags"] == []

    def test_list_tags(self, client, sample_tags):
        """Test listing all tags."""
        response = client.get("/api/v1/tags/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert len(data["tags"]) == 4

        # Check tag structure
        tag_names = {t["name"] for t in data["tags"]}
        assert tag_names == {"tech", "ai", "news", "python"}

    def test_list_tags_with_digest_counts(self, client, sample_digest_with_tags):
        """Test that tags include digest counts."""
        response = client.get("/api/v1/tags/")
        assert response.status_code == 200
        data = response.json()

        # Find the tags that are attached to the digest
        tags_by_name = {t["name"]: t for t in data["tags"]}

        # tech and ai should have count 1
        assert tags_by_name["tech"]["digest_count"] == 1
        assert tags_by_name["ai"]["digest_count"] == 1

        # news and python should have count 0
        assert tags_by_name["news"]["digest_count"] == 0
        assert tags_by_name["python"]["digest_count"] == 0

    def test_list_tags_sorted_by_count(self, client, test_db, sample_tags):
        """Test that tags are sorted by digest count descending."""
        # Create digests with different tag counts
        for i in range(3):
            digest = Digest(
                url=f"https://example.com/article-{i}",
                title=f"Article {i}",
                summary=f"Summary {i}",
                source_type="rss",
                language="en",
            )
            test_db.add(digest)
            test_db.flush()

            # Give tech 3 uses, ai 2 uses, news 1 use
            if i < 3:
                test_db.add(DigestTag(digest_id=digest.id, tag_id=sample_tags[0].id))  # tech
            if i < 2:
                test_db.add(DigestTag(digest_id=digest.id, tag_id=sample_tags[1].id))  # ai
            if i < 1:
                test_db.add(DigestTag(digest_id=digest.id, tag_id=sample_tags[2].id))  # news

        test_db.commit()

        response = client.get("/api/v1/tags/")
        assert response.status_code == 200
        data = response.json()

        # First tags should be sorted by count
        counts = [t["digest_count"] for t in data["tags"]]
        assert counts == sorted(counts, reverse=True)


@pytest.mark.api
class TestTagSuggestionsAPI:
    """Test suite for /api/v1/tags/suggestions/ endpoint."""

    def test_suggestions_empty_query(self, client, sample_tags):
        """Test getting suggestions without a query returns all tags."""
        response = client.get("/api/v1/tags/suggestions/")
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        # Should return all tags up to limit
        assert len(data["suggestions"]) == 4

    def test_suggestions_with_prefix(self, client, sample_tags):
        """Test getting suggestions with prefix filter."""
        response = client.get("/api/v1/tags/suggestions/?q=te")
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

        # Should only return "tech"
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["name"] == "tech"

    def test_suggestions_case_insensitive(self, client, sample_tags):
        """Test that suggestions search is case-insensitive."""
        response = client.get("/api/v1/tags/suggestions/?q=AI")
        assert response.status_code == 200
        data = response.json()

        # Should find "ai" even with uppercase query
        names = [s["name"] for s in data["suggestions"]]
        assert "ai" in names

    def test_suggestions_with_limit(self, client, sample_tags):
        """Test suggestions respect limit parameter."""
        response = client.get("/api/v1/tags/suggestions/?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2

    def test_suggestions_include_digest_count(self, client, sample_digest_with_tags):
        """Test that suggestions include digest count."""
        response = client.get("/api/v1/tags/suggestions/?q=tech")
        assert response.status_code == 200
        data = response.json()

        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["name"] == "tech"
        assert data["suggestions"][0]["digest_count"] == 1


@pytest.mark.api
class TestDigestTagsUpdate:
    """Test suite for PATCH /api/v1/digests/{id}/tags endpoint."""

    def test_update_digest_tags(self, client, sample_digest_with_tags):
        """Test updating tags on a digest."""
        response = client.patch(
            f"/api/v1/digests/{sample_digest_with_tags.id}/tags",
            json={"tags": ["python", "news"]}
        )
        assert response.status_code == 200
        data = response.json()

        # Verify new tags are set
        assert set(data["tags"]) == {"python", "news"}

    def test_update_digest_tags_creates_new(self, client, sample_digest_with_tags):
        """Test that updating tags can create new tags."""
        response = client.patch(
            f"/api/v1/digests/{sample_digest_with_tags.id}/tags",
            json={"tags": ["new-tag", "another-new-tag"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert set(data["tags"]) == {"new-tag", "another-new-tag"}

        # Verify tags were created in database
        response = client.get("/api/v1/tags/")
        data = response.json()
        tag_names = {t["name"] for t in data["tags"]}
        assert "new-tag" in tag_names
        assert "another-new-tag" in tag_names

    def test_update_digest_tags_empty(self, client, sample_digest_with_tags):
        """Test removing all tags from a digest."""
        response = client.patch(
            f"/api/v1/digests/{sample_digest_with_tags.id}/tags",
            json={"tags": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []

    def test_update_digest_tags_not_found(self, client):
        """Test updating tags on non-existent digest."""
        response = client.patch(
            "/api/v1/digests/99999/tags",
            json={"tags": ["tech"]}
        )
        assert response.status_code == 404
