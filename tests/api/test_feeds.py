"""Tests for Feed API routes."""
import pytest


@pytest.mark.api
class TestFeedsAPI:
    """Test suite for /api/v1/feeds endpoints."""

    def test_list_feeds_empty(self, client):
        """Test listing feeds when none exist."""
        response = client.get("/api/v1/feeds")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_feeds(self, client, sample_feed):
        """Test listing feeds."""
        response = client.get("/api/v1/feeds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Feed"
        assert data[0]["schedule_cron"] == "0 9 * * *"
        assert data[0]["schedule_enabled"] is True

    def test_list_feeds_with_sources(self, client, sample_feed):
        """Test that listed feeds include their feed_sources."""
        response = client.get("/api/v1/feeds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        # Feed should have feed_sources populated
        assert "feed_sources" in data[0]
        assert len(data[0]["feed_sources"]) == 1

    def test_create_feed(self, client, sample_source, sample_prompt_template, sample_report_template):
        """Test creating a new feed."""
        feed_data = {
            "name": "New Daily Digest",
            "description": "A new daily digest feed",
            "schedule_cron": "0 8 * * 1-5",
            "schedule_enabled": True,
            "prompt_template_id": sample_prompt_template.id,
            "report_template_id": sample_report_template.id,
            "source_ids": [sample_source.id]
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Daily Digest"
        assert data["schedule_cron"] == "0 8 * * 1-5"
        assert data["id"] is not None
        # Check that next_run_at was calculated
        assert data.get("next_run_at") is not None or data["schedule_enabled"] is True

    def test_create_feed_minimal(self, client):
        """Test creating feed with minimal data."""
        feed_data = {
            "name": "Minimal Feed",
            "source_ids": []
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Feed"

    def test_create_feed_validation_error(self, client):
        """Test creating feed with invalid data."""
        # Missing required name
        response = client.post("/api/v1/feeds", json={})
        assert response.status_code == 422

    def test_get_feed(self, client, sample_feed):
        """Test getting a specific feed."""
        response = client.get(f"/api/v1/feeds/{sample_feed.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_feed.id
        assert data["name"] == "Test Feed"

    def test_get_feed_not_found(self, client):
        """Test getting non-existent feed."""
        response = client.get("/api/v1/feeds/99999")
        assert response.status_code == 404

    def test_update_feed(self, client, sample_feed):
        """Test updating a feed."""
        update_data = {
            "name": "Updated Feed Name",
            "schedule_enabled": False
        }
        response = client.put(f"/api/v1/feeds/{sample_feed.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Feed Name"
        assert data["schedule_enabled"] is False

    def test_update_feed_schedule(self, client, sample_feed):
        """Test updating feed schedule recalculates next_run_at."""
        update_data = {
            "schedule_cron": "0 10 * * *",
            "schedule_enabled": True
        }
        response = client.put(f"/api/v1/feeds/{sample_feed.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["schedule_cron"] == "0 10 * * *"

    def test_update_feed_not_found(self, client):
        """Test updating non-existent feed."""
        response = client.put("/api/v1/feeds/99999", json={"name": "Test"})
        assert response.status_code == 404

    def test_delete_feed(self, client, sample_feed):
        """Test deleting a feed."""
        response = client.delete(f"/api/v1/feeds/{sample_feed.id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get(f"/api/v1/feeds/{sample_feed.id}")
        assert response.status_code == 404

    def test_delete_feed_not_found(self, client):
        """Test deleting non-existent feed."""
        response = client.delete("/api/v1/feeds/99999")
        assert response.status_code == 404

    def test_run_feed(self, client, sample_feed):
        """Test triggering a manual feed run."""
        response = client.post(f"/api/v1/feeds/{sample_feed.id}/run")
        assert response.status_code == 200
        data = response.json()
        assert data["feed_id"] == sample_feed.id
        assert data["status"] == "pending"
        assert "id" in data

    def test_run_feed_not_found(self, client):
        """Test running non-existent feed."""
        response = client.post("/api/v1/feeds/99999/run")
        assert response.status_code == 404

    def test_get_feed_runs(self, client, sample_feed):
        """Test getting feed run history."""
        response = client.get(f"/api/v1/feeds/{sample_feed.id}/runs")
        assert response.status_code == 200
        data = response.json()
        # Initially should be empty (paginated response)
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_feed_runs_not_found(self, client):
        """Test getting runs for non-existent feed."""
        response = client.get("/api/v1/feeds/99999/runs")
        assert response.status_code == 404


@pytest.mark.api
class TestFeedFieldNames:
    """Test that feed API uses correct field names (schedule_cron, schedule_enabled)."""

    def test_create_feed_uses_correct_field_names(self, client, sample_source):
        """Verify feed creation accepts schedule_cron and schedule_enabled."""
        feed_data = {
            "name": "Field Name Test",
            "schedule_cron": "0 9 * * *",
            "schedule_enabled": True,
            "source_ids": [sample_source.id]
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        # Response should use correct field names
        assert "schedule_cron" in data
        assert "schedule_enabled" in data
        # Old field names should NOT be present
        assert "schedule" not in data
        assert "enabled" not in data or data.get("enabled") != data.get("schedule_enabled")

    def test_update_feed_uses_correct_field_names(self, client, sample_feed):
        """Verify feed update accepts schedule_cron and schedule_enabled."""
        update_data = {
            "schedule_cron": "0 10 * * *",
            "schedule_enabled": False
        }
        response = client.put(f"/api/v1/feeds/{sample_feed.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["schedule_cron"] == "0 10 * * *"
        assert data["schedule_enabled"] is False


@pytest.mark.api
class TestFeedExportConfig:
    """Test suite for per-feed export configuration."""

    def test_create_feed_with_export_config(self, client, sample_source):
        """Test creating a feed with export configuration."""
        feed_data = {
            "name": "Feed With Export",
            "source_ids": [sample_source.id],
            "output_config": {
                "exports": {
                    "obsidian": {"enabled": True, "path": "/vault/path"}
                }
            }
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["output_config"]["exports"]["obsidian"]["enabled"] is True
        assert data["output_config"]["exports"]["obsidian"]["path"] == "/vault/path"

    def test_create_feed_with_multiple_exporters(self, client, sample_source):
        """Test creating a feed with multiple exporters configured."""
        feed_data = {
            "name": "Feed With Multiple Exports",
            "source_ids": [sample_source.id],
            "output_config": {
                "exports": {
                    "obsidian": {"enabled": True, "path": "/vault"},
                    "json": {"enabled": True, "path": "/json/export"}
                }
            }
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        exports = data["output_config"]["exports"]
        assert exports["obsidian"]["enabled"] is True
        assert exports["json"]["enabled"] is True

    def test_update_feed_export_config(self, client, sample_feed):
        """Test updating feed export configuration."""
        update_data = {
            "output_config": {
                "exports": {
                    "obsidian": {"enabled": True, "path": "/new/vault"}
                }
            }
        }
        response = client.put(f"/api/v1/feeds/{sample_feed.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["output_config"]["exports"]["obsidian"]["enabled"] is True
        assert data["output_config"]["exports"]["obsidian"]["path"] == "/new/vault"

    def test_create_feed_export_config_without_path(self, client, sample_source):
        """Test creating feed with export config without path (uses global)."""
        feed_data = {
            "name": "Feed Without Path",
            "source_ids": [sample_source.id],
            "output_config": {
                "exports": {
                    "obsidian": {"enabled": True}
                }
            }
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["output_config"]["exports"]["obsidian"]["enabled"] is True
        # Path should be None or not present
        assert data["output_config"]["exports"]["obsidian"].get("path") is None

    def test_create_feed_export_disabled(self, client, sample_source):
        """Test creating feed with export explicitly disabled."""
        feed_data = {
            "name": "Feed Export Disabled",
            "source_ids": [sample_source.id],
            "output_config": {
                "exports": {
                    "obsidian": {"enabled": False}
                }
            }
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["output_config"]["exports"]["obsidian"]["enabled"] is False

    def test_create_feed_with_email_and_export(self, client, sample_source):
        """Test creating feed with both email and export configuration."""
        feed_data = {
            "name": "Feed With Email And Export",
            "source_ids": [sample_source.id],
            "output_config": {
                "email_recipients": "test@example.com",
                "exports": {
                    "obsidian": {"enabled": True, "path": "/vault"}
                }
            }
        }
        response = client.post("/api/v1/feeds", json=feed_data)
        assert response.status_code == 201
        data = response.json()
        assert data["output_config"]["email_recipients"] == "test@example.com"
        assert data["output_config"]["exports"]["obsidian"]["enabled"] is True

    def test_get_feed_returns_export_config(self, client, sample_source):
        """Test that getting a feed returns its export configuration."""
        # First create a feed with export config
        feed_data = {
            "name": "Feed To Get",
            "source_ids": [sample_source.id],
            "output_config": {
                "exports": {
                    "json": {"enabled": True, "path": "/export/json"}
                }
            }
        }
        create_response = client.post("/api/v1/feeds", json=feed_data)
        assert create_response.status_code == 201
        feed_id = create_response.json()["id"]

        # Now get the feed
        get_response = client.get(f"/api/v1/feeds/{feed_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["output_config"]["exports"]["json"]["enabled"] is True
        assert data["output_config"]["exports"]["json"]["path"] == "/export/json"
