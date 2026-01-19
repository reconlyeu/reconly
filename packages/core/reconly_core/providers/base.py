"""Base LLM provider interface.

This module defines the abstract base class for all LLM providers.

Edition Notes:
    - OSS edition: Cost estimation methods return 0.0 (stubbed)
    - Enterprise edition: Extends these classes to provide actual cost calculations
    - Token tracking (tokens_in, tokens_out) is available in both editions
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Union

from reconly_core.config_types import ProviderConfigSchema
from reconly_core.resilience.config import RetryConfig
from reconly_core.resilience.errors import ErrorCategory, classify_error
from reconly_core.providers.capabilities import ProviderCapabilities, ModelInfo


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement all abstract methods. In OSS edition, cost-related
    methods return 0.0. Enterprise edition extends these classes to provide
    actual cost calculations based on provider pricing.

    Extension Point:
        Enterprise edition can override estimate_cost() and get_capabilities()
        to provide real pricing data without modifying the OSS codebase.

    Class Attributes:
        description: Human-readable description of this provider for UI display.
                     Subclasses should override this with a provider-specific description.
    """

    # Human-readable description of this provider
    description: str = "LLM provider"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the provider.

        Args:
            api_key: API key for the service (if required)
        """
        self.api_key = api_key

    @abstractmethod
    def summarize(
        self,
        content_data: Dict[str, str],
        language: str = 'de',
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Summarize content.

        Args:
            content_data: Dictionary with content information (from fetchers).
                         Must contain 'content' key, optionally 'title', 'source_type', 'url'.
            language: Target language for summary (default: 'de')
            system_prompt: System prompt for the LLM. If None, summarizer must have a default.
            user_prompt: User prompt with content filled in. If None, summarizer builds from content_data.

        Returns:
            Dictionary with original data plus 'summary' key
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.

        Returns:
            Provider name (e.g., 'anthropic', 'huggingface-glm4')
        """
        pass

    @abstractmethod
    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate the cost for summarizing content of given length.

        OSS Edition:
            Returns 0.0 for all providers. Cost tracking is disabled.

        Enterprise Edition:
            Returns estimated cost based on provider pricing.
            Enterprise extends these classes to provide actual calculations.

        Args:
            content_length: Length of content in characters

        Returns:
            Estimated cost in USD (0.0 in OSS edition)
        """
        pass

    def get_model_info(self) -> Dict[str, str]:
        """
        Get information about the model being used.

        Returns:
            Dictionary with model information
        """
        return {
            'provider': self.get_provider_name(),
            'model': 'unknown'
        }

    @staticmethod
    def extract_title_from_summary(summary: str) -> Optional[str]:
        """
        Extract translated title from LLM output.

        Looks for patterns like:
        - **Title:** Some title here
        - **Titel:** Ein Titel hier
        - Title: Some title here
        - English Title: Some title here

        Args:
            summary: The LLM-generated summary text

        Returns:
            Extracted title or None if not found
        """
        import re

        # Pattern 1: **Title:** or **Titel:** (markdown bold with colon inside)
        match = re.search(r'^\*\*(?:Title|Titel):\*\*\s*(.+?)$', summary, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'^\[(.+)\]$', r'\1', title)
            if title and not title.startswith('['):
                return title

        # Pattern 2: **Title**: or **Titel**: (markdown bold with colon outside)
        match = re.search(r'^\*\*(?:Title|Titel)\*\*:\s*(.+?)$', summary, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'^\[(.+)\]$', r'\1', title)
            if title and not title.startswith('['):
                return title

        # Pattern 3: Plain "Title:" or "English Title:" at start of line
        match = re.search(r'^(?:English\s+)?(?:Title|Titel):\s*(.+?)$', summary, re.MULTILINE | re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'^\[(.+)\]$', r'\1', title)
            if title and not title.startswith('['):
                return title

        return None

    @classmethod
    @abstractmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """
        Get provider capabilities for runtime feature discovery.

        OSS Edition:
            cost_per_1k_input and cost_per_1k_output are always 0.0.

        Enterprise Edition:
            Extends to provide actual pricing in cost fields.

        Returns:
            ProviderCapabilities instance describing this provider's features

        Example:
            >>> class MyProvider(BaseProvider):
            >>>     @classmethod
            >>>     def get_capabilities(cls):
            >>>         return ProviderCapabilities(
            >>>             is_local=True,
            >>>             requires_api_key=False,
            >>>             cost_per_1k_input=0.0,  # OSS stub
            >>>             cost_per_1k_output=0.0  # OSS stub
            >>>         )
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is currently available (API key set, server reachable, etc.).

        This method should not raise exceptions - return False if provider is unavailable.

        Returns:
            True if provider can process requests, False otherwise

        Example:
            >>> def is_available(self):
            >>>     if not self.api_key:
            >>>         return False
            >>>     try:
            >>>         # Check if API is reachable
            >>>         response = requests.get(f"{self.base_url}/health", timeout=2)
            >>>         return response.status_code == 200
            >>>     except:
            >>>         return False
        """
        pass

    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate provider configuration and return list of errors.

        Returns:
            List of error strings (empty list if configuration is valid)

        Example:
            >>> def validate_config(self):
            >>>     errors = []
            >>>     if not self.api_key:
            >>>         errors.append("API key is required but not set")
            >>>     if not self.base_url.startswith('http'):
            >>>         errors.append("Base URL must start with http:// or https://")
            >>>     return errors
        """
        pass

    def get_config_schema(self) -> ProviderConfigSchema:
        """
        Get the configuration schema for this provider.

        Override this method in subclasses to declare configurable settings.
        The default implementation returns an empty schema with no fields.

        Returns:
            ProviderConfigSchema with field definitions

        Example:
            >>> def get_config_schema(self):
            >>>     from reconly_core.config_types import ConfigField
            >>>     return ProviderConfigSchema(
            >>>         fields=[
            >>>             ConfigField(
            >>>                 key="api_key",
            >>>                 type="string",
            >>>                 label="API Key",
            >>>                 description="API key for authentication",
            >>>                 env_var="MY_API_KEY",
            >>>                 editable=False,
            >>>                 secret=True,
            >>>             ),
            >>>         ],
            >>>         requires_api_key=True,
            >>>     )
        """
        return ProviderConfigSchema(fields=[], requires_api_key=False)

    def classify_error(self, error: Union[Exception, int, str]) -> ErrorCategory:
        """
        Classify an error to determine retry behavior.

        This method classifies errors as TRANSIENT (retryable), PERMANENT (not retryable),
        or CONFIGURATION (fix config before retry). Providers can override this method
        to add provider-specific error classification logic.

        Args:
            error: The error to classify. Can be an Exception, HTTP status code, or message string.

        Returns:
            ErrorCategory indicating how to handle the error

        Example:
            >>> error = Exception("Rate limit exceeded")
            >>> category = summarizer.classify_error(error)
            >>> if category == ErrorCategory.TRANSIENT:
            ...     # Retry with backoff
            ...     pass
        """
        return classify_error(error)

    def get_retry_config(self) -> RetryConfig:
        """
        Get the retry configuration for this provider.

        Returns default retry settings. Providers can override this method
        to customize retry behavior (e.g., longer timeouts for local providers).

        Returns:
            RetryConfig with retry settings for this provider

        Example:
            >>> config = summarizer.get_retry_config()
            >>> print(f"Max attempts: {config.max_attempts}")
        """
        return RetryConfig.from_env()

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        List available models for this provider.

        This is a class method that can be called without instantiation to
        discover available models. Implementations should handle API failures
        gracefully and return a fallback list if the API is unavailable.

        Args:
            api_key: Optional API key for providers that require auth to list models

        Returns:
            List of ModelInfo objects for available models

        Note:
            Default implementation returns empty list. Providers should override
            to return their available models.
        """
        return []

    def summarize_with_prompt(
        self,
        content: str,
        system_prompt: str,
        title: str,
        url: str,
        language: str = 'de'
    ) -> Dict[str, str]:
        """
        Summarize content using a custom prompt (for consolidated digests).

        This is an optional method used by the consolidated digest feature.
        Default implementation falls back to regular summarize() by constructing
        a content_data dict. Providers can override for more efficient handling.

        Args:
            content: The content to summarize (usually a formatted multi-article prompt)
            system_prompt: Custom system prompt for the LLM
            title: Title for the resulting digest
            url: URL for the resulting digest (synthetic for consolidated)
            language: Target language for summary (default: 'de')

        Returns:
            Dictionary with summarization result including 'summary', 'title', 'url', etc.
        """
        # Default implementation: delegate to summarize() with prompts
        content_data = {
            'title': title,
            'content': content,
            'url': url,
            'source_type': 'consolidated',
        }
        # Pass the content as user_prompt since it's already formatted
        result = self.summarize(
            content_data,
            language=language,
            system_prompt=system_prompt,
            user_prompt=content,
        )
        # Ensure url is set correctly
        result['url'] = url
        return result


# Backwards compatibility alias
BaseSummarizer = BaseProvider
