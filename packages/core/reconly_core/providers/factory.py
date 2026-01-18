"""Provider factory with fallback chain from settings."""
import os
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

# Default fallback chain when no setting is configured
DEFAULT_FALLBACK_CHAIN = ["ollama", "huggingface", "openai", "anthropic"]

# Import providers to ensure they're registered
from reconly_core.providers.anthropic import AnthropicProvider
from reconly_core.providers.huggingface import HuggingFaceProvider
from reconly_core.providers.ollama import OllamaProvider
from reconly_core.providers.openai_provider import OpenAIProvider


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

            logger.info(
                "summarize_attempt",
                provider=provider_name,
                fallback_level=idx,
                is_fallback=idx > 0,
            )

            # Get provider-specific retry config
            provider_retry_config = summarizer.get_retry_config()

            # Use retry_with_result for detailed metadata
            retry_result = retry_with_result(
                func=self._attempt_summarize,
                args=(summarizer, content_data, language, system_prompt, user_prompt),
                config=provider_retry_config,
                classifier=summarizer.classify_error,
            )

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
    Instantiate a provider using provider-specific settings.

    Reads configuration from:
    - llm.{provider}.model - Default model for the provider
    - llm.{provider}.base_url - Base URL (for providers like Ollama)
    - Environment variables for API keys

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

    # Read provider-specific model from settings if not overridden
    if model is None:
        model = _get_setting_with_db_fallback(
            f"provider.{provider_name}.model",
            db=db,
            env_var=None,
            default=None,
        )

    # Get API key from environment if not provided
    if api_key is None:
        api_key = _get_api_key_for_provider(provider_name)

    # Initialize provider based on type
    if provider_name == 'huggingface':
        return provider_class(api_key=api_key, model=model or 'glm-4')
    elif provider_name == 'anthropic':
        return provider_class(api_key=api_key)
    elif provider_name == 'openai':
        return provider_class(api_key=api_key)
    elif provider_name == 'ollama':
        # Ollama doesn't need API key, but may have custom base_url
        base_url = _get_setting_with_db_fallback(
            f"provider.{provider_name}.base_url",
            db=db,
            env_var="OLLAMA_BASE_URL",
            default=None,
        )
        try:
            return provider_class(api_key=None, model=model, base_url=base_url)
        except TypeError:
            # Some versions may not accept base_url
            return provider_class(api_key=None, model=model)
    else:
        # Generic provider initialization
        try:
            return provider_class(api_key=api_key, model=model)
        except TypeError:
            # Try without model if not supported
            try:
                return provider_class(api_key=api_key)
            except TypeError:
                return provider_class()


def _get_api_key_for_provider(provider_name: str) -> Optional[str]:
    """
    Get API key for a provider from environment variables.

    Args:
        provider_name: Name of the provider

    Returns:
        API key if found, None otherwise
    """
    env_var_map = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'huggingface': 'HUGGINGFACE_API_KEY',
    }
    env_var = env_var_map.get(provider_name)
    if env_var:
        return os.getenv(env_var)
    return None


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
            value = service.get(key)
            if value is not None:
                return value
        except Exception:
            pass  # Fall through to env var

    # Priority 2: Environment variable
    if env_var:
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value

    # Priority 3: Default
    return default


def get_summarizer(
    provider: str = None,
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
        return DEFAULT_FALLBACK_CHAIN.copy()

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

    return valid_chain if valid_chain else DEFAULT_FALLBACK_CHAIN.copy()


def list_available_models() -> Dict[str, List[str]]:
    """
    List all available models by provider.

    Returns:
        Dictionary mapping provider names to lists of available models
    """
    models = {}

    # Get registered providers
    for provider_name in list_providers():
        try:
            # Special handling for providers with known model lists
            if provider_name == 'huggingface':
                models[provider_name] = list(HuggingFaceProvider.AVAILABLE_MODELS.keys())
            elif provider_name == 'anthropic':
                # Use dynamic list_models() which fetches from API with fallback
                models[provider_name] = [m.id for m in AnthropicProvider.list_models()]
            elif provider_name == 'openai':
                models[provider_name] = list(OpenAIProvider.MODEL_PRICING.keys())
            elif provider_name == 'ollama':
                # Try to fetch available models from Ollama server
                try:
                    ollama_instance = OllamaProvider()
                    available = ollama_instance._fetch_available_models()
                    models[provider_name] = available if available else ['llama3.2', 'mistral', 'gemma2']
                except:
                    models[provider_name] = ['llama3.2', 'mistral', 'gemma2']
            else:
                # Generic handling for new providers
                models[provider_name] = ['default']

        except Exception:
            continue

    return models
