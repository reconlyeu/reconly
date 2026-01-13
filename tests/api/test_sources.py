"""Tests for Source API routes."""
import pytest


@pytest.mark.api
class TestSourcesAPI:
    """Test suite for /api/v1/sources endpoints."""

    def test_list_sources_empty(self, client):
        """Test listing sources when none exist."""
        response = client.get("/api/v1/sources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_sources(self, client, sample_source):
        """Test listing sources."""
        response = client.get("/api/v1/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test RSS Feed"
        assert data[0]["type"] == "rss"

    def test_list_sources_filter_by_type(self, client, sample_source, test_db):
        """Test filtering sources by type."""
        from reconly_core.database.models import Source

        # Add another source with different type
        youtube_source = Source(
            name="Test YouTube",
            type="youtube",
            url="https://youtube.com/channel/test",
            enabled=True
        )
        test_db.add(youtube_source)
        test_db.commit()

        # Filter by rss
        response = client.get("/api/v1/sources?type=rss")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "rss"

        # Filter by youtube
        response = client.get("/api/v1/sources?type=youtube")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "youtube"

    def test_create_source(self, client):
        """Test creating a new source."""
        source_data = {
            "name": "New RSS Feed",
            "type": "rss",
            "url": "https://example.com/new-feed.xml",
            "enabled": True,
            "config": {"max_items": 20}
        }
        response = client.post("/api/v1/sources", json=source_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New RSS Feed"
        assert data["type"] == "rss"
        assert data["id"] is not None

    def test_create_source_validation_error(self, client):
        """Test creating source with invalid data."""
        # Missing required fields
        response = client.post("/api/v1/sources", json={})
        assert response.status_code == 422

        # Invalid type
        response = client.post("/api/v1/sources", json={
            "name": "Test",
            "type": "invalid_type",
            "url": "https://example.com"
        })
        assert response.status_code == 422

    def test_get_source(self, client, sample_source):
        """Test getting a specific source."""
        response = client.get(f"/api/v1/sources/{sample_source.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_source.id
        assert data["name"] == "Test RSS Feed"

    def test_get_source_not_found(self, client):
        """Test getting non-existent source."""
        response = client.get("/api/v1/sources/99999")
        assert response.status_code == 404

    def test_update_source(self, client, sample_source):
        """Test updating a source."""
        update_data = {
            "name": "Updated Feed Name",
            "enabled": False
        }
        response = client.put(f"/api/v1/sources/{sample_source.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Feed Name"
        assert data["enabled"] is False

    def test_update_source_not_found(self, client):
        """Test updating non-existent source."""
        response = client.put("/api/v1/sources/99999", json={"name": "Test"})
        assert response.status_code == 404

    def test_delete_source(self, client, sample_source):
        """Test deleting a source."""
        response = client.delete(f"/api/v1/sources/{sample_source.id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get(f"/api/v1/sources/{sample_source.id}")
        assert response.status_code == 404

    def test_delete_source_not_found(self, client):
        """Test deleting non-existent source."""
        response = client.delete("/api/v1/sources/99999")
        assert response.status_code == 404

    def test_toggle_source_enabled(self, client, sample_source):
        """Test toggling source enabled status via PATCH."""
        # Disable
        response = client.patch(f"/api/v1/sources/{sample_source.id}", json={"enabled": False})
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Re-enable
        response = client.patch(f"/api/v1/sources/{sample_source.id}", json={"enabled": True})
        assert response.status_code == 200
        assert response.json()["enabled"] is True


@pytest.mark.api
class TestSourceContentFilters:
    """Test suite for source content filter fields."""

    def test_create_source_with_filters(self, client):
        """Test creating a source with content filters."""
        source_data = {
            "name": "Filtered Feed",
            "type": "rss",
            "url": "https://example.com/feed.xml",
            "include_keywords": ["python", "ai"],
            "exclude_keywords": ["sponsored"],
            "filter_mode": "both",
            "use_regex": False,
        }
        response = client.post("/api/v1/sources", json=source_data)
        assert response.status_code == 201
        data = response.json()
        assert data["include_keywords"] == ["python", "ai"]
        assert data["exclude_keywords"] == ["sponsored"]
        assert data["filter_mode"] == "both"
        assert data["use_regex"] is False

    def test_create_source_with_regex_patterns(self, client):
        """Test creating a source with regex patterns."""
        source_data = {
            "name": "Regex Feed",
            "type": "rss",
            "url": "https://example.com/feed.xml",
            "include_keywords": [r"\bpython\b", r"ai|ml"],
            "use_regex": True,
        }
        response = client.post("/api/v1/sources", json=source_data)
        assert response.status_code == 201
        data = response.json()
        assert data["use_regex"] is True

    def test_create_source_invalid_regex(self, client):
        """Test creating source with invalid regex pattern."""
        source_data = {
            "name": "Bad Regex Feed",
            "type": "rss",
            "url": "https://example.com/feed.xml",
            "include_keywords": [r"[unclosed"],
            "use_regex": True,
        }
        response = client.post("/api/v1/sources", json=source_data)
        assert response.status_code == 422
        assert "Invalid regex pattern" in response.text

    def test_update_source_filters(self, client, sample_source):
        """Test updating source filter fields."""
        update_data = {
            "include_keywords": ["cloud", "aws"],
            "exclude_keywords": ["ad", "promo"],
            "filter_mode": "title_only",
        }
        response = client.put(f"/api/v1/sources/{sample_source.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["include_keywords"] == ["cloud", "aws"]
        assert data["exclude_keywords"] == ["ad", "promo"]
        assert data["filter_mode"] == "title_only"

    def test_update_source_clear_filters(self, client, test_db):
        """Test clearing source filters."""
        from reconly_core.database.models import Source

        # Create source with filters
        source = Source(
            name="Source with filters",
            type="rss",
            url="https://example.com/feed.xml",
            include_keywords=["test"],
            exclude_keywords=["spam"],
            filter_mode="both",
            use_regex=False,
        )
        test_db.add(source)
        test_db.commit()

        # Clear filters
        update_data = {
            "include_keywords": None,
            "exclude_keywords": None,
        }
        response = client.put(f"/api/v1/sources/{source.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["include_keywords"] is None
        assert data["exclude_keywords"] is None

    def test_get_source_with_filters(self, client, test_db):
        """Test retrieving source with filter fields."""
        from reconly_core.database.models import Source

        source = Source(
            name="Filtered Source",
            type="rss",
            url="https://example.com/feed.xml",
            include_keywords=["keyword1", "keyword2"],
            filter_mode="content",
            use_regex=True,
        )
        test_db.add(source)
        test_db.commit()

        response = client.get(f"/api/v1/sources/{source.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["include_keywords"] == ["keyword1", "keyword2"]
        assert data["filter_mode"] == "content"
        assert data["use_regex"] is True

    def test_filter_mode_validation(self, client):
        """Test that invalid filter_mode is rejected."""
        source_data = {
            "name": "Test",
            "type": "rss",
            "url": "https://example.com/feed.xml",
            "filter_mode": "invalid_mode",
        }
        response = client.post("/api/v1/sources", json=source_data)
        assert response.status_code == 422
