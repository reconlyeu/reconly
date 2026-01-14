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

# Default insecure secret key - used for validation
_DEFAULT_INSECURE_SECRET_KEY = "your-secret-key-change-in-production"


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

    # Environment (production or development)
    reconly_env: str = "development"

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
    secret_key: str = ""  # Empty default to force explicit setting
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days (changed from 30 minutes)
    secure_cookies: str = "auto"  # Cookie security: "auto" (detect from request), "true", "false"

    # Security Headers
    csp_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'"

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

    @property
    def is_production(self) -> bool:
        """Check if running in production mode.

        Returns True only if RECONLY_ENV is explicitly set to "production".
        Debug mode is independent of environment designation.
        """
        return self.reconly_env.lower() == "production"


class SecretKeyValidationError(Exception):
    """Raised when SECRET_KEY validation fails in production."""
    pass


def _mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value, showing only first and last N characters.

    Args:
        value: The secret value to mask
        visible_chars: Number of characters to show at start and end

    Returns:
        Masked string like "abcd...wxyz" or "****" if too short
    """
    if not value:
        return "(not set)"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


def _validate_cors_origins(origins: list[str]) -> list[str]:
    """Validate CORS origins format.

    Args:
        origins: List of CORS origin strings

    Returns:
        List of invalid origins (empty if all valid)
    """
    from urllib.parse import urlparse

    invalid = []
    for origin in origins:
        origin = origin.strip()
        if origin == "*":
            continue  # Wildcard is valid
        if not origin:
            continue  # Skip empty strings

        try:
            parsed = urlparse(origin)
            # Must have scheme and netloc for a valid URL
            if not parsed.scheme or not parsed.netloc:
                invalid.append(origin)
        except Exception:
            invalid.append(origin)

    return invalid


def validate_configuration(settings: "Settings", db_session_factory=None) -> dict:
    """Validate application configuration at startup.

    Performs comprehensive validation of settings and logs warnings/errors.
    Does not abort startup for most issues (except critical ones handled elsewhere).

    Args:
        settings: The application settings instance
        db_session_factory: Optional SQLAlchemy session factory for DB connection test

    Returns:
        Dict with validation results:
        {
            "database_ok": bool,
            "llm_configured": bool,
            "cors_valid": bool,
            "warnings": list[str]
        }
    """
    from reconly_core.logging import get_logger
    logger = get_logger(__name__)

    results = {
        "database_ok": False,
        "llm_configured": False,
        "cors_valid": True,
        "warnings": [],
    }

    # Log configuration summary (mask secrets)
    logger.info(
        "Configuration summary",
        edition=settings.reconly_edition,
        environment=settings.reconly_env,
        debug=settings.debug,
        database_url=_mask_secret(settings.database_url, 8),
        secret_key_length=len(settings.secret_key) if settings.secret_key else 0,
        auth_required=settings.auth_required,
        secure_cookies=settings.secure_cookies,
        rate_limit_per_minute=settings.rate_limit_per_minute,
        cors_origins_count=len(settings.cors_origins),
        anthropic_api_key=_mask_secret(settings.anthropic_api_key or "", 4),
        huggingface_api_key=_mask_secret(settings.huggingface_api_key or "", 4),
    )

    # Test database connection (warn but don't abort)
    if db_session_factory:
        try:
            from sqlalchemy import text
            with db_session_factory() as session:
                session.execute(text("SELECT 1"))
                results["database_ok"] = True
                logger.debug("Database connection test passed")
        except Exception as e:
            results["warnings"].append(f"Database connection test failed: {e}")
            logger.warning(
                "Database connection test failed",
                error=str(e),
                hint="Database may not be available yet - this is OK during startup",
            )
    else:
        logger.debug("Skipping database connection test (no session factory provided)")

    # Check LLM API keys
    has_anthropic = bool(settings.anthropic_api_key)
    has_huggingface = bool(settings.huggingface_api_key)
    results["llm_configured"] = has_anthropic or has_huggingface

    if not results["llm_configured"]:
        results["warnings"].append("No LLM API keys configured")
        logger.warning(
            "No LLM API keys configured",
            hint="Set ANTHROPIC_API_KEY or HUGGINGFACE_API_KEY for AI features",
        )
    else:
        configured_providers = []
        if has_anthropic:
            configured_providers.append("Anthropic")
        if has_huggingface:
            configured_providers.append("HuggingFace")
        logger.debug("LLM providers configured", providers=configured_providers)

    # Validate CORS origins format
    invalid_origins = _validate_cors_origins(settings.cors_origins)
    if invalid_origins:
        results["cors_valid"] = False
        results["warnings"].append(f"Invalid CORS origins: {invalid_origins}")
        logger.warning(
            "Invalid CORS origins detected",
            invalid_origins=invalid_origins,
            hint="CORS origins should be valid URLs (e.g., 'http://localhost:3000') or '*'",
        )
    else:
        logger.debug("CORS origins validation passed", count=len(settings.cors_origins))

    # Log summary of warnings
    if results["warnings"]:
        logger.info(
            "Configuration validation completed with warnings",
            warning_count=len(results["warnings"]),
        )
    else:
        logger.info("Configuration validation completed successfully")

    return results


def validate_secret_key(settings: Settings) -> None:
    """Validate the SECRET_KEY configuration.

    In production: Aborts startup if SECRET_KEY is empty, default, or < 32 chars.
    In development: Logs warnings but does not abort startup.

    Args:
        settings: The application settings instance

    Raises:
        SecretKeyValidationError: If validation fails in production
    """
    from reconly_core.logging import get_logger
    logger = get_logger(__name__)

    secret_key = settings.secret_key
    is_prod = settings.is_production
    generate_hint = 'python -c "import secrets; print(secrets.token_urlsafe(32))"'

    # Define validation checks: (condition, error_message, warning_message, extra_log_kwargs)
    checks = [
        (
            not secret_key,
            "SECRET_KEY is not set.",
            "SECRET_KEY is not set - using insecure default for development only",
            {},
        ),
        (
            secret_key == _DEFAULT_INSECURE_SECRET_KEY,
            "SECRET_KEY is set to the default insecure value.",
            "SECRET_KEY is set to the default insecure value",
            {},
        ),
        (
            secret_key and len(secret_key) < 32,
            f"SECRET_KEY is too short ({len(secret_key)} chars). Minimum is 32.",
            "SECRET_KEY is too short for production use",
            {"length": len(secret_key), "minimum": 32},
        ),
    ]

    for condition, error_msg, warning_msg, extra_kwargs in checks:
        if condition:
            if is_prod:
                raise SecretKeyValidationError(
                    f"{error_msg} Generate a secure key with: {generate_hint}"
                )
            logger.warning(warning_msg, hint=f"Generate with: {generate_hint}", **extra_kwargs)
            return

    logger.debug("SECRET_KEY validation passed", length=len(secret_key))


# Global settings instance
settings = Settings()
