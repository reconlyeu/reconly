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
        default="",  # No default - user must configure
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

    # ─────────────────────────────────────────────────────────────────────────
    # Agent Settings
    # Configuration for agent-based web research sources
    # ─────────────────────────────────────────────────────────────────────────
    "agent.search_provider": SettingDef(
        category="agent",
        type=str,
        default="brave",
        editable=True,
        env_var="AGENT_SEARCH_PROVIDER",
        description="Search provider: brave or searxng",
    ),
    "agent.brave_api_key": SettingDef(
        category="agent",
        type=str,
        default=None,
        editable=False,  # Secret - env only
        env_var="BRAVE_API_KEY",
        secret=True,
        description="Brave Search API key",
    ),
    "agent.searxng_url": SettingDef(
        category="agent",
        type=str,
        default="http://localhost:8080",
        editable=True,
        env_var="SEARXNG_URL",
        description="SearXNG instance URL",
    ),
    "agent.max_search_results": SettingDef(
        category="agent",
        type=int,
        default=10,
        editable=True,
        env_var="AGENT_MAX_SEARCH_RESULTS",
        description="Maximum number of search results to retrieve",
    ),
    "agent.default_max_iterations": SettingDef(
        category="agent",
        type=int,
        default=5,
        editable=True,
        env_var="AGENT_DEFAULT_MAX_ITERATIONS",
        description="Default maximum iterations for agent research loops",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # Resilience Settings
    # Configuration for circuit breakers, retry logic, and validation
    # ─────────────────────────────────────────────────────────────────────────
    "resilience.circuit_breaker.failure_threshold": SettingDef(
        category="resilience",
        type=int,
        default=5,
        editable=True,
        env_var="RESILIENCE_CB_FAILURE_THRESHOLD",
        description="Number of consecutive failures before circuit opens",
    ),
    "resilience.circuit_breaker.recovery_timeout": SettingDef(
        category="resilience",
        type=int,
        default=300,
        editable=True,
        env_var="RESILIENCE_CB_RECOVERY_TIMEOUT",
        description="Seconds to wait before attempting recovery (circuit half-open)",
    ),
    "resilience.retry.max_attempts": SettingDef(
        category="resilience",
        type=int,
        default=3,
        editable=True,
        env_var="RESILIENCE_RETRY_MAX_ATTEMPTS",
        description="Maximum number of retry attempts for transient errors",
    ),
    "resilience.retry.base_delay": SettingDef(
        category="resilience",
        type=float,
        default=1.0,
        editable=True,
        env_var="RESILIENCE_RETRY_BASE_DELAY",
        description="Initial delay between retries in seconds",
    ),
    "resilience.retry.max_delay": SettingDef(
        category="resilience",
        type=float,
        default=60.0,
        editable=True,
        env_var="RESILIENCE_RETRY_MAX_DELAY",
        description="Maximum delay between retries in seconds",
    ),
    "resilience.validation.default_timeout": SettingDef(
        category="resilience",
        type=int,
        default=10,
        editable=True,
        env_var="RESILIENCE_VALIDATION_TIMEOUT",
        description="Default timeout for source validation test fetch",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # RAG Source Content Settings
    # Configuration for source content storage and embedding behavior
    # ─────────────────────────────────────────────────────────────────────────
    "rag.source_content.enabled": SettingDef(
        category="rag",
        type=bool,
        default=True,
        editable=True,
        env_var="RAG_SOURCE_CONTENT_ENABLED",
        description="Whether to store source content for RAG embedding",
    ),
    "rag.source_content.max_length": SettingDef(
        category="rag",
        type=int,
        default=100000,
        editable=True,
        env_var="RAG_SOURCE_CONTENT_MAX_LENGTH",
        description="Maximum content length (characters) to store per source item",
    ),
    "rag.source_content.default_chunk_source": SettingDef(
        category="rag",
        type=str,
        default="source_content",
        editable=True,
        env_var="RAG_DEFAULT_CHUNK_SOURCE",
        description="Default chunk source for RAG queries: 'source_content' or 'digest'",
    ),
    "rag.graph.semantic_threshold": SettingDef(
        category="rag",
        type=float,
        default=0.75,
        editable=True,
        env_var="RAG_GRAPH_SEMANTIC_THRESHOLD",
        description="Minimum similarity score for semantic relationships (0.0-1.0)",
    ),
    "rag.graph.max_edges_per_digest": SettingDef(
        category="rag",
        type=int,
        default=10,
        editable=True,
        env_var="RAG_GRAPH_MAX_EDGES",
        description="Maximum number of relationship edges per digest",
    ),
    "rag.graph.auto_compute": SettingDef(
        category="rag",
        type=bool,
        default=True,
        editable=True,
        env_var="RAG_GRAPH_AUTO_COMPUTE",
        description="Automatically compute relationships when digests are created",
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
