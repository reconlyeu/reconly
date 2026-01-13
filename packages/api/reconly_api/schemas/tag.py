"""Tag-related schemas."""
from typing import List
from pydantic import BaseModel, Field


class TagResponse(BaseModel):
    """Schema for a tag with usage count."""
    id: int
    name: str
    digest_count: int = Field(default=0, description="Number of digests using this tag")


class TagListResponse(BaseModel):
    """Schema for list of tags."""
    tags: List[TagResponse]
    total: int


class TagSuggestion(BaseModel):
    """Schema for tag autocomplete suggestion."""
    name: str
    digest_count: int = Field(default=0, description="Number of digests using this tag")


class TagSuggestionsResponse(BaseModel):
    """Schema for tag suggestions response."""
    suggestions: List[TagSuggestion]


class TagDeleteResponse(BaseModel):
    """Schema for tag deletion response."""
    deleted: bool = True
    tag_name: str
    digests_affected: int = Field(default=0, description="Number of digests that had this tag removed")


class TagBulkDeleteResponse(BaseModel):
    """Schema for bulk tag deletion response."""
    deleted_count: int = Field(description="Number of tags deleted")
    tag_names: List[str] = Field(description="Names of deleted tags")
