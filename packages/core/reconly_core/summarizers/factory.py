"""Summarizer factory with intelligent fallback logic."""
import os
from typing import Optional, Dict, List, TYPE_CHECKING, Any

import structlog

from reconly_core.resilience.config import RetryConfig
from reconly_core.resilience.errors import ErrorCategory
from reconly_core.resilience.retry import retry_with_result
from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.summarizers.registry import get_provider, list_providers, is_provider_registered

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

# Import providers to ensure they're registered
from reconly_core.summarizers.anthropic import AnthropicSummarizer
from reconly_core.summarizers.huggingface import HuggingFaceSummarizer
from reconly_core.summarizers.ollama import OllamaSummarizer
from reconly_core.summarizers.openai_provider import OpenAISummarizer


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
        primary_summarizer: BaseSummarizer,
        fallback_chain: List[BaseSummarizer],
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
        summarizer: BaseSummarizer,
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


def _build_intelligent_fallback_chain(
    primary_provider: str,
    exclude_model: Optional[str] = None
) -> List[BaseSummarizer]:
    """
    Build intelligent fallback chain prioritizing local/free providers over paid ones.

    Priority order:
    1. Local providers (is_local=True) - Ollama
    2. Free cloud providers (cost_free=True) - HuggingFace
    3. Paid cloud providers (sorted by cost) - OpenAI, Anthropic

    Args:
        primary_provider: Name of primary provider (excluded from fallback)
        exclude_model: For HuggingFace, which model to exclude (already primary)

    Returns:
        List of initialized provider instances for fallback chain
    """
    fallback_chain = []

    # Get all registered providers
    all_providers = list_providers()

    # Categorize providers by priority
    local_providers = []
    free_providers = []
    paid_providers = []

    for provider_name in all_providers:
        if provider_name == primary_provider:
            continue  # Skip primary provider

        try:
            provider_class = get_provider(provider_name)
            caps = provider_class.get_capabilities()

            # Categorize by cost and locality
            if caps.is_local:
                local_providers.append((provider_name, caps))
            elif caps.is_free():
                free_providers.append((provider_name, caps))
            else:
                # For paid providers, store cost for sorting
                avg_cost = (caps.cost_per_1k_input or 0) + (caps.cost_per_1k_output or 0)
                paid_providers.append((provider_name, caps, avg_cost))
        except:
            continue  # Skip providers we can't get capabilities for

    # Sort paid providers by cost (cheapest first)
    paid_providers.sort(key=lambda x: x[2])

    # Build fallback chain in priority order
    priority_order = []
    priority_order.extend([(name, caps) for name, caps in local_providers])
    priority_order.extend([(name, caps) for name, caps in free_providers])
    priority_order.extend([(name, caps, cost) for name, caps, cost in paid_providers])

    # Try to initialize each provider in priority order
    for item in priority_order:
        provider_name = item[0]

        try:
            provider_class = get_provider(provider_name)

            # Special handling for providers with specific initialization
            if provider_name == 'huggingface':
                # Add multiple HuggingFace models as separate fallbacks
                hf_api_key = os.getenv('HUGGINGFACE_API_KEY')
                if hf_api_key:
                    hf_models = ['glm-4', 'mixtral', 'llama', 'mistral']
                    for hf_model in hf_models:
                        if hf_model != exclude_model:
                            try:
                                fallback_chain.append(
                                    provider_class(api_key=hf_api_key, model=hf_model)
                                )
                            except:
                                pass  # Skip if can't initialize this model

            elif provider_name == 'anthropic':
                anthropic_key = os.getenv('ANTHROPIC_API_KEY')
                if anthropic_key:
                    fallback_chain.append(provider_class(api_key=anthropic_key))

            elif provider_name == 'openai':
                openai_key = os.getenv('OPENAI_API_KEY')
                if openai_key:
                    fallback_chain.append(provider_class(api_key=openai_key))

            elif provider_name == 'ollama':
                # Ollama doesn't require API key, try to initialize
                try:
                    ollama_instance = provider_class()
                    # Only add if Ollama server is actually available
                    if ollama_instance.is_available():
                        fallback_chain.append(ollama_instance)
                except:
                    pass  # Skip if Ollama not available

            else:
                # Generic provider initialization
                try:
                    fallback_chain.append(provider_class())
                except TypeError:
                    # Try with empty api_key
                    try:
                        fallback_chain.append(provider_class(api_key=None))
                    except:
                        pass  # Skip if can't initialize

        except Exception:
            continue  # Skip providers that fail to initialize

    return fallback_chain


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
) -> BaseSummarizer:
    """
    Get a summarizer instance with optional intelligent fallback chain.

    Intelligent fallback order (if enabled):
    1. Local providers (Ollama) - $0 cost, privacy-focused
    2. Free cloud providers (HuggingFace) - Free tier available
    3. Paid cloud providers (OpenAI, Anthropic) - Sorted by cost

    Args:
        provider: Provider name (e.g., 'huggingface', 'anthropic', 'ollama', 'openai')
                 If None, reads from SettingsService or DEFAULT_PROVIDER env var
        api_key: API key (provider-specific)
        model: Model identifier for HuggingFace (default: 'glm-4')
        enable_fallback: Enable automatic fallback to other providers
        db: Optional database session for reading settings from DB

    Returns:
        BaseSummarizer instance (possibly with fallback wrapper)
    """
    # Get provider from settings (DB > env > default)
    if provider is None:
        provider = _get_setting_with_db_fallback(
            "llm.default_provider",
            db=db,
            env_var="DEFAULT_PROVIDER",
            default="ollama"
        )

    # Validate provider is registered
    if not is_provider_registered(provider):
        available = list_providers()
        raise ValueError(
            f"Unknown provider: {provider}. Available providers: {available}. "
            f"See docs/ADDING_PROVIDERS.md for information on adding new providers."
        )

    # Get model from settings if not specified
    if model is None:
        model = _get_setting_with_db_fallback(
            "llm.default_model",
            db=db,
            env_var="DEFAULT_MODEL",
            default="llama3.2" if provider == "ollama" else "glm-4"
        )

    # Get provider class from registry
    provider_class = get_provider(provider)

    # Initialize primary provider based on type
    primary = None

    if provider == 'huggingface':
        primary = provider_class(api_key=api_key, model=model or 'glm-4')
    elif provider == 'anthropic':
        primary = provider_class(api_key=api_key)
    elif provider == 'openai':
        primary = provider_class(api_key=api_key)
    elif provider == 'ollama':
        # Ollama doesn't need API key
        try:
            primary = provider_class(api_key=None, model=model)
        except TypeError:
            primary = provider_class()
    else:
        # Generic provider initialization
        try:
            primary = provider_class(api_key=api_key)
        except TypeError:
            # Try without api_key for local providers
            primary = provider_class()

    # If fallback disabled, return primary only
    if not enable_fallback:
        return primary

    # Build intelligent fallback chain
    exclude_model = model if provider == 'huggingface' else None
    fallback_chain = _build_intelligent_fallback_chain(provider, exclude_model)

    # If we have fallbacks, wrap with fallback logic
    if fallback_chain:
        return SummarizerWithFallback(primary, fallback_chain)
    else:
        return primary


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
                models[provider_name] = list(HuggingFaceSummarizer.AVAILABLE_MODELS.keys())
            elif provider_name == 'anthropic':
                # Use dynamic list_models() which fetches from API with fallback
                models[provider_name] = [m.id for m in AnthropicSummarizer.list_models()]
            elif provider_name == 'openai':
                models[provider_name] = list(OpenAISummarizer.MODEL_PRICING.keys())
            elif provider_name == 'ollama':
                # Try to fetch available models from Ollama server
                try:
                    ollama_instance = OllamaSummarizer()
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
