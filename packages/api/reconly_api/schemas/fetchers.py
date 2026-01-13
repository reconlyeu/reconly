"""Fetcher-related schemas."""
from typing import List
from pydantic import BaseModel, ConfigDict, Field

from reconly_api.schemas.common import ConfigFieldResponse


class FetcherConfigSchemaResponse(BaseModel):
    """Schema for fetcher configuration schema."""
    fields: List[ConfigFieldResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FetcherResponse(BaseModel):
    """Schema for single fetcher in list response."""
    name: str = Field(..., description="Source type name (e.g., 'rss', 'youtube')")
    description: str = Field(..., description="Human-readable description")
    config_schema: FetcherConfigSchemaResponse = Field(
        ..., description="Configuration options"
    )
    # Activation state fields
    enabled: bool = Field(default=True, description="Whether fetcher is enabled")
    is_configured: bool = Field(default=True, description="Whether all required config fields have values")
    can_enable: bool = Field(default=True, description="Whether fetcher can be enabled")
    # Extension flag
    is_extension: bool = Field(default=False, description="Whether this is an external extension")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "rss",
            "description": "RSS/Atom feed fetcher",
            "config_schema": {
                "fields": []
            },
            "enabled": True,
            "is_configured": True,
            "can_enable": True,
            "is_extension": False
        }
    })


class FetcherListResponse(BaseModel):
    """Schema for list of fetchers."""
    fetchers: List[FetcherResponse] = Field(..., description="Available fetchers")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "fetchers": [
                {
                    "name": "rss",
                    "description": "RSS/Atom feed fetcher",
                    "config_schema": {"fields": []},
                    "enabled": True,
                    "is_configured": True,
                    "can_enable": True,
                    "is_extension": False
                }
            ]
        }
    })


class FetcherToggleRequest(BaseModel):
    """Schema for toggling fetcher enabled state."""
    enabled: bool = Field(..., description="Whether to enable or disable the fetcher")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "enabled": True
        }
    })
