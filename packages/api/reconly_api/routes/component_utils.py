"""Shared utilities for component routes (exporters, fetchers, etc.)."""
from typing import List, Tuple

from reconly_core.config_types import ComponentConfigSchema
from reconly_core.services.settings_service import SettingsService
from reconly_core.services.settings_registry import SETTINGS_REGISTRY

from reconly_api.schemas.common import ConfigFieldResponse


def get_enabled_key(component_type: str, component_name: str) -> str:
    """Get the settings key for component enabled state.

    Args:
        component_type: Type of component (e.g., 'export', 'fetch')
        component_name: Name of the component (e.g., 'obsidian', 'rss')

    Returns:
        Settings key like 'export.obsidian.enabled'
    """
    return f"{component_type}.{component_name}.enabled"


def is_component_configured(
    component_type: str,
    component_name: str,
    schema: ComponentConfigSchema,
    settings_service: SettingsService,
) -> bool:
    """Check if all required config fields for a component have values set.

    Args:
        component_type: Type of component (e.g., 'export', 'fetch')
        component_name: Name of the component
        schema: Component's configuration schema
        settings_service: Settings service instance

    Returns:
        True if all required fields are configured, False otherwise
    """
    required_fields = [f for f in schema.fields if f.required]
    if not required_fields:
        return True

    for field in required_fields:
        setting_key = f"{component_type}.{component_name}.{field.key}"
        if setting_key not in SETTINGS_REGISTRY:
            return False
        value = settings_service.get(setting_key)
        if value is None or value == "":
            return False

    return True


def get_activation_state(
    component_type: str,
    component_name: str,
    schema: ComponentConfigSchema,
    settings_service: SettingsService,
) -> Tuple[bool, bool, bool]:
    """Get the activation state for a component.

    Args:
        component_type: Type of component (e.g., 'export', 'fetch')
        component_name: Name of the component
        schema: Component's configuration schema
        settings_service: Settings service instance

    Returns:
        Tuple of (enabled, is_configured, can_enable)
    """
    is_configured = is_component_configured(
        component_type, component_name, schema, settings_service
    )

    has_required = any(f.required for f in schema.fields)

    enabled_key = get_enabled_key(component_type, component_name)
    if enabled_key in SETTINGS_REGISTRY:
        enabled = settings_service.get(enabled_key)
    else:
        # Default: non-configurable components enabled, configurable disabled
        enabled = not has_required

    # can_enable is True if configured OR if no required fields
    can_enable = is_configured or not has_required

    return enabled, is_configured, can_enable


def get_missing_required_fields(
    component_type: str,
    component_name: str,
    schema: ComponentConfigSchema,
    settings_service: SettingsService,
) -> List[str]:
    """Get list of required fields that are missing values.

    Args:
        component_type: Type of component (e.g., 'export', 'fetch')
        component_name: Name of the component
        schema: Component's configuration schema
        settings_service: Settings service instance

    Returns:
        List of field keys that are missing values
    """
    missing = []
    for field in schema.fields:
        if not field.required:
            continue
        setting_key = f"{component_type}.{component_name}.{field.key}"
        if setting_key not in SETTINGS_REGISTRY:
            missing.append(field.key)
        else:
            value = settings_service.get(setting_key)
            if value is None or value == "":
                missing.append(field.key)
    return missing


def convert_config_fields(schema: ComponentConfigSchema) -> List[ConfigFieldResponse]:
    """Convert config schema fields to API response format.

    Args:
        schema: Component's configuration schema

    Returns:
        List of ConfigFieldResponse objects
    """
    return [
        ConfigFieldResponse(
            key=f.key,
            type=f.type,
            label=f.label,
            description=f.description,
            default=f.default,
            required=f.required,
            placeholder=f.placeholder,
            env_var=f.env_var or None,
            editable=f.editable,
            secret=f.secret,
            options_from=f.options_from or None,
        )
        for f in schema.fields
    ]
