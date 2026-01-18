"""Tests for SettingsService."""
import os
import pytest
from unittest.mock import patch

from reconly_core.services.settings_service import SettingsService, migrate_provider_settings
from reconly_core.services.settings_registry import SETTINGS_REGISTRY
from reconly_core.database.models import AppSetting


class TestSettingsServiceGet:
    """Tests for SettingsService.get() method."""

    def test_get_returns_default_when_no_override(self, db_session):
        """Get should return default value when no DB or env override."""
        service = SettingsService(db_session)

        # Clear any env var that might interfere
        with patch.dict(os.environ, {}, clear=True):
            value = service.get("email.smtp_host")
            assert value == "localhost"  # Default from registry

    def test_get_returns_env_value_over_default(self, db_session):
        """Get should return env value over default."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"SMTP_HOST": "mail.example.com"}):
            value = service.get("email.smtp_host")
            assert value == "mail.example.com"

    def test_get_returns_db_value_over_env(self, db_session):
        """Get should return DB value over env value."""
        service = SettingsService(db_session)

        # Set in DB
        service.set("email.smtp_host", "db.example.com")

        # Set different value in env
        with patch.dict(os.environ, {"SMTP_HOST": "env.example.com"}):
            value = service.get("email.smtp_host")
            assert value == "db.example.com"  # DB wins

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

        service.set("email.smtp_host", "mail.example.com")
        value = service.get("email.smtp_host")
        assert value == "mail.example.com"

    def test_set_updates_existing_value(self, db_session):
        """Set should update existing value."""
        service = SettingsService(db_session)

        service.set("email.smtp_host", "first.example.com")
        service.set("email.smtp_host", "second.example.com")
        value = service.get("email.smtp_host")
        assert value == "second.example.com"

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

        service.set("email.smtp_host", "mail.example.com")
        result = service.reset("email.smtp_host")
        assert result is True

        # Should fall back to default
        with patch.dict(os.environ, {}, clear=True):
            value = service.get("email.smtp_host")
            assert value == "localhost"

    def test_reset_returns_false_when_no_db_value(self, db_session):
        """Reset should return False when no DB value exists."""
        service = SettingsService(db_session)

        result = service.reset("email.smtp_host")
        assert result is False

    def test_reset_falls_back_to_env(self, db_session):
        """Reset should fall back to env value after removing DB value."""
        service = SettingsService(db_session)

        service.set("email.smtp_host", "db.example.com")

        with patch.dict(os.environ, {"SMTP_HOST": "env.example.com"}):
            service.reset("email.smtp_host")
            value = service.get("email.smtp_host")
            assert value == "env.example.com"


class TestSettingsServiceGetWithSource:
    """Tests for SettingsService.get_with_source() method."""

    def test_get_with_source_default(self, db_session):
        """Get with source should indicate default source."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {}, clear=True):
            result = service.get_with_source("email.smtp_host")
            assert result["value"] == "localhost"
            assert result["source"] == "default"
            assert result["editable"] is True

    def test_get_with_source_environment(self, db_session):
        """Get with source should indicate environment source."""
        service = SettingsService(db_session)

        with patch.dict(os.environ, {"SMTP_HOST": "env.example.com"}):
            result = service.get_with_source("email.smtp_host")
            assert result["value"] == "env.example.com"
            assert result["source"] == "environment"

    def test_get_with_source_database(self, db_session):
        """Get with source should indicate database source."""
        service = SettingsService(db_session)

        service.set("email.smtp_host", "db.example.com")
        result = service.get_with_source("email.smtp_host")
        assert result["value"] == "db.example.com"
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
        assert "llm.fallback_chain" in result
        assert "email.smtp_host" in result

    def test_get_all_filtered_by_category(self, db_session):
        """Get all should filter by category."""
        service = SettingsService(db_session)

        result = service.get_all("provider")
        assert "llm.fallback_chain" in result
        assert "email.smtp_host" not in result

    def test_get_by_category_organizes_by_category(self, db_session):
        """Get by category should organize settings by category."""
        service = SettingsService(db_session)

        result = service.get_by_category()
        assert "provider" in result
        assert "email" in result
        assert "export" in result
        assert "llm.fallback_chain" in result["provider"]


class TestSettingsServiceRawMethods:
    """Tests for raw methods that bypass registry check."""

    def test_get_raw_returns_db_value(self, db_session):
        """get_raw should return value directly from database."""
        service = SettingsService(db_session)

        # Insert directly into DB (bypasses registry)
        service.set_raw("test.unregistered.key", "test_value")
        value = service.get_raw("test.unregistered.key")
        assert value == "test_value"

    def test_get_raw_returns_none_for_missing(self, db_session):
        """get_raw should return None when key not in database."""
        service = SettingsService(db_session)

        value = service.get_raw("nonexistent.key")
        assert value is None

    def test_set_raw_creates_new_setting(self, db_session):
        """set_raw should create new setting in database."""
        service = SettingsService(db_session)

        result = service.set_raw("test.new.key", {"nested": "value"})
        assert result is True

        value = service.get_raw("test.new.key")
        assert value == {"nested": "value"}

    def test_set_raw_updates_existing(self, db_session):
        """set_raw should update existing setting."""
        service = SettingsService(db_session)

        service.set_raw("test.update.key", "first")
        service.set_raw("test.update.key", "second")
        value = service.get_raw("test.update.key")
        assert value == "second"

    def test_delete_removes_setting(self, db_session):
        """delete should remove setting from database."""
        service = SettingsService(db_session)

        service.set_raw("test.delete.key", "value")
        result = service.delete("test.delete.key")
        assert result is True

        value = service.get_raw("test.delete.key")
        assert value is None

    def test_delete_returns_false_for_missing(self, db_session):
        """delete should return False when key not in database."""
        service = SettingsService(db_session)

        result = service.delete("nonexistent.key")
        assert result is False


