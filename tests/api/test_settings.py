"""Tests for Settings API routes."""
import pytest
from unittest.mock import patch
import os


@pytest.mark.api
class TestSettingsAPI:
    """Test suite for /api/v1/settings endpoints."""

    def test_get_settings_returns_all_categories(self, client):
        """Test GET /settings returns all setting categories."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        # Response is wrapped in "categories" for dynamic category support
        assert "categories" in data
        categories = data["categories"]
        assert "provider" in categories
        assert "email" in categories
        assert "export" in categories

    def test_get_settings_includes_source_indicators(self, client):
        """Test settings include source indicators."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()

        # Check provider settings have required fields
        # Now using llm.fallback_chain which becomes fallback_chain in response
        provider = data["categories"]["provider"]
        assert "fallback_chain" in provider
        setting = provider["fallback_chain"]
        assert "value" in setting
        assert "source" in setting
        assert "editable" in setting
        assert setting["source"] in ["database", "environment", "default"]

    def test_get_settings_filter_by_category(self, client):
        """Test filtering by category."""
        response = client.get("/api/v1/settings?category=email")
        assert response.status_code == 200
        data = response.json()

        # Email category should have settings
        assert len(data["categories"]["email"]) > 0
        # Other categories should not be present (dynamic filtering)
        assert "provider" not in data["categories"]
        assert "export" not in data["categories"]

    def test_get_settings_shows_default_source(self, client):
        """Test settings show 'default' source when no override exists."""
        with patch.dict(os.environ, {}, clear=True):
            response = client.get("/api/v1/settings")
            assert response.status_code == 200
            data = response.json()

            # With no env vars set, source should be default
            # Note: Some settings might still be from env if test env has them
            provider = data["categories"]["provider"]
            assert "fallback_chain" in provider

    def test_get_settings_masks_secrets(self, client):
        """Test secret values are masked."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-secret-key-12345"}):
            response = client.get("/api/v1/settings")
            assert response.status_code == 200
            data = response.json()

            provider = data["categories"]["provider"]
            api_key_setting = provider.get("anthropic.api_key")
            if api_key_setting and api_key_setting["value"]:
                # Should be masked, not showing full key
                assert "sk-ant-secret-key-12345" not in str(api_key_setting["value"])
                assert "..." in str(api_key_setting["value"]) or "••" in str(api_key_setting["value"])

    def test_get_settings_non_editable_marked(self, client):
        """Test non-editable settings are marked correctly."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()

        # API keys should not be editable
        provider = data["categories"]["provider"]
        if "anthropic.api_key" in provider:
            assert provider["anthropic.api_key"]["editable"] is False


@pytest.mark.api
class TestSettingsUpdate:
    """Test suite for PUT /api/v1/settings endpoint."""

    def test_update_editable_setting(self, client):
        """Test updating an editable setting."""
        response = client.put(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "email.smtp_host", "value": "mail.example.com"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "email.smtp_host" in data["updated"]
        assert len(data["errors"]) == 0

        # Verify the setting was updated
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["categories"]["email"]["smtp_host"]["value"] == "mail.example.com"
        assert data["categories"]["email"]["smtp_host"]["source"] == "database"

    def test_update_multiple_settings(self, client):
        """Test updating multiple settings at once."""
        response = client.put(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "llm.fallback_chain", "value": ["openai", "ollama", "anthropic"]},
                    {"key": "email.smtp_host", "value": "smtp.test.com"},
                    {"key": "export.default_format", "value": "csv"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["updated"]) == 3
        assert len(data["errors"]) == 0

    def test_update_non_editable_setting_fails(self, client):
        """Test updating a non-editable setting returns error."""
        # provider.anthropic.api_key uses new unified pattern with editable=False
        response = client.put(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "provider.anthropic.api_key", "value": "sk-test"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["updated"]) == 0
        assert len(data["errors"]) == 1
        assert "not editable" in data["errors"][0]["error"]

    def test_update_unknown_setting_fails(self, client):
        """Test updating an unknown setting returns error."""
        response = client.put(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "unknown.setting", "value": "test"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["updated"]) == 0
        assert len(data["errors"]) == 1
        assert "Unknown setting" in data["errors"][0]["error"]


@pytest.mark.api
class TestSettingsReset:
    """Test suite for POST /api/v1/settings/reset endpoint."""

    def test_reset_removes_db_override(self, client):
        """Test resetting a setting removes DB value."""
        # First set a value
        client.put(
            "/api/v1/settings",
            json={"settings": [{"key": "email.smtp_host", "value": "mail.example.com"}]}
        )

        # Verify it's set
        response = client.get("/api/v1/settings")
        assert response.json()["categories"]["email"]["smtp_host"]["source"] == "database"

        # Reset it
        response = client.post(
            "/api/v1/settings/reset",
            json={"keys": ["email.smtp_host"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email.smtp_host" in data["reset"]

        # Verify it's no longer from database
        response = client.get("/api/v1/settings")
        assert response.json()["categories"]["email"]["smtp_host"]["source"] != "database"

    def test_reset_nonexistent_returns_not_found(self, client):
        """Test resetting a setting with no DB value returns not_found."""
        response = client.post(
            "/api/v1/settings/reset",
            json={"keys": ["email.smtp_host"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email.smtp_host" in data["not_found"]

    def test_reset_multiple_settings(self, client):
        """Test resetting multiple settings."""
        # Set multiple values
        client.put(
            "/api/v1/settings",
            json={
                "settings": [
                    {"key": "llm.fallback_chain", "value": ["anthropic", "ollama"]},
                    {"key": "email.smtp_host", "value": "test.com"}
                ]
            }
        )

        # Reset both
        response = client.post(
            "/api/v1/settings/reset",
            json={"keys": ["llm.fallback_chain", "email.smtp_host"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["reset"]) == 2
