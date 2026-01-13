"""Settings registry defining all configurable settings with metadata.

Each setting has:
- category: Grouping for UI display (provider, email, export)
- type: Python type for validation
- default: Default value if not set in env or DB
- editable: Whether user can modify via UI (False = env-only)
- env_var: Environment variable name
- secret: Whether to mask value in API responses
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.config_types import ProviderConfigSchema
    from reconly_core.exporters.base import ExporterConfigSchema
    from reconly_core.fetchers.base import FetcherConfigSchema

logger = logging.getLogger(__name__)


@dataclass
class SettingDef:
    """Definition of a configurable setting."""
    category: str
    type: type
    default: Any
    editable: bool
    env_var: str
    secret: bool = False
    description: str = ""


# Registry of all settings
# Foundation settings + global settings
# Per-provider settings are auto-registered via @register_provider decorator
SETTINGS_REGISTRY: dict[str, SettingDef] = {
    # ─────────────────────────────────────────────────────────────────────────
    # Global LLM/Provider Settings
    # Per-provider settings (api_key, model, base_url) are auto-registered
    # via @register_provider decorator using provider.{name}.{field} pattern
    # ─────────────────────────────────────────────────────────────────────────
    "llm.default_provider": SettingDef(
        category="provider",
        type=str,
        default="ollama",
        editable=True,
        env_var="DEFAULT_PROVIDER",
        description="Default LLM provider for summarization",
    ),
    "llm.default_model": SettingDef(
        category="provider",
        type=str,
        default="llama3.2",
        editable=True,
        env_var="DEFAULT_MODEL",
        description="Default model for the selected provider",
    ),
    "llm.fallback_chain": SettingDef(
        category="provider",
        type=list,
        default=["ollama", "huggingface", "openai", "anthropic"],
        editable=True,
        env_var="",  # No direct env var, JSON in DB
        description="Provider fallback order when primary fails",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # Email Settings
    # ─────────────────────────────────────────────────────────────────────────
    "email.smtp_host": SettingDef(
        category="email",
        type=str,
        default="localhost",
        editable=True,
        env_var="SMTP_HOST",
        description="SMTP server hostname",
    ),
    "email.smtp_port": SettingDef(
        category="email",
        type=int,
        default=587,
        editable=True,
        env_var="SMTP_PORT",
        description="SMTP server port",
    ),
    "email.smtp_user": SettingDef(
        category="email",
        type=str,
        default=None,
        editable=False,  # Credential - env only
        env_var="SMTP_USER",
        description="SMTP username",
    ),
    "email.smtp_password": SettingDef(
        category="email",
        type=str,
        default=None,
        editable=False,  # Secret - env only
        env_var="SMTP_PASSWORD",
        secret=True,
        description="SMTP password",
    ),
    "email.from_address": SettingDef(
        category="email",
        type=str,
        default="noreply@reconly.com",
        editable=True,
        env_var="SMTP_FROM_EMAIL",
        description="Sender email address",
    ),
    "email.from_name": SettingDef(
        category="email",
        type=str,
        default="Reconly",
        editable=True,
        env_var="SMTP_FROM_NAME",
        description="Sender display name",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # Global Export Settings
    # Per-exporter settings are auto-registered via @register_exporter decorator
    # ─────────────────────────────────────────────────────────────────────────
    "export.default_format": SettingDef(
        category="export",
        type=str,
        default="json",
        editable=True,
        env_var="DEFAULT_EXPORT_FORMAT",
        description="Default export format (json, csv, obsidian)",
    ),
    "export.include_metadata": SettingDef(
        category="export",
        type=bool,
        default=True,
        editable=True,
        env_var="EXPORT_INCLUDE_METADATA",
        description="Include metadata in exports",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # RAG / Embedding Settings
    # ─────────────────────────────────────────────────────────────────────────
    "embedding.provider": SettingDef(
        category="embedding",
        type=str,
        default="ollama",
        editable=True,
        env_var="EMBEDDING_PROVIDER",
        description="Embedding provider for RAG (ollama, openai, huggingface)",
    ),
    "embedding.model": SettingDef(
        category="embedding",
        type=str,
        default="bge-m3",
        editable=True,
        env_var="EMBEDDING_MODEL",
        description="Embedding model for the selected provider",
    ),
    "embedding.batch_size": SettingDef(
        category="embedding",
        type=int,
        default=32,
        editable=True,
        env_var="EMBEDDING_BATCH_SIZE",
        description="Number of texts to embed per batch",
    ),
    "embedding.chunk_size": SettingDef(
        category="embedding",
        type=int,
        default=384,
        editable=True,
        env_var="EMBEDDING_CHUNK_SIZE",
        description="Target token count per chunk (256-512 recommended)",
    ),
    "embedding.chunk_overlap": SettingDef(
        category="embedding",
        type=int,
        default=64,
        editable=True,
        env_var="EMBEDDING_CHUNK_OVERLAP",
        description="Token overlap between chunks (10-20% of chunk_size)",
    ),
}


def get_settings_by_category(category: str) -> dict[str, SettingDef]:
    """Get all settings for a specific category."""
    return {
        key: setting
        for key, setting in SETTINGS_REGISTRY.items()
        if setting.category == category
    }


def get_all_categories() -> list[str]:
    """Get list of all setting categories."""
    return list(set(s.category for s in SETTINGS_REGISTRY.values()))


# ─────────────────────────────────────────────────────────────────────────────
# Component Settings Auto-Registration
# ─────────────────────────────────────────────────────────────────────────────

# ConfigField.type string -> Python type mapping
_CONFIG_FIELD_TYPE_MAP: dict[str, type] = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "path": str,
}


def register_component_settings(
    component_type: str,
    name: str,
    schema: "ExporterConfigSchema | FetcherConfigSchema | ProviderConfigSchema",
) -> None:
    """
    Register settings for a component based on its config schema.

    Called automatically by component decorators (e.g., @register_exporter, @register_fetcher,
    @register_provider) to add settings entries to SETTINGS_REGISTRY.

    Args:
        component_type: Type prefix for settings keys (e.g., "export", "fetch", "provider")
        name: Component name (e.g., "json", "csv", "rss", "youtube", "openai")
        schema: The component's configuration schema with field definitions
    """
    prefix = f"{component_type}.{name}"
    has_required_fields = any(f.required for f in schema.fields)

    # Register enabled setting (defaults to False if component has required fields)
    # Skip enabled setting for providers - they're always available if configured
    if component_type != "provider":
        _register_enabled_setting(prefix, component_type, name, has_required_fields)

    # Register each field from the schema
    for field in schema.fields:
        _register_field_setting(prefix, component_type, name, field)


def _register_enabled_setting(
    prefix: str,
    component_type: str,
    name: str,
    has_required_fields: bool,
) -> None:
    """Register the enabled setting for a component."""
    enabled_key = f"{prefix}.enabled"
    if enabled_key in SETTINGS_REGISTRY:
        return

    SETTINGS_REGISTRY[enabled_key] = SettingDef(
        category=component_type,
        type=bool,
        default=not has_required_fields,
        editable=True,
        env_var="",
        description=f"Whether {name} {component_type}er is enabled",
    )
    logger.debug(f"Auto-registered setting: {enabled_key}")


def _register_field_setting(
    prefix: str,
    component_type: str,
    name: str,
    field,
) -> None:
    """Register a single field setting from a config schema."""
    setting_key = f"{prefix}.{field.key}"

    if setting_key in SETTINGS_REGISTRY:
        logger.debug(f"Setting {setting_key} already exists, skipping")
        return

    python_type = _CONFIG_FIELD_TYPE_MAP.get(field.type, str)

    # Use field's env_var if specified, otherwise generate default
    env_var_name = field.env_var or f"{name.upper()}_{field.key.upper()}"

    SETTINGS_REGISTRY[setting_key] = SettingDef(
        category=component_type,
        type=python_type,
        default=field.default,
        editable=field.editable,
        env_var=env_var_name,
        secret=field.secret,
        description=field.description,
    )
    logger.debug(f"Auto-registered setting: {setting_key}")