class TestMigrateProviderSettings:
    """Tests for migrate_provider_settings function."""

    def test_migration_with_no_old_settings(self, db_session):
        """Migration should be no-op when no old settings exist."""
        result = migrate_provider_settings(db_session)

        assert result["migrated_provider"] is None
        assert result["migrated_model"] is None
        assert result["chain"] is None

    def test_migration_moves_provider_to_first_in_chain(self, db_session):
        """Migration should move old default_provider to first position in chain."""
        service = SettingsService(db_session)

        # Set up old setting
        service.set_raw("llm.default_provider", "anthropic")

        # Run migration
        result = migrate_provider_settings(db_session)

        assert result["migrated_provider"] == "anthropic"
        assert result["chain"][0] == "anthropic"

        # Old setting should be deleted
        assert service.get_raw("llm.default_provider") is None

    def test_migration_moves_model_to_provider_specific_key(self, db_session):
        """Migration should move old default_model to provider.{name}.model."""
        service = SettingsService(db_session)

        # Set up old settings
        service.set_raw("llm.default_provider", "openai")
        service.set_raw("llm.default_model", "gpt-4o")

        # Run migration
        result = migrate_provider_settings(db_session)

        assert result["migrated_provider"] == "openai"
        assert result["migrated_model"] == "gpt-4o"

        # Model should be in provider-specific key
        model = service.get_raw("provider.openai.model")
        assert model == "gpt-4o"

        # Old settings should be deleted
        assert service.get_raw("llm.default_provider") is None
        assert service.get_raw("llm.default_model") is None

    def test_migration_does_not_overwrite_existing_model(self, db_session):
        """Migration should not overwrite existing provider-specific model."""
        service = SettingsService(db_session)

        # Set up old settings and existing provider model
        service.set_raw("llm.default_provider", "openai")
        service.set_raw("llm.default_model", "gpt-4")  # Old model
        service.set_raw("provider.openai.model", "gpt-4o")  # Existing specific model

        # Run migration
        result = migrate_provider_settings(db_session)

        # Should not migrate model since there's already a provider-specific one
        assert result["migrated_model"] is None

        # Existing model should be preserved
        model = service.get_raw("provider.openai.model")
        assert model == "gpt-4o"

    def test_migration_is_idempotent(self, db_session):
        """Migration should be safe to run multiple times."""
        service = SettingsService(db_session)

        # Set up old settings
        service.set_raw("llm.default_provider", "ollama")
        service.set_raw("llm.default_model", "llama3.2")

        # Run migration twice
        result1 = migrate_provider_settings(db_session)
        result2 = migrate_provider_settings(db_session)

        # First run should migrate
        assert result1["migrated_provider"] == "ollama"
        assert result1["migrated_model"] == "llama3.2"

        # Second run should be no-op (old settings are gone)
        assert result2["migrated_provider"] is None
        assert result2["migrated_model"] is None

        # Final state should be correct
        chain = service.get("llm.fallback_chain")
        assert chain[0] == "ollama"

        model = service.get_raw("provider.ollama.model")
        assert model == "llama3.2"

    def test_migration_handles_provider_already_first_in_chain(self, db_session):
        """Migration should handle when provider is already first in chain."""
        service = SettingsService(db_session)

        # Set up old setting with provider that's already first in default chain
        service.set_raw("llm.default_provider", "ollama")

        # Run migration
        result = migrate_provider_settings(db_session)

        # Should still record migration
        assert result["migrated_provider"] == "ollama"

        # Chain should still have ollama first (no duplicates)
        chain = service.get("llm.fallback_chain")
        assert chain[0] == "ollama"
        assert chain.count("ollama") == 1  # No duplicates

    def test_migration_preserves_fallback_chain_order(self, db_session):
        """Migration should preserve other providers' order in chain."""
        service = SettingsService(db_session)

        # Set custom fallback chain first
        service.set("llm.fallback_chain", ["huggingface", "openai", "anthropic", "ollama"])

        # Set old default provider
        service.set_raw("llm.default_provider", "anthropic")

        # Run migration
        result = migrate_provider_settings(db_session)

        # Anthropic should be moved to first
        chain = service.get("llm.fallback_chain")
        assert chain[0] == "anthropic"

        # Other providers should maintain relative order
        assert "huggingface" in chain
        assert "openai" in chain
        assert "ollama" in chain
