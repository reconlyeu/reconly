"""Provider factory with fallback chain from settings."""
import os
import time
from typing import Optional, Dict, List, TYPE_CHECKING, Any

import structlog

from reconly_core.resilience.config import RetryConfig
from reconly_core.resilience.errors import ErrorCategory
from reconly_core.resilience.retry import retry_with_result
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.registry import get_provider, list_providers, is_provider_registered

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

# Import providers to ensure they're registered (side-effect imports)
from reconly_core.providers.anthropic import AnthropicProvider  # noqa: F401
from reconly_core.providers.huggingface import HuggingFaceProvider  # noqa: F401
from reconly_core.providers.lmstudio import LMStudioProvider  # noqa: F401
from reconly_core.providers.ollama import OllamaProvider  # noqa: F401
from reconly_core.providers.openai_provider import OpenAIProvider  # noqa: F401


class SummarizerWithFallback:
    """Wrapper that implements fallback logic across multiple providers with retry support.

    This class wraps multiple summarizers and provides:
    - Automatic retry with exponential backoff for transient errors
    - Fallback to next provider when a provider fails permanently
    - Re-checking provider availability before each fallback attempt
    - Detailed retry/fallback metadata in results
    """

    def __init__(
        self,
        primary_summarizer: BaseProvider,
        fallback_chain: List[BaseProvider],
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize summarizer with fallback chain.

        Args:
            primary_summarizer: Primary summarizer to use
            fallback_chain: List of fallback summarizers (in order)
            retry_config: Retry configuration (uses defaults from env if None)
        """
        self.primary = primary_summarizer
        self.fallbacks = fallback_chain
        self.all_summarizers = [primary_summarizer] + fallback_chain
        self.retry_config = retry_config or RetryConfig.from_env()

    def _attempt_summarize(
        self,
        summarizer: BaseProvider,
        content_data: Dict[str, str],
        language: str,
        system_prompt: Optional[str],
        user_prompt: Optional[str],
    ) -> Dict[str, str]:
        """Attempt to summarize with a single provider (for retry wrapper).

        This method is designed to be called by retry_with_result.
        """
        return summarizer.summarize(
            content_data,
            language,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def summarize(
        self,
        content_data: Dict[str, str],
        language: str = 'de',
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Summarize content with automatic retry and fallback.

        Each provider is first retried according to RetryConfig for transient errors.
        If all retries fail or error is non-transient, moves to next fallback provider.
        Provider availability is re-checked before each fallback attempt.

        Args:
            content_data: Content to summarize
            language: Target language
            system_prompt: Optional system prompt for the LLM
            user_prompt: Optional user prompt with content filled in

        Returns:
            Summarized content with metadata including:
                - fallback_used: bool
                - fallback_level: int (0 = primary, 1+ = fallback)
                - retry_metadata: dict with retry details
                - provider_name: str of the successful provider
        """
        last_error: Optional[Exception] = None
        last_error_category: Optional[ErrorCategory] = None
        fallback_reasons: List[Dict[str, Any]] = []

        for idx, summarizer in enumerate(self.all_summarizers):
            provider_name = summarizer.get_provider_name()

            # Re-check availability before attempting (except for primary)
            if idx > 0:
                if not summarizer.is_available():
                    reason = f"Provider {provider_name} is not available"
                    fallback_reasons.append({
                        "provider": provider_name,
                        "reason": "not_available",
                        "detail": reason,
                    })
                    logger.info(
                        "fallback_skip_unavailable",
                        provider=provider_name,
                        fallback_level=idx,
                    )
                    continue

            # Debug: log content size to correlate with timing
            content_len = len(content_data.get('content', '')) if content_data else 0
            title = content_data.get('title', 'Unknown')[:50] if content_data else 'Unknown'

            logger.info(
                "summarize_attempt",
                provider=provider_name,
                fallback_level=idx,
                is_fallback=idx > 0,
                content_chars=content_len,
                title=title,
            )

            # Get provider-specific retry config
            provider_retry_config = summarizer.get_retry_config()

            # Track timing
            start_time = time.time()

            # Use retry_with_result for detailed metadata
            retry_result = retry_with_result(
                func=self._attempt_summarize,
                args=(summarizer, content_data, language, system_prompt, user_prompt),
                config=provider_retry_config,
                classifier=summarizer.classify_error,
            )

            duration_sec = time.time() - start_time

            if retry_result["success"]:
                result = retry_result["result"]

                # Add fallback and retry metadata
                result['fallback_used'] = idx > 0
                result['fallback_level'] = idx
                result['provider_name'] = provider_name
                result['retry_metadata'] = {
                    "attempts": retry_result["attempts"],
                    "retry_delays": retry_result["retry_delays"],
                    "fallback_reasons": fallback_reasons if idx > 0 else [],
                }

                logger.info(
                    "summarize_success",
                    provider=provider_name,
                    fallback_level=idx,
                    retry_attempts=retry_result["attempts"],
                    duration_sec=round(duration_sec, 1),
                    content_chars=content_len,
                )

                return result

            # Provider failed - record reason and try next
            last_error = retry_result["error"]
            last_error_category = retry_result["error_category"]

            fallback_reasons.append({
                "provider": provider_name,
                "reason": last_error_category.value if last_error_category else "unknown",
                "error": str(last_error),
                "attempts": retry_result["attempts"],
            })

            logger.warning(
                "summarize_failed",
                provider=provider_name,
                fallback_level=idx,
                error=str(last_error),
                error_category=last_error_category.value if last_error_category else None,
                retry_attempts=retry_result["attempts"],
            )

            # If this is not the last option, continue to next
            if idx < len(self.all_summarizers) - 1:
                logger.info(
                    "fallback_to_next",
                    from_provider=provider_name,
                    next_provider=self.all_summarizers[idx + 1].get_provider_name(),
                )
                continue

        # All providers exhausted
        logger.error(
            "all_providers_failed",
            total_providers=len(self.all_summarizers),
            fallback_reasons=fallback_reasons,
        )

        error_detail = (
            f"All {len(self.all_summarizers)} summarization providers failed. "
            f"Last error ({last_error_category.value if last_error_category else 'unknown'}): "
            f"{str(last_error)}"
        )
        raise Exception(error_detail)

    def get_provider_name(self) -> str:
        """Get primary provider name."""
        return self.primary.get_provider_name()

    def estimate_cost(self, content_length: int) -> float:
        """Estimate cost using primary provider."""
        return self.primary.estimate_cost(content_length)

    def get_model_info(self) -> Dict[str, str]:
        """Get primary model info."""
        return self.primary.get_model_info()

    def classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error using primary provider's classification."""
        return self.primary.classify_error(error)

    def get_retry_config(self) -> RetryConfig:
        """Get retry configuration."""
        return self.retry_config


def _instantiate_provider(
    provider_name: str,
    db: Optional["Session"] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseProvider:
    """
    Instantiate a provider using provider metadata for configuration.

    Uses ProviderMetadata to determine:
    - API key environment variable (metadata.get_api_key())
    - Base URL configuration (metadata.get_base_url())
    - Timeout settings (metadata.get_timeout())

    Also reads from settings service:
    - provider.{name}.model - Default model override
    - provider.{name}.base_url - Base URL override

    Args:
        provider_name: Name of the provider (e.g., 'ollama', 'openai')
        db: Optional database session for reading settings
        api_key: Optional API key override
        model: Optional model override

    Returns:
        Initialized provider instance

    Raises:
        ValueError: If provider is not registered
        Exception: If provider cannot be instantiated
    """
    if not is_provider_registered(provider_name):
        available = list_providers()
        raise ValueError(
            f"Unknown provider: {provider_name}. Available providers: {available}. "
            f"See docs/ADDING_PROVIDERS.md for information on adding new providers."
        )

    # Get provider class from registry
    provider_class = get_provider(provider_name)

    # Get provider metadata for configuration
    try:
        metadata = provider_class.get_metadata()
    except (AttributeError, NotImplementedError):
        # Fallback for providers without metadata - use legacy behavior
        metadata = None

    # Read provider-specific model from settings if not overridden
    if model is None:
        model = _get_setting_with_db_fallback(
            f"provider.{provider_name}.model",
            db=db,
            env_var=None,
            default=None,
        )

    # Get API key using metadata or fallback to legacy method
    if api_key is None:
        if metadata:
            api_key = metadata.get_api_key()
        else:
            api_key = _get_api_key_for_provider(provider_name)

    # Build initialization kwargs based on metadata
    init_kwargs: Dict[str, Any] = {}

    # Add API key if provider requires it
    if metadata:
        if metadata.requires_api_key or api_key:
            init_kwargs['api_key'] = api_key
        else:
            init_kwargs['api_key'] = None
    else:
        init_kwargs['api_key'] = api_key

    # Add model if provided
    if model:
        init_kwargs['model'] = model

    # Handle base_url for local providers or providers with configurable endpoints
    if metadata and metadata.base_url_env_var:
        # Get base_url from settings first, then fallback to metadata
        base_url = _get_setting_with_db_fallback(
            f"provider.{provider_name}.base_url",
            db=db,
            env_var=metadata.base_url_env_var,
            default=metadata.base_url_default,
        )
        if base_url:
            init_kwargs['base_url'] = base_url

    # Handle timeout from metadata
    if metadata:
        timeout = metadata.get_timeout()
        if timeout != metadata.timeout_default:  # Only pass if customized via env
            init_kwargs['timeout'] = timeout

    # Handle max_content_chars for local providers
    # Read provider-specific setting, pass to constructor if set
    max_content_chars = _get_setting_with_db_fallback(
        f"provider.{provider_name}.max_content_chars",
        db=db,
        env_var=f"{provider_name.upper()}_MAX_CONTENT_CHARS",
        default=None,
    )
    if max_content_chars is not None:
        try:
            init_kwargs['max_content_chars'] = int(max_content_chars)
        except (ValueError, TypeError):
            pass  # Skip if not a valid integer

    # Instantiate provider with kwargs
    try:
        return provider_class(**init_kwargs)
    except TypeError as e:
        # Handle providers that don't accept all kwargs
        # Try progressively simpler initializations
        logger.debug(
            "provider_init_fallback",
            provider=provider_name,
            error=str(e),
            kwargs=list(init_kwargs.keys()),
        )

        # Try without timeout
        if 'timeout' in init_kwargs:
            del init_kwargs['timeout']
            try:
                return provider_class(**init_kwargs)
            except TypeError:
                pass

        # Try without max_content_chars
        if 'max_content_chars' in init_kwargs:
            del init_kwargs['max_content_chars']
            try:
                return provider_class(**init_kwargs)
            except TypeError:
                pass

        # Try without base_url
        if 'base_url' in init_kwargs:
            del init_kwargs['base_url']
            try:
                return provider_class(**init_kwargs)
            except TypeError:
                pass

        # Try with just api_key and model
        try:
            return provider_class(api_key=api_key, model=model)
        except TypeError:
            pass

        # Try with just api_key
        try:
            return provider_class(api_key=api_key)
        except TypeError:
            pass

        # Last resort: no arguments
        return provider_class()


def get_api_key_for_provider(provider_name: str) -> Optional[str]:
    """
    Get API key for a provider using provider metadata.

    Uses the provider's metadata.get_api_key() method which reads from the
    configured environment variable (metadata.api_key_env_var).

    Falls back to a hardcoded map for providers without metadata.

    Args:
        provider_name: Name of the provider (e.g., 'openai', 'anthropic', 'huggingface')

    Returns:
        API key if found, None otherwise
    """
    # Try to get API key from provider metadata
    if is_provider_registered(provider_name):
        try:
            provider_class = get_provider(provider_name)
            metadata = provider_class.get_metadata()
            return metadata.get_api_key()
        except (AttributeError, NotImplementedError):
            pass

    # Fallback: hardcoded map for providers without metadata
    env_var_map = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'huggingface': 'HUGGINGFACE_API_KEY',
    }
    env_var = env_var_map.get(provider_name)
    if env_var:
        return os.getenv(env_var)
    return None


# Internal alias for backwards compatibility within this module
_get_api_key_for_provider = get_api_key_for_provider


def _get_setting_with_db_fallback(
    key: str,
    db: Optional["Session"] = None,
    env_var: Optional[str] = None,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Get a setting value using priority: DB > env > default.

    Args:
        key: Setting key for SettingsService
        db: Optional database session
        env_var: Environment variable name
        default: Default value

    Returns:
        The effective value
    """
    # Priority 1: Database via SettingsService
    if db is not None:
        try:
            from reconly_core.services.settings_service import SettingsService
            service = SettingsService(db)
            # Use get_raw() for provider settings since they may be dynamically
            # registered and not always in SETTINGS_REGISTRY at lookup time.
            # This prevents KeyError from being silently swallowed.
            if key.startswith("provider."):
                value = service.get_raw(key)
            else:
                value = service.get(key)
            if value is not None:
                return value
        except KeyError:
            # Key not in registry - log and fall through
            logger.debug("setting_not_in_registry", key=key)
        except Exception as e:
            # Other errors - log and fall through to env var
            logger.debug("setting_lookup_failed", key=key, error=str(e))

    # Priority 2: Environment variable
    if env_var:
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value

    # Priority 3: Default
    return default


def get_summarizer(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    enable_fallback: bool = True,
    db: Optional["Session"] = None
) -> BaseProvider:
    """
    Get a summarizer instance with fallback chain from settings.

    The fallback chain is configured via the `llm.fallback_chain` setting.
    Position 0 in the chain is the default provider when no explicit provider is given.

    Args:
        provider: Provider name (e.g., 'huggingface', 'anthropic', 'ollama', 'openai')
                 If None, uses first provider in fallback chain
        api_key: API key override (provider-specific)
        model: Model override (reads from provider.{name}.model if not specified)
        enable_fallback: Enable automatic fallback to other providers in chain
        db: Optional database session for reading settings from DB

    Returns:
        BaseProvider instance (possibly with fallback wrapper)
    """
    # Get fallback chain from settings
    chain = _get_fallback_chain(db)

    # Position 0 = default provider (or explicit override)
    primary_name = provider or (chain[0] if chain else "ollama")

    # Instantiate primary provider with any overrides
    primary = _instantiate_provider(
        primary_name,
        db=db,
        api_key=api_key,
        model=model,
    )

    # If fallback disabled, return primary only
    if not enable_fallback:
        return primary

    # Build fallback chain from remaining providers in settings
    fallbacks = []
    for name in chain:
        if name == primary_name:
            continue  # Skip primary provider

        try:
            instance = _instantiate_provider(name, db=db)
            # Keep in chain even if not available - checked at runtime
            fallbacks.append(instance)
            logger.debug("fallback_provider_added", provider=name)
        except Exception as e:
            # Skip providers that fail to instantiate (missing API key, etc.)
            logger.debug(
                "fallback_provider_skipped",
                provider=name,
                reason=str(e),
            )
            continue

    # If we have fallbacks, wrap with fallback logic
    if fallbacks:
        return SummarizerWithFallback(primary, fallbacks)
    else:
        return primary


def _get_default_fallback_chain() -> List[str]:
    """Get default fallback chain from settings registry (single source of truth)."""
    from reconly_core.services.settings_registry import SETTINGS_REGISTRY
    return SETTINGS_REGISTRY["llm.fallback_chain"].default.copy()


def _get_fallback_chain(db: Optional["Session"] = None) -> List[str]:
    """
    Get the fallback chain from settings.

    Args:
        db: Optional database session for reading settings

    Returns:
        List of provider names in fallback order
    """
    chain = _get_setting_with_db_fallback(
        "llm.fallback_chain",
        db=db,
        env_var=None,  # No direct env var for lists
        default=None,
    )

    if chain is None:
        return _get_default_fallback_chain()

    # Handle string values (from env or misconfigured DB)
    if isinstance(chain, str):
        try:
            import json
            chain = json.loads(chain)
        except (json.JSONDecodeError, ValueError):
            # Comma-separated fallback
            chain = [p.strip() for p in chain.split(",") if p.strip()]

    # Validate all providers in chain are registered
    valid_chain = []
    for name in chain:
        if is_provider_registered(name):
            valid_chain.append(name)
        else:
            logger.warning(
                "invalid_provider_in_chain",
                provider=name,
                message="Provider not registered, removing from chain",
            )

    return valid_chain if valid_chain else _get_default_fallback_chain()


def resolve_default_provider(
    fallback_chain: Optional[List[str]] = None,
    db: Optional["Session"] = None,
) -> Dict[str, Any]:
    """Resolve the first available provider from the fallback chain.

    Checks each provider in the fallback chain for actual availability:
    - Local providers (Ollama, LMStudio): Pings the server
    - Cloud providers (OpenAI, Anthropic, HuggingFace): Checks for API key

    This is the single source of truth for determining which provider
    will actually be used - for both display (UI) and execution (feed/chat).

    Args:
        fallback_chain: Optional explicit chain. If None, reads from settings.
        db: Optional database session for reading settings.

    Returns:
        Dict with:
            - provider: str - The resolved provider name
            - model: str | None - The default model for this provider
            - available: bool - Whether provider is available
            - fallback_used: bool - Whether we fell back from first choice
            - unavailable_providers: list[str] - Providers that were unavailable

    Example:
        >>> result = resolve_default_provider()
        >>> print(f"Using {result['provider']} with model {result['model']}")
    """
    import httpx

    # Get fallback chain from settings if not provided
    if fallback_chain is None:
        fallback_chain = _get_fallback_chain(db)

    unavailable = []

    for provider_name in fallback_chain:
        # Check provider availability
        is_available = False

        if provider_name in ("ollama",):
            # Local provider - ping the server
            try:
                base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
                is_available = response.status_code == 200
            except Exception:
                pass

        elif provider_name in ("lmstudio",):
            # Local provider - ping the server
            try:
                base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
                response = httpx.get(f"{base_url}/models", timeout=2.0)
                is_available = response.status_code == 200
            except Exception:
                pass

        elif provider_name in ("openai",):
            # Cloud provider - check for API key
            is_available = bool(os.getenv("OPENAI_API_KEY"))

        elif provider_name in ("anthropic",):
            # Cloud provider - check for API key
            is_available = bool(os.getenv("ANTHROPIC_API_KEY"))

        elif provider_name in ("huggingface",):
            # Cloud provider - check for API key
            is_available = bool(os.getenv("HUGGINGFACE_API_KEY"))

        else:
            # Unknown provider - try to instantiate and check
            try:
                instance = _instantiate_provider(provider_name, db=db)
                is_available = instance.is_available()
            except Exception:
                pass

        if is_available:
            # Found an available provider - get its default model
            # Priority: DB setting > provider-specific env var (e.g., OLLAMA_MODEL)
            model = None
            try:
                # Build provider-specific env var name (e.g., OLLAMA_MODEL, LMSTUDIO_MODEL)
                provider_model_env_var = f"{provider_name.upper()}_MODEL"
                model = _get_setting_with_db_fallback(
                    f"provider.{provider_name}.model",
                    db=db,
                    env_var=provider_model_env_var,
                    default=None,
                )
            except Exception:
                pass

            return {
                "provider": provider_name,
                "model": model,
                "available": True,
                "fallback_used": provider_name != fallback_chain[0],
                "unavailable_providers": unavailable,
            }
        else:
            unavailable.append(provider_name)

    # No providers available
    return {
        "provider": fallback_chain[0] if fallback_chain else "ollama",
        "model": None,
        "available": False,
        "fallback_used": False,
        "unavailable_providers": unavailable,
    }


def list_available_models() -> Dict[str, List[str]]:
    """
    List all available models by provider.

    Uses each provider's list_models() method which fetches from API with fallback.

    Returns:
        Dictionary mapping provider names to lists of available model IDs
    """
    models = {}

    # Get registered providers
    for provider_name in list_providers():
        try:
            # Use the registry to get provider class
            provider_cls = get_provider(provider_name)

            # Use list_models() which handles API calls and fallbacks
            model_list = provider_cls.list_models()
            models[provider_name] = [m.id for m in model_list]

        except Exception:
            continue

    return models
