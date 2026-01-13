"""Source schemas for API."""
import re
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime


FilterMode = Literal["title_only", "content", "both"]


class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(rss|youtube|website|blog)$")
    url: str = Field(..., max_length=2048)
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = True
    # Content filtering
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    filter_mode: Optional[FilterMode] = "both"
    use_regex: Optional[bool] = False

    @model_validator(mode='after')
    def validate_regex_patterns(self):
        """Validate regex patterns if use_regex is enabled."""
        if not self.use_regex:
            return self

        for field_name in ['include_keywords', 'exclude_keywords']:
            patterns = getattr(self, field_name)
            if patterns:
                for pattern in patterns:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regex pattern '{pattern}' in {field_name}: {e}")
        return self


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, pattern="^(rss|youtube|website|blog)$")
    url: Optional[str] = Field(None, max_length=2048)
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    # Content filtering
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    filter_mode: Optional[FilterMode] = None
    use_regex: Optional[bool] = None

    @model_validator(mode='after')
    def validate_regex_patterns(self):
        """Validate regex patterns if use_regex is enabled."""
        if not self.use_regex:
            return self

        for field_name in ['include_keywords', 'exclude_keywords']:
            patterns = getattr(self, field_name)
            if patterns:
                for pattern in patterns:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regex pattern '{pattern}' in {field_name}: {e}")
        return self


class SourceResponse(SourceBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
