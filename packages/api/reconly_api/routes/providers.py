"""Provider status and configuration API routes."""
import logging
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
    ResolvedProviderResponse,
)
from reconly_api.schemas.components import ProviderMetadataResponse
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


def _get_default_fallback_chain() -> list[str]:
    """Get default fallback chain from settings registry (single source of truth)."""
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY
    return SETTINGS_REGISTRY["llm.fallback_chain"].default.copy()


def _mask_api_key(api_key: Optional[str], provider_name: str) -> Optional[str]:
    """Mask an API key for display using provider metadata.

    Uses the provider's metadata.mask_api_key() method which preserves the
    configured API key prefix (e.g., 'sk-' for OpenAI, 'sk-ant-' for Anthropic).

    Falls back to a hardcoded prefix map for providers without metadata.

    Args:
        api_key: The API key to mask
        provider_name: Name of the provider

    Returns:
        Masked API key string (e.g., 'sk-***xyz') or None if no key
    """
    if not api_key:
        return None

    # Try to use provider metadata for masking
    if is_provider_registered(provider_name):
        try:
            entry = get_provider_entry(provider_name)
            metadata = entry.cls.get_metadata()
            return metadata.mask_api_key(api_key)
        except (AttributeError, NotImplementedError):
            pass

    # Fallback: hardcoded prefix map for providers without metadata
    prefix_map = {
        'openai': 'sk-',
        'anthropic': 'sk-ant-',
        'huggingface': 'hf_',
    }
    prefix = prefix_map.get(provider_name, '')

    # Show prefix + masked middle + last 3 chars (matching metadata behavior)
    suffix = api_key[-3:] if len(api_key) > 3 else ""
    return f"{prefix}***{suffix}"


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


def _provider_metadata_to_response(provider_cls) -> Optional[ProviderMetadataResponse]:
    """Convert provider metadata to API response schema.

    Args:
        provider_cls: Provider class with get_metadata() method

    Returns:
        ProviderMetadataResponse or None if metadata not available
    """
    try:
        metadata = provider_cls.get_metadata()
        return ProviderMetadataResponse(
            name=metadata.name,
            display_name=metadata.display_name,
            description=metadata.description,
            icon=metadata.icon,
            is_local=metadata.is_local,
            requires_api_key=metadata.requires_api_key,
        )
    except (AttributeError, NotImplementedError):
        # Provider doesn't have get_metadata() or it's not implemented
        return None


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
    """Check if a local provider is available (server reachable).

    Uses provider metadata for configuration:
    - metadata.is_local: Whether to perform availability check
    - metadata.get_base_url(): Base URL for the provider
    - metadata.availability_endpoint: Endpoint to check (e.g., '/api/tags')

    Args:
        provider_name: Name of the provider to check

    Returns:
        True if provider is reachable, False otherwise
    """
    if not is_provider_registered(provider_name):
        return False

    try:
        entry = get_provider_entry(provider_name)
        metadata = entry.cls.get_metadata()

        # Only check local providers with availability endpoints
        if not metadata.is_local or not metadata.availability_endpoint:
            return False

        # Build full URL from base_url + availability_endpoint
        base_url = metadata.get_base_url()
        if not base_url:
            return False

        # Remove trailing /v1 if present for endpoint construction
        # (LMStudio uses /v1 as base but /v1/models as endpoint)
        check_url = f"{base_url.rstrip('/')}{metadata.availability_endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.get(check_url, timeout=2.0)
            return response.status_code == 200

    except (AttributeError, NotImplementedError):
        # Provider doesn't have metadata - use legacy behavior
        logger.debug(f"Provider {provider_name} has no metadata for availability check")
        return False
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.debug(f"{provider_name} availability check failed: {e}")
        return False
    except Exception as e:
        logger.debug(f"{provider_name} availability check error: {e}")
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
        fallback_chain = _get_default_fallback_chain()

    # Pre-check local provider availability using metadata
    local_availability = {}
    for provider_name in list_providers():
        entry = get_provider_entry(provider_name)
        # Try metadata first, fall back to capabilities
        try:
            metadata = entry.cls.get_metadata()
            is_local = metadata.is_local
        except (AttributeError, NotImplementedError):
            capabilities = entry.cls.get_capabilities()
            is_local = capabilities.is_local

        if is_local:
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
                metadata=_provider_metadata_to_response(provider_cls),
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


@router.get("/default", response_model=ResolvedProviderResponse)
async def get_default_provider(db: Session = Depends(get_db)):
    """Get the resolved default provider (first available from fallback chain).

    Checks each provider in the fallback chain for actual availability:
    - Local providers (Ollama, LMStudio): Pings the server
    - Cloud providers (OpenAI, Anthropic): Checks for API key

    Returns the first available provider with its default model.
    This is what will actually be used for chat/summarization.
    """
    from reconly_core.providers.factory import resolve_default_provider

    result = resolve_default_provider(db=db)
    return ResolvedProviderResponse(**result)
