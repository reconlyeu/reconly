"""Settings integration for extensions.

This module provides helpers for managing extension activation and configuration
using the SettingsService infrastructure.
"""
from typing import Any, Dict, Optional, TYPE_CHECKING

from reconly_core.extensions.types import ExtensionType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_extension_settings_prefix(ext_type: ExtensionType, name: str) -> str:
    """Get the settings key prefix for an extension.

    Uses the same key pattern as built-in components so that extension
    settings are compatible with existing UI and API patterns:
    - Exporters: export.{name}.*
    - Fetchers: fetch.{name}.*
    - Providers: provider.{name}.*

    Args:
        ext_type: Type of extension
        name: Extension name (registry name)

    Returns:
        Settings key prefix like "export.notion" for exporters
    """
    # Map extension types to their settings prefix patterns
    # These must match the patterns used by built-in components
    prefix_map = {
        ExtensionType.EXPORTER: "export",
        ExtensionType.FETCHER: "fetch",
        ExtensionType.PROVIDER: "provider",
    }
    prefix = prefix_map.get(ext_type, f"extension.{ext_type.value}")
    return f"{prefix}.{name}"


def get_extension_enabled_key(ext_type: ExtensionType, name: str) -> str:
    """Get the settings key for extension enabled state.

    Args:
        ext_type: Type of extension
        name: Extension name

    Returns:
        Settings key like "export.notion.enabled" for exporters
    """
    return f"{get_extension_settings_prefix(ext_type, name)}.enabled"


def is_extension_enabled(
    ext_type: ExtensionType,
    name: str,
    db: "Session"
) -> bool:
    """Check if an extension is enabled.

    Extensions are enabled by default if they have no required configuration.
    Extensions with required config are disabled until configured and enabled.

    Args:
        ext_type: Type of extension
        name: Extension name
        db: Database session

    Returns:
        True if extension is enabled
    """
    from reconly_core.services.settings_service import SettingsService
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY

    settings_service = SettingsService(db)
    enabled_key = get_extension_enabled_key(ext_type, name)

    # Check if setting exists in registry
    if enabled_key in SETTINGS_REGISTRY:
        return settings_service.get(enabled_key)

    # Default: enabled if no explicit setting
    # (extensions without required config auto-enable)
    return True


def is_extension_configured(
    ext_type: ExtensionType,
    name: str,
    db: "Session",
    required_fields: Optional[list[str]] = None
) -> bool:
    """Check if all required config fields for an extension have values.

    Args:
        ext_type: Type of extension
        name: Extension name
        db: Database session
        required_fields: List of required field keys (without prefix)

    Returns:
        True if all required fields are configured
    """
    if not required_fields:
        return True

    from reconly_core.services.settings_service import SettingsService
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY

    settings_service = SettingsService(db)
    prefix = get_extension_settings_prefix(ext_type, name)

    for field in required_fields:
        setting_key = f"{prefix}.{field}"
        if setting_key not in SETTINGS_REGISTRY:
            return False
        value = settings_service.get(setting_key)
        if value is None or value == "":
            return False

    return True


def can_enable_extension(
    ext_type: ExtensionType,
    name: str,
    db: "Session",
    required_fields: Optional[list[str]] = None
) -> bool:
    """Check if an extension can be enabled.

    An extension can be enabled if it has no required config,
    or all required config fields are set.

    Args:
        ext_type: Type of extension
        name: Extension name
        db: Database session
        required_fields: List of required field keys

    Returns:
        True if extension can be enabled
    """
    if not required_fields:
        return True
    return is_extension_configured(ext_type, name, db, required_fields)


def set_extension_enabled(
    ext_type: ExtensionType,
    name: str,
    enabled: bool,
    db: "Session"
) -> bool:
    """Set the enabled state for an extension.

    Note: This does not validate that required fields are configured.
    Call can_enable_extension() first if validation is needed.

    Args:
        ext_type: Type of extension
        name: Extension name
        enabled: Whether to enable or disable
        db: Database session

    Returns:
        True if successful

    Raises:
        KeyError: If the setting key is not in registry
        ValueError: If the setting is not editable
    """
    from reconly_core.services.settings_service import SettingsService
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY

    settings_service = SettingsService(db)
    enabled_key = get_extension_enabled_key(ext_type, name)

    if enabled_key not in SETTINGS_REGISTRY:
        raise KeyError(f"Extension enabled setting not registered: {enabled_key}")

    return settings_service.set(enabled_key, enabled)


def get_extension_activation_state(
    ext_type: ExtensionType,
    name: str,
    db: "Session",
    required_fields: Optional[list[str]] = None
) -> Dict[str, Any]:
    """Get the complete activation state for an extension.

    Args:
        ext_type: Type of extension
        name: Extension name
        db: Database session
        required_fields: List of required field keys

    Returns:
        Dict with enabled, is_configured, can_enable keys
    """
    enabled = is_extension_enabled(ext_type, name, db)
    is_configured = is_extension_configured(ext_type, name, db, required_fields)
    can_enable = can_enable_extension(ext_type, name, db, required_fields)

    return {
        "enabled": enabled,
        "is_configured": is_configured,
        "can_enable": can_enable,
    }


def register_extension_settings(
    ext_type: ExtensionType,
    name: str,
    config_fields: Optional[list[Dict[str, Any]]] = None
) -> None:
    """Register settings for a new extension in the settings registry.

    This should be called when an extension is first discovered to add
    its settings to the registry.

    Args:
        ext_type: Type of extension
        name: Extension name
        config_fields: List of field definitions (key, type, default, required, description)
    """
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY, SettingDef

    prefix = get_extension_settings_prefix(ext_type, name)

    # Always register enabled setting
    enabled_key = f"{prefix}.enabled"
    if enabled_key not in SETTINGS_REGISTRY:
        # Default: disabled if has required fields, enabled otherwise
        has_required = any(f.get("required", False) for f in (config_fields or []))
        SETTINGS_REGISTRY[enabled_key] = SettingDef(
            category="extension",
            type=bool,
            default=not has_required,
            editable=True,
            env_var="",
            description=f"Whether {name} extension is enabled",
        )

    # Register config fields
    if config_fields:
        for field in config_fields:
            field_key = f"{prefix}.{field['key']}"
            if field_key not in SETTINGS_REGISTRY:
                field_type = field.get("type", str)
                if isinstance(field_type, str):
                    # Convert string type to Python type
                    type_map = {
                        "string": str,
                        "boolean": bool,
                        "integer": int,
                        "path": str,
                    }
                    field_type = type_map.get(field_type, str)

                SETTINGS_REGISTRY[field_key] = SettingDef(
                    category="extension",
                    type=field_type,
                    default=field.get("default"),
                    editable=True,
                    env_var="",
                    secret=field.get("secret", False),
                    description=field.get("description", ""),
                )
