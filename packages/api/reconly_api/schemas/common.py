"""Common schemas shared across API modules."""
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConfigFieldResponse(BaseModel):
    """Schema for component config field (shared by exporters, fetchers, providers, etc.)."""
    key: str = Field(..., description="Setting key")
    type: str = Field(..., description="Field type: string, boolean, integer, path, select")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="Help text")
    default: Any = Field(default=None, description="Default value")
    required: bool = Field(default=False, description="Required for operation")
    placeholder: str = Field(default="", description="Input placeholder")
    env_var: Optional[str] = Field(default=None, description="Environment variable name for this field")
    editable: bool = Field(default=True, description="Whether field can be edited via UI (False = env-only)")
    secret: bool = Field(default=False, description="Whether field contains sensitive data")
    options_from: Optional[str] = Field(default=None, description="Source for select options (e.g., 'models')")

    model_config = ConfigDict(from_attributes=True)
