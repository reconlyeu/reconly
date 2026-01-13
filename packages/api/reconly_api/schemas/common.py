"""Common schemas shared across API modules."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConfigFieldResponse(BaseModel):
    """Schema for component config field (shared by exporters, fetchers, etc.)."""
    key: str = Field(..., description="Setting key")
    type: str = Field(..., description="Field type: string, boolean, integer, path")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="Help text")
    default: Any = Field(default=None, description="Default value")
    required: bool = Field(default=False, description="Required for operation")
    placeholder: str = Field(default="", description="Input placeholder")

    model_config = ConfigDict(from_attributes=True)
