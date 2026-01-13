"""Batch operation schemas for API."""
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class BatchDeleteRequest(BaseModel):
    """Schema for batch delete request."""
    ids: List[int] = Field(..., min_length=1, description="List of IDs to delete")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "ids": [1, 2, 3, 4, 5]
        }
    })


class BatchDeleteResponse(BaseModel):
    """Schema for batch delete response."""
    deleted_count: int = Field(..., description="Number of successfully deleted items")
    failed_ids: List[int] = Field(default_factory=list, description="IDs that failed to delete")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "deleted_count": 5,
            "failed_ids": []
        }
    })
