"""Provider-related schemas for API responses."""
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from reconly_api.schemas.common import ConfigFieldResponse


class ProviderConfigSchemaResponse(BaseModel):
    """Schema for provider configuration schema."""
    fields: List[ConfigFieldResponse] = Field(default_factory=list)
    requires_api_key: bool = Field(default=False, description="Whether provider requires an API key")

    model_config = ConfigDict(from_attributes=True)


class ModelInfoResponse(BaseModel):
    """Schema for model information."""
    id: str = Field(..., description="Model identifier (e.g., 'claude-sonnet-4-20250514')")
    name: str = Field(..., description="Display name (e.g., 'Claude Sonnet 4')")
    provider: str = Field(..., description="Provider name (e.g., 'anthropic', 'openai')")
    is_default: bool = Field(default=False, description="Whether this is the provider's default model")
    deprecated: bool = Field(default=False, description="Whether model is deprecated")

    model_config = ConfigDict(from_attributes=True)


ProviderStatus = Literal["available", "configured", "not_configured", "unavailable"]


class ProviderResponse(BaseModel):
    """Schema for single provider in list response."""
    name: str = Field(..., description="Provider name (e.g., 'ollama', 'openai')")
    description: str = Field(..., description="Human-readable description")
    status: ProviderStatus = Field(..., description="Provider status")
    is_local: bool = Field(..., description="Whether provider runs locally")
    models: List[ModelInfoResponse] = Field(default_factory=list, description="Available models")
    config_schema: ProviderConfigSchemaResponse = Field(
        ..., description="Configuration options for this provider"
    )
    masked_api_key: Optional[str] = Field(
        default=None, description="Masked API key if configured (e.g., 'sk-...xxxx')"
    )
    is_extension: bool = Field(default=False, description="Whether this is an external extension")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "ollama",
            "description": "Local LLM via Ollama server",
            "status": "available",
            "is_local": True,
            "models": [
                {"id": "llama3.2", "name": "llama3.2", "provider": "ollama", "is_default": True, "deprecated": False}
            ],
            "config_schema": {
                "fields": [
                    {
                        "key": "base_url",
                        "type": "string",
                        "label": "Server URL",
                        "description": "URL of your Ollama server",
                        "default": "http://localhost:11434",
                        "required": False,
                        "placeholder": "http://localhost:11434",
                        "env_var": "OLLAMA_BASE_URL",
                        "editable": True,
                        "secret": False,
                        "options_from": None
                    }
                ],
                "requires_api_key": False
            },
            "masked_api_key": None,
            "is_extension": False
        }
    })


class ProviderListResponse(BaseModel):
    """Schema for provider configuration response."""
    providers: List[ProviderResponse] = Field(..., description="Available providers")
    fallback_chain: List[str] = Field(
        ...,
        description="Ordered list of provider names for fallback. Position 0 = default provider."
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "providers": [
                {
                    "name": "ollama",
                    "description": "Local LLM via Ollama server",
                    "status": "available",
                    "is_local": True,
                    "models": [],
                    "config_schema": {"fields": [], "requires_api_key": False},
                    "masked_api_key": None,
                    "is_extension": False
                }
            ],
            "fallback_chain": ["ollama", "huggingface", "openai", "anthropic"]
        }
    })
