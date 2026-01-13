"""Template schemas for API."""
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field
from datetime import datetime

# Template origin types
TemplateOrigin = Literal["builtin", "user", "imported"]


class PromptTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: str
    user_prompt_template: str
    language: str = "en"
    target_length: int = 150
    model_provider: Optional[str] = None
    model_name: Optional[str] = None


class PromptTemplateCreate(PromptTemplateBase):
    """Create schema - origin defaults to 'user'."""
    pass


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    language: Optional[str] = None
    target_length: Optional[int] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None


class PromptTemplateResponse(PromptTemplateBase):
    id: int
    user_id: Optional[int] = None
    origin: TemplateOrigin
    imported_from_bundle: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_system(self) -> bool:
        """Backwards compatibility field - True if origin is 'builtin'."""
        return self.origin == "builtin"


class ReportTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    format: str = Field(..., pattern="^(markdown|html|text)$")
    template_content: str


class ReportTemplateCreate(ReportTemplateBase):
    """Create schema - origin defaults to 'user'."""
    pass


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    format: Optional[str] = Field(None, pattern="^(markdown|html|text)$")
    template_content: Optional[str] = None
    is_active: Optional[bool] = None


class ReportTemplateResponse(ReportTemplateBase):
    id: int
    user_id: Optional[int] = None
    origin: TemplateOrigin
    imported_from_bundle: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_system(self) -> bool:
        """Backwards compatibility field - True if origin is 'builtin'."""
        return self.origin == "builtin"
