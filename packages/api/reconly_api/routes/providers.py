"""Provider status and configuration API routes."""
import logging
import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.providers import (
    ProviderListResponse,
    ProviderResponse,
    ProviderConfigSchemaResponse,
    ModelInfoResponse,
    ProviderStatus,
)
from reconly_api.routes.component_utils import convert_config_fields
from reconly_core.services.settings_service import SettingsService
from reconly_core.providers.capabilities import ModelInfo
from reconly_core.providers.cache import get_model_cache
from reconly_core.providers.factory import get_api_key_for_provider
from reconly_core.providers.registry import (
    list_providers,
    get_provider_entry,
    is_provider_registered,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Default fallback chain (local-first)
DEFAULT_FALLBACK_CHAIN = ["ollama", "huggingface", "openai", "anthropic"]

# Local provider URLs are configurable via environment variables
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


def _mask_api_key(api_key: Optional[str], provider_name: str) -> Optional[str]:
    """Mask an API key for display, showing only last 4 characters."""
    if not api_key:
        return None

    # Different providers use different key prefixes
    prefix_map = {
        'openai': 'sk-',
        'anthropic': 'sk-',
        'huggingface': 'hf_',
    }
    prefix = prefix_map.get(provider_name, '')
    return f"{prefix}...{api_key[-4:]}"


def _config_schema_to_response(schema) -> ProviderConfigSchemaResponse:
    """Convert a ProviderConfigSchema to ProviderConfigSchemaResponse."""
    return ProviderConfigSchemaResponse(
        fields=convert_config_fields(schema),
        requires_api_key=schema.requires_api_key,
    )


def _get_config_schema_with_fallback(entry, provider_cls):
    """Get config schema from registry entry, falling back to instance method.

    Args:
        entry: Provider registry entry
        provider_cls: Provider class

    Returns:
        ProviderConfigSchema (may be empty if all methods fail)
    """
    from reconly_core.config_types import ProviderConfigSchema

    if entry.config_schema is not None:
        return entry.config_schema

    # Fallback: try to get from instance
    try:
        instance = provider_cls(api_key="dummy_key_for_schema")
    except TypeError:
        instance = provider_cls()

    try:
        return instance.get_config_schema()
    except Exception:
        return ProviderConfigSchema(fields=[], requires_api_key=False)


def _model_info_to_response(model: ModelInfo) -> ModelInfoResponse:
    """Convert a ModelInfo dataclass to ModelInfoResponse schema."""
    return ModelInfoResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        is_default=model.is_default,
        deprecated=model.deprecated,
    )


def get_provider_models_cached(provider_name: str, api_key: Optional[str] = None) -> List[ModelInfo]:
    """Get models for provider with caching."""
    cache = get_model_cache()

    # Check cache first
    cached = cache.get(provider_name)
    if cached is not None:
        return cached

    # Fetch from provider via registry
    if not is_provider_registered(provider_name):
        return []

    entry = get_provider_entry(provider_name)
    models = entry.cls.list_models(api_key=api_key)

    # Cache result
    cache.set(provider_name, models)
    return models


async def _check_local_provider_availability(provider_name: str) -> bool:
    """Check if a local provider is available (server reachable)."""
    if provider_name == 'ollama':
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
            logger.debug(f"Ollama check failed: {e}")
            return False
    elif provider_name == 'lmstudio':
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{LMSTUDIO_BASE_URL}/models", timeout=2.0)
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
            logger.debug(f"LMStudio check failed: {e}")
            return False
    return False


def _determine_provider_status(
    is_local: bool,
    requires_api_key: bool,
    api_key: Optional[str],
    local_available: bool,
) -> ProviderStatus:
    """Determine the status of a provider based on its configuration.

    Status values:
    - available: Local provider, server reachable
    - configured: Cloud provider, API key set
    - not_configured: Missing required config (API key)
    - unavailable: Local provider, server not reachable
    """
    if is_local:
        return "available" if local_available else "unavailable"
    else:
        # Cloud provider
        if requires_api_key and not api_key:
            return "not_configured"
        return "configured"


@router.get("", response_model=ProviderListResponse)
async def get_provider_config(db: Session = Depends(get_db)):
    """Get provider configuration and status.

    Returns all registered providers with their status, available models,
    and configuration schema. Also returns the fallback chain from settings.
    """
    providers_list: List[ProviderResponse] = []
    settings_service = SettingsService(db)

    # Get fallback chain from settings (unfiltered - UI shows status)
    fallback_chain = settings_service.get("llm.fallback_chain")
    if not fallback_chain:
        fallback_chain = DEFAULT_FALLBACK_CHAIN.copy()

    # Pre-check local provider availability
    local_availability = {}
    for provider_name in list_providers():
        entry = get_provider_entry(provider_name)
        capabilities = entry.cls.get_capabilities()
        if capabilities.is_local:
            local_availability[provider_name] = await _check_local_provider_availability(provider_name)

    # Iterate over all registered providers
    for provider_name in list_providers():
        try:
            entry = get_provider_entry(provider_name)
            provider_cls = entry.cls

            # Get capabilities and config schema
            capabilities = provider_cls.get_capabilities()
            config_schema = _get_config_schema_with_fallback(entry, provider_cls)

            # Get API key
            api_key = get_api_key_for_provider(provider_name)

            # Determine status
            is_local = capabilities.is_local
            requires_api_key = capabilities.requires_api_key
            local_available = local_availability.get(provider_name, False)

            status = _determine_provider_status(
                is_local,
                requires_api_key,
                api_key,
                local_available,
            )

            # Get models (only if provider is usable)
            models: List[ModelInfo] = []
            if status in ("available", "configured"):
                models = get_provider_models_cached(provider_name, api_key=api_key)

            # Build provider response
            provider_response = ProviderResponse(
                name=provider_name,
                description=provider_cls.description,
                status=status,
                is_local=is_local,
                models=[_model_info_to_response(m) for m in models],
                config_schema=_config_schema_to_response(config_schema),
                masked_api_key=_mask_api_key(api_key, provider_name),
                is_extension=entry.is_extension,
            )
            providers_list.append(provider_response)

        except Exception as e:
            logger.warning(f"Failed to process provider '{provider_name}': {e}")
            continue

    return ProviderListResponse(
        providers=providers_list,
        fallback_chain=fallback_chain,
    )


@router.get("/{provider_name}/models")
async def get_provider_models(provider_name: str):
    """Get available models for a provider."""
    if not is_provider_registered(provider_name):
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")

    api_key = get_api_key_for_provider(provider_name)
    models = get_provider_models_cached(provider_name, api_key=api_key)
    return [m.to_dict() for m in models]


@router.post("/refresh-models")
async def refresh_models(provider_name: Optional[str] = None):
    """Invalidate model cache and fetch fresh models.

    Args:
        provider_name: Provider to refresh, or None for all providers
    """
    cache = get_model_cache()
    cache.invalidate(provider_name)

    # Re-fetch models
    if provider_name:
        if not is_provider_registered(provider_name):
            raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")
        api_key = get_api_key_for_provider(provider_name)
        models = get_provider_models_cached(provider_name, api_key=api_key)
        return {"provider": provider_name, "models": [m.to_dict() for m in models]}
    else:
        # Refresh all providers
        result = {}
        for name in list_providers():
            api_key = get_api_key_for_provider(name)
            models = get_provider_models_cached(name, api_key=api_key)
            result[name] = [m.to_dict() for m in models]
        return {"providers": result}
