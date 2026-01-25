"""Shared configuration types for components (exporters, fetchers, etc.).

This module defines common data structures used across different component types
for configuration schemas and settings registration.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigField:
    """Single configuration field definition for a component.

    Attributes:
        key: Setting key (e.g., "timeout", "vault_path")
        type: Field type - "string", "boolean", "integer", "path", or "select"
        label: Human-readable label for UI
        description: Help text describing the field
        default: Default value if not configured
        required: Whether field is required for the component to function
        placeholder: Input placeholder text for UI
        env_var: Environment variable name for this field (e.g., "OPENAI_API_KEY")
        editable: Whether field can be edited via UI (False = env-only, for secrets)
        secret: Whether field contains sensitive data (should be masked in responses)
        options_from: Source for select options (e.g., "models" to populate from models list)
        options: Static options for select fields: [{"value": "...", "label": "..."}]
    """
    key: str
    type: str  # "string" | "boolean" | "integer" | "path" | "select"
    label: str
    description: str
    default: Any = None
    required: bool = False
    placeholder: str = ""
    env_var: str = ""
    editable: bool = True
    secret: bool = False
    options_from: str = ""
    options: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ComponentConfigSchema:
    """Base configuration schema for a component.

    Attributes:
        fields: List of configurable fields
    """
    fields: list[ConfigField] = field(default_factory=list)


@dataclass
class ProviderConfigSchema(ComponentConfigSchema):
    """Configuration schema for a provider (summarizer).

    Inherits fields from ComponentConfigSchema.

    Attributes:
        requires_api_key: Whether provider requires an API key to function
    """
    requires_api_key: bool = False
