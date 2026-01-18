"""Settings service for runtime configuration management.

Implements priority chain: DB value > env variable > code default.
Provides source indicators for UI display.
"""
import json
import os
from typing import Any

from sqlalchemy.orm import Session

from reconly_core.database.models import AppSetting
from reconly_core.services.settings_registry import (
    SETTINGS_REGISTRY,
    get_settings_by_category,
    get_all_categories,
)


class SettingsService:
    """Service for managing application settings with DB persistence."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def get(self, key: str) -> Any:
        """
        Get setting value using priority chain: DB > env > default.

        Args:
            key: Setting key (e.g., "llm.default_provider")

        Returns:
            The effective value for the setting

        Raises:
            KeyError: If setting key is not in registry
        """
        if key not in SETTINGS_REGISTRY:
            raise KeyError(f"Unknown setting: {key}")

        setting_def = SETTINGS_REGISTRY[key]

        # Priority 1: Database value
        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            return self._decode_value(db_setting.value, setting_def.type)

        # Priority 2: Environment variable
        if setting_def.env_var:
            env_value = os.environ.get(setting_def.env_var)
            if env_value is not None:
                return self._convert_type(env_value, setting_def.type)

        # Priority 3: Default value
        return setting_def.default

    def get_with_source(self, key: str) -> dict[str, Any]:
        """
        Get setting value with source indicator.

        Args:
            key: Setting key

        Returns:
            Dict with value, source, and editable fields
        """
        if key not in SETTINGS_REGISTRY:
            raise KeyError(f"Unknown setting: {key}")

        setting_def = SETTINGS_REGISTRY[key]
        value = None
        source = "default"

        # Check database first
        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            value = self._decode_value(db_setting.value, setting_def.type)
            source = "database"
        # Check environment variable
        elif setting_def.env_var:
            env_value = os.environ.get(setting_def.env_var)
            if env_value is not None:
                value = self._convert_type(env_value, setting_def.type)
                source = "environment"

        # Use default if no override
        if value is None:
            value = setting_def.default

        # Mask secrets
        display_value = self._mask_secret(value) if setting_def.secret else value

        return {
            "value": display_value,
            "source": source,
            "editable": setting_def.editable,
        }

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value in the database.

        Args:
            key: Setting key
            value: New value

        Returns:
            True if successful

        Raises:
            KeyError: If setting key is not in registry
            ValueError: If setting is not editable
        """
        if key not in SETTINGS_REGISTRY:
            raise KeyError(f"Unknown setting: {key}")

        setting_def = SETTINGS_REGISTRY[key]
        if not setting_def.editable:
            raise ValueError(f"Setting '{key}' is not editable (env-only)")

        # Validate type
        if not self._validate_type(value, setting_def.type):
            raise ValueError(f"Invalid type for '{key}': expected {setting_def.type.__name__}")

        # Encode value as JSON
        encoded_value = self._encode_value(value)

        # Upsert into database
        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            db_setting.value = encoded_value
        else:
            db_setting = AppSetting(key=key, value=encoded_value)
            self.db.add(db_setting)

        self.db.commit()
        return True

    def reset(self, key: str) -> bool:
        """
        Remove database override, falling back to env or default.

        Args:
            key: Setting key

        Returns:
            True if a database value was removed, False if none existed
        """
        if key not in SETTINGS_REGISTRY:
            raise KeyError(f"Unknown setting: {key}")

        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            self.db.delete(db_setting)
            self.db.commit()
            return True
        return False

    def get_all(self, category: str | None = None) -> dict[str, dict[str, Any]]:
        """
        Get all settings with source indicators, optionally filtered by category.

        Args:
            category: Optional category filter (provider, email, export)

        Returns:
            Dict of setting keys to {value, source, editable} dicts
        """
        if category:
            settings = get_settings_by_category(category)
        else:
            settings = SETTINGS_REGISTRY

        result = {}
        for key in settings:
            result[key] = self.get_with_source(key)
        return result

    def get_by_category(self) -> dict[str, dict[str, dict[str, Any]]]:
        """
        Get all settings organized by category.

        Returns:
            Dict of category -> {setting_key -> {value, source, editable}}
        """
        result = {}
        for category in get_all_categories():
            result[category] = self.get_all(category)
        return result

    def _encode_value(self, value: Any) -> str:
        """Encode value as JSON string for storage."""
        return json.dumps(value)

    def _decode_value(self, encoded: str, expected_type: type) -> Any:
        """Decode JSON string to value."""
        try:
            value = json.loads(encoded)
            return value
        except json.JSONDecodeError:
            # Return as-is for non-JSON strings
            return encoded

    def _convert_type(self, value: str, expected_type: type) -> Any:
        """Convert string value from env var to expected type."""
        if expected_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif expected_type == int:
            return int(value)
        elif expected_type == float:
            return float(value)
        elif expected_type == list:
            # Try JSON parse for lists
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.split(",")
        return value

    def _validate_type(self, value: Any, expected_type: type) -> bool:
        """Validate value matches expected type."""
        if expected_type == list:
            return isinstance(value, (list, tuple))
        if value is None:
            return True  # None is always valid
        return isinstance(value, expected_type)

    def _mask_secret(self, value: Any) -> str:
        """Mask a secret value for display."""
        if value is None:
            return None
        s = str(value)
        if len(s) <= 8:
            return "••••••••"
        return f"{s[:4]}...{s[-4:]}"

    def delete(self, key: str) -> bool:
        """
        Delete a setting from the database by key.

        Unlike reset(), this method doesn't require the key to be in the registry.
        Used for migration cleanup of deprecated settings.

        Args:
            key: Setting key to delete

        Returns:
            True if a database value was removed, False if none existed
        """
        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            self.db.delete(db_setting)
            self.db.commit()
            return True
        return False

    def get_raw(self, key: str) -> Any | None:
        """
        Get raw setting value from database only, bypassing registry check.

        Used for migration to read deprecated settings that may not be in registry.

        Args:
            key: Setting key

        Returns:
            The decoded value from database, or None if not found
        """
        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            try:
                return json.loads(db_setting.value)
            except json.JSONDecodeError:
                return db_setting.value
        return None

    def set_raw(self, key: str, value: Any) -> bool:
        """
        Set a setting value in the database, bypassing registry check.

        Used for migration to write to keys that may not be in registry yet.

        Args:
            key: Setting key
            value: New value

        Returns:
            True if successful
        """
        encoded_value = self._encode_value(value)

        db_setting = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        if db_setting:
            db_setting.value = encoded_value
        else:
            db_setting = AppSetting(key=key, value=encoded_value)
            self.db.add(db_setting)

        self.db.commit()
        return True


