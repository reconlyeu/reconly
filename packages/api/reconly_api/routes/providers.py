"""Provider status and configuration API routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import httpx
import logging

from reconly_api.dependencies import get_db
from reconly_core.services.settings_service import SettingsService
from reconly_core.providers.capabilities import ModelInfo
from reconly_core.providers.cache import get_model_cache
from reconly_core.providers.ollama import OllamaProvider
from reconly_core.providers.anthropic import AnthropicProvider
from reconly_core.providers.openai_provider import OpenAIProvider
from reconly_core.providers.huggingface import HuggingFaceProvider

router = APIRouter()
logger = logging.getLogger(__name__)

# Ollama URL is configurable via environment variable
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Provider class mapping
PROVIDER_CLASSES = {
    'ollama': OllamaProvider,
    'anthropic': AnthropicProvider,
    'openai': OpenAIProvider,
    'huggingface': HuggingFaceProvider,
}


def get_provider_models_cached(provider_name: str, api_key: Optional[str] = None) -> List[ModelInfo]:
    """Get models for provider with caching."""
    cache = get_model_cache()

    # Check cache first
    cached = cache.get(provider_name)
    if cached is not None:
        return cached

    # Fetch from provider
    provider_class = PROVIDER_CLASSES.get(provider_name)
    if not provider_class:
        return []

    models = provider_class.list_models(api_key=api_key)

    # Cache result
    cache.set(provider_name, models)
    return models


@router.get("")
async def get_provider_config(db: Session = Depends(get_db)):
    """Get provider configuration and status."""
    providers = []
    settings_service = SettingsService(db)

    # Get saved default provider/model from settings service (DB > env > default)
    saved_default_provider = settings_service.get("llm.default_provider")
    saved_default_model = settings_service.get("llm.default_model")

    # Check Ollama
    ollama_available = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            if response.status_code == 200:
                ollama_available = True
    except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
        logger.debug(f"Ollama check failed: {e}")

    # Get dynamic models for each provider
    ollama_models = get_provider_models_cached('ollama') if ollama_available else []

    # Ollama is a local service - use "unavailable" when not running, not "not_configured"
    providers.append({
        "name": "ollama",
        "status": "available" if ollama_available else "unavailable",
        "masked_api_key": None,
        "models": [m.to_dict() for m in ollama_models],
        "is_default": saved_default_provider == "ollama"
    })

    # Check HuggingFace
    hf_token = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
    hf_models = get_provider_models_cached('huggingface', api_key=hf_token)
    providers.append({
        "name": "huggingface",
        "status": "configured" if hf_token else "not_configured",
        "masked_api_key": f"hf_...{hf_token[-4:]}" if hf_token else None,
        "models": [m.to_dict() for m in hf_models],
        "is_default": saved_default_provider == "huggingface"
    })

    # Check OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    openai_models = get_provider_models_cached('openai', api_key=openai_key)
    providers.append({
        "name": "openai",
        "status": "configured" if openai_key else "not_configured",
        "masked_api_key": f"sk-...{openai_key[-4:]}" if openai_key else None,
        "models": [m.to_dict() for m in openai_models],
        "is_default": saved_default_provider == "openai"
    })

    # Check Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_models = get_provider_models_cached('anthropic', api_key=anthropic_key)
    providers.append({
        "name": "anthropic",
        "status": "configured" if anthropic_key else "not_configured",
        "masked_api_key": f"sk-...{anthropic_key[-4:]}" if anthropic_key else None,
        "models": [m.to_dict() for m in anthropic_models],
        "is_default": saved_default_provider == "anthropic"
    })

    # Determine fallback order
    fallback_order = []
    if ollama_available:
        fallback_order.append("ollama")
    if hf_token:
        fallback_order.append("huggingface")
    if openai_key:
        fallback_order.append("openai")
    if anthropic_key:
        fallback_order.append("anthropic")

    return {
        "providers": providers,
        "default_provider": saved_default_provider,
        "default_model": saved_default_model,
        "fallback_order": fallback_order
    }


@router.get("/{provider_name}/models")
async def get_provider_models(provider_name: str):
    """Get available models for a provider."""
    if provider_name not in PROVIDER_CLASSES:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")

    # Get API key for the provider if available
    api_keys = {
        'openai': os.getenv('OPENAI_API_KEY'),
        'anthropic': os.getenv('ANTHROPIC_API_KEY'),
        'huggingface': os.getenv('HUGGINGFACE_API_KEY') or os.getenv('HF_TOKEN'),
        'ollama': None,
    }

    models = get_provider_models_cached(provider_name, api_key=api_keys.get(provider_name))
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
        if provider_name not in PROVIDER_CLASSES:
            raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")
        api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'anthropic': os.getenv('ANTHROPIC_API_KEY'),
            'huggingface': os.getenv('HUGGINGFACE_API_KEY') or os.getenv('HF_TOKEN'),
            'ollama': None,
        }
        models = get_provider_models_cached(provider_name, api_key=api_keys.get(provider_name))
        return {"provider": provider_name, "models": [m.to_dict() for m in models]}
    else:
        # Refresh all providers
        result = {}
        for name in PROVIDER_CLASSES.keys():
            api_keys = {
                'openai': os.getenv('OPENAI_API_KEY'),
                'anthropic': os.getenv('ANTHROPIC_API_KEY'),
                'huggingface': os.getenv('HUGGINGFACE_API_KEY') or os.getenv('HF_TOKEN'),
                'ollama': None,
            }
            models = get_provider_models_cached(name, api_key=api_keys.get(name))
            result[name] = [m.to_dict() for m in models]
        return {"providers": result}
