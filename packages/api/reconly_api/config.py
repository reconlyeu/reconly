"""Backend configuration management."""
from enum import Enum
from pathlib import Path
from typing import Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find project root .env file
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent  # packages/api/reconly_api -> reconly-oss
_ENV_FILE = _PROJECT_ROOT / ".env"


class Edition(str, Enum):
    """Reconly edition types."""
    OSS = "oss"
    ENTERPRISE = "enterprise"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        case_sensitive=False,
        extra="ignore",
    )

    # Edition & Auth
    reconly_edition: str = "oss"
    reconly_auth_password: Optional[str] = None

    # Application
    app_name: str = "Reconly API"
    app_version: str = "0.1.0"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://reconly:reconly@localhost:5432/reconly"

    # LLM Providers (defaults are fallbacks if not in .env)
    default_provider: str = "huggingface"
    default_model: str = "llama-3.3-70b"
    default_language: str = "en"

    # API Keys (loaded from environment)
    anthropic_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days (changed from 30 minutes)

    # CORS - use str type and parse in validator to avoid JSON parsing issues
    cors_origins: Union[str, list[str]] = "http://localhost:3000,http://localhost:8080"

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Scheduler: Uses APScheduler for feed scheduling (no external dependencies)
    scheduler_timezone: Optional[str] = None  # None = local timezone, or e.g. "Europe/Berlin"

    # Email (SMTP)
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: str = "noreply@reconly.com"
    smtp_from_name: str = "Reconly"

    # Author info for bundle exports
    author_name: str = "Anonymous"
    author_github: Optional[str] = None
    author_email: Optional[str] = None

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    @field_validator('reconly_edition', mode='before')
    @classmethod
    def validate_edition(cls, v):
        """Validate and normalize edition value."""
        if v is None:
            return "oss"
        v = str(v).lower()
        if v not in ("oss", "enterprise"):
            import warnings
            warnings.warn(f"Invalid RECONLY_EDITION '{v}', defaulting to 'oss'")
            return "oss"
        return v

    @property
    def is_enterprise(self) -> bool:
        """Check if running in enterprise mode."""
        return self.reconly_edition == "enterprise"

    @property
    def is_oss(self) -> bool:
        """Check if running in OSS mode."""
        return self.reconly_edition == "oss"

    @property
    def auth_required(self) -> bool:
        """Check if authentication is required (password is set)."""
        return bool(self.reconly_auth_password)


# Global settings instance
settings = Settings()
