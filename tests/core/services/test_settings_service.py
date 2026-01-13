"""Tests for SettingsService."""
import os
import pytest
from unittest.mock import patch

from reconly_core.services.settings_service import SettingsService
from reconly_core.services.settings_registry import SETTINGS_REGISTRY


class TestSettingsServiceGet:
    """Tests for SettingsService.get() method."""

    def test_get_returns_default_when_no_override(self, db_session):
        """Get should return default value when no DB or env override."""
        service = SettingsService(db_session)

        # Clear any env var that might interfere
        with patch.dict(os.environ, {}, clear=True):
            value = service.get("llm.default_provider")
            assert value == "ollama"  # Default from registry

    def test_get_returns_env_value_over_default(self, db_session):
        """Get should return env value over default."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"DEFAULT_PROVIDER": "anthropic"}):
            value = service.get("llm.default_provider")
            assert value == "anthropic"

    def test_get_returns_db_value_over_env(self, db_session):
        """Get should return DB value over env value."""
        service = SettingsService(db_session)

        # Set in DB
        service.set("llm.default_provider", "openai")

        # Set different value in env
        with patch.dict(os.environ, {"DEFAULT_PROVIDER": "anthropic"}):
            value = service.get("llm.default_provider")
            assert value == "openai"  # DB wins

    def test_get_unknown_setting_raises_keyerror(self, db_session):
        """Get should raise KeyError for unknown settings."""
        service = SettingsService(db_session)

        with pytest.raises(KeyError, match="Unknown setting"):
            service.get("unknown.setting")

    def test_get_converts_int_from_env(self, db_session):
        """Get should convert int types from env strings."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"SMTP_PORT": "465"}):
            value = service.get("email.smtp_port")
            assert value == 465
            assert isinstance(value, int)

    def test_get_converts_bool_from_env(self, db_session):
        """Get should convert bool types from env strings."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"EXPORT_INCLUDE_METADATA": "false"}):
            value = service.get("export.include_metadata")
            assert value is False


class TestSettingsServiceSet:
    """Tests for SettingsService.set() method."""

    def test_set_persists_value(self, db_session):
        """Set should persist value to database."""
        service = SettingsService(db_session)

        service.set("llm.default_provider", "anthropic")
        value = service.get("llm.default_provider")
        assert value == "anthropic"

    def test_set_updates_existing_value(self, db_session):
        """Set should update existing value."""
        service = SettingsService(db_session)

        service.set("llm.default_provider", "openai")
        service.set("llm.default_provider", "anthropic")
        value = service.get("llm.default_provider")
        assert value == "anthropic"

    def test_set_non_editable_raises_error(self, db_session):
        """Set should raise ValueError for non-editable settings."""
        service = SettingsService(db_session)

        # provider.anthropic.api_key uses new unified pattern with editable=False
        with pytest.raises(ValueError, match="not editable"):
            service.set("provider.anthropic.api_key", "sk-test")

    def test_set_unknown_setting_raises_keyerror(self, db_session):
        """Set should raise KeyError for unknown settings."""
        service = SettingsService(db_session)

        with pytest.raises(KeyError, match="Unknown setting"):
            service.set("unknown.setting", "value")

    def test_set_list_value(self, db_session):
        """Set should handle list values."""
        service = SettingsService(db_session)

        chain = ["anthropic", "openai", "ollama"]
        service.set("llm.fallback_chain", chain)
        value = service.get("llm.fallback_chain")
        assert value == chain


class TestSettingsServiceReset:
    """Tests for SettingsService.reset() method."""

    def test_reset_removes_db_value(self, db_session):
        """Reset should remove DB value."""
        service = SettingsService(db_session)

        service.set("llm.default_provider", "anthropic")
        result = service.reset("llm.default_provider")
        assert result is True

        # Should fall back to default
        with patch.dict(os.environ, {}, clear=True):
            value = service.get("llm.default_provider")
            assert value == "ollama"

    def test_reset_returns_false_when_no_db_value(self, db_session):
        """Reset should return False when no DB value exists."""
        service = SettingsService(db_session)

        result = service.reset("llm.default_provider")
        assert result is False

    def test_reset_falls_back_to_env(self, db_session):
        """Reset should fall back to env value after removing DB value."""
        service = SettingsService(db_session)

        service.set("llm.default_provider", "openai")

        with patch.dict(os.environ, {"DEFAULT_PROVIDER": "anthropic"}):
            service.reset("llm.default_provider")
            value = service.get("llm.default_provider")
            assert value == "anthropic"


class TestSettingsServiceGetWithSource:
    """Tests for SettingsService.get_with_source() method."""

    def test_get_with_source_default(self, db_session):
        """Get with source should indicate default source."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {}, clear=True):
            result = service.get_with_source("llm.default_provider")
            assert result["value"] == "ollama"
            assert result["source"] == "default"
            assert result["editable"] is True

    def test_get_with_source_environment(self, db_session):
        """Get with source should indicate environment source."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"DEFAULT_PROVIDER": "anthropic"}):
            result = service.get_with_source("llm.default_provider")
            assert result["value"] == "anthropic"
            assert result["source"] == "environment"

    def test_get_with_source_database(self, db_session):
        """Get with source should indicate database source."""
        service = SettingsService(db_session)

        service.set("llm.default_provider", "openai")
        result = service.get_with_source("llm.default_provider")
        assert result["value"] == "openai"
        assert result["source"] == "database"

    def test_get_with_source_masks_secrets(self, db_session):
        """Get with source should mask secret values."""
        service = SettingsService(db_session)

        # provider.anthropic.api_key uses new unified pattern
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api-12345678"}):
            result = service.get_with_source("provider.anthropic.api_key")
            assert result["value"] == "sk-a...5678"
            assert result["editable"] is False

    def test_get_with_source_non_editable(self, db_session):
        """Get with source should indicate non-editable settings."""
        service = SettingsService(db_session)

        # provider.anthropic.api_key uses new unified pattern
        result = service.get_with_source("provider.anthropic.api_key")
        assert result["editable"] is False


class TestSettingsServiceGetAll:
    """Tests for SettingsService.get_all() method."""

    def test_get_all_returns_all_settings(self, db_session):
        """Get all should return all registered settings."""
        service = SettingsService(db_session)

        result = service.get_all()
        assert len(result) == len(SETTINGS_REGISTRY)
        assert "llm.default_provider" in result
        assert "email.smtp_host" in result

    def test_get_all_filtered_by_category(self, db_session):
        """Get all should filter by category."""
        service = SettingsService(db_session)

        result = service.get_all("provider")
        assert "llm.default_provider" in result
        assert "email.smtp_host" not in result

    def test_get_by_category_organizes_by_category(self, db_session):
        """Get by category should organize settings by category."""
        service = SettingsService(db_session)

        result = service.get_by_category()
        assert "provider" in result
        assert "email" in result
        assert "export" in result
        assert "llm.default_provider" in result["provider"]