def migrate_provider_settings(db: Session) -> dict[str, Any]:
    """
    Migrate old provider settings to new format.

    This is a one-time migration that:
    1. Moves llm.default_provider to position 0 in llm.fallback_chain
    2. Moves llm.default_model to llm.{provider}.model
    3. Deletes the old keys from the database

    This function is idempotent - safe to run multiple times.

    Args:
        db: Database session

    Returns:
        Dict with migration results:
        - migrated_provider: The old default provider (if any)
        - migrated_model: The old default model (if any)
        - chain: The updated fallback chain
    """
    import structlog
    logger = structlog.get_logger(__name__)

    service = SettingsService(db)
    result = {
        "migrated_provider": None,
        "migrated_model": None,
        "chain": None,
    }

    # Get old settings (directly from DB to avoid registry check)
    old_provider = service.get_raw("llm.default_provider")
    old_model = service.get_raw("llm.default_model")

    # Get current fallback chain from registry-aware getter (has default)
    try:
        chain = service.get("llm.fallback_chain")
    except KeyError:
        # If somehow not in registry, use default
        chain = ["ollama", "huggingface", "openai", "anthropic"]

    if chain is None:
        chain = ["ollama", "huggingface", "openai", "anthropic"]

    # Ensure chain is a list
    if not isinstance(chain, list):
        chain = ["ollama", "huggingface", "openai", "anthropic"]

    # Migration 1: Ensure old default provider is first in chain
    if old_provider:
        result["migrated_provider"] = old_provider
        if old_provider in chain:
            chain.remove(old_provider)
        chain.insert(0, old_provider)
        logger.info(
            "Migrated default provider to chain position 0",
            old_provider=old_provider,
        )

    # Migration 2: Move old default model to provider-specific key
    if old_provider and old_model:
        provider_model_key = f"provider.{old_provider}.model"
        # Only migrate if there's no existing provider-specific model setting
        existing_model = service.get_raw(provider_model_key)
        if existing_model is None:
            service.set_raw(provider_model_key, old_model)
            result["migrated_model"] = old_model
            logger.info(
                "Migrated default model to provider-specific setting",
                provider=old_provider,
                model=old_model,
                new_key=provider_model_key,
            )

    # Save updated chain if we made changes
    if old_provider:
        service.set("llm.fallback_chain", chain)
        result["chain"] = chain

    # Cleanup: Delete old keys from database
    if service.delete("llm.default_provider"):
        logger.info("Deleted deprecated setting llm.default_provider")
    if service.delete("llm.default_model"):
        logger.info("Deleted deprecated setting llm.default_model")

    return result
