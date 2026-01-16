"""Anthropic Claude summarizer implementation."""
import os
from anthropic import Anthropic
from typing import Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.summarizers.registry import register_provider
from reconly_core.summarizers.capabilities import ProviderCapabilities, ModelInfo


@register_provider('anthropic')
class AnthropicSummarizer(BaseSummarizer):
    """Summarizes content using Claude AI via Anthropic API."""

    # Default timeout for cloud API calls
    DEFAULT_TIMEOUT = 120  # 2 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize the Anthropic summarizer.

        Args:
            api_key: Anthropic API key (if not provided, reads from ANTHROPIC_API_KEY env var)
            timeout: Request timeout in seconds (default: 120s)
                     Can be configured via PROVIDER_TIMEOUT_ANTHROPIC env var.
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Timeout priority: param > env var > default
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('PROVIDER_TIMEOUT_ANTHROPIC')
            self.timeout = int(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT

        self.client = Anthropic(api_key=self.api_key, timeout=float(self.timeout))
        self.model = "claude-opus-4-5-20251101"

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "anthropic"

    def get_model_info(self) -> Dict[str, str]:
        """Get model information."""
        return {
            'provider': 'anthropic',
            'model': self.model,
            'name': 'Claude Opus 4.5'
        }

    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate cost for Anthropic API.

        Note: Cost estimation is stubbed in OSS edition (returns 0.0).
        Enterprise edition overrides this with actual pricing calculations.

        Args:
            content_length: Length of content in characters

        Returns:
            0.0 in OSS edition (Enterprise: estimated cost in USD)
        """
        # OSS stub - Enterprise overrides with actual pricing
        return 0.0

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Get provider capabilities.

        Note: Cost fields are 0.0 in OSS edition. Enterprise overrides with actual pricing.
        """
        return ProviderCapabilities(
            supports_streaming=False,
            supports_async=False,
            requires_api_key=True,
            is_local=False,
            max_context_tokens=200_000,
            cost_per_1k_input=0.0,  # OSS stub - Enterprise overrides
            cost_per_1k_output=0.0  # OSS stub - Enterprise overrides
        )

    def is_available(self) -> bool:
        """Check if provider is available (API key is set)."""
        return self.api_key is not None and len(self.api_key) > 0

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.api_key:
            errors.append("Anthropic API key is required but not set. Set ANTHROPIC_API_KEY environment variable.")

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for Anthropic provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="Anthropic API key",
                    env_var="ANTHROPIC_API_KEY",
                    editable=False,
                    secret=True,
                    required=True,
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Model",
                    description="Model to use (e.g., claude-opus-4-5-20251101)",
                    default="claude-opus-4-5-20251101",
                    editable=True,
                    placeholder="claude-opus-4-5-20251101",
                ),
            ],
            requires_api_key=True,
        )

    # Fallback models when API is unavailable
    FALLBACK_MODELS = [
        ModelInfo(id='claude-sonnet-4-20250514', name='Claude Sonnet 4', provider='anthropic', is_default=True),
        ModelInfo(id='claude-3-5-sonnet-20241022', name='Claude 3.5 Sonnet', provider='anthropic'),
        ModelInfo(id='claude-3-5-haiku-20241022', name='Claude 3.5 Haiku', provider='anthropic'),
    ]

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Fetch available models from Anthropic API.

        Args:
            api_key: Optional API key (uses ANTHROPIC_API_KEY env if not provided)

        Returns:
            List of ModelInfo for available Anthropic models
        """
        if not api_key:
            api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return cls.FALLBACK_MODELS.copy()

        try:
            client = Anthropic(api_key=api_key)
            # Fetch models from API - returns most recent first
            models_response = client.models.list(limit=100)

            models = []
            for i, m in enumerate(models_response.data):
                models.append(ModelInfo(
                    id=m.id,
                    name=m.display_name,
                    provider='anthropic',
                    is_default=(i == 0)  # First model (most recent) is default
                ))

            return models if models else cls.FALLBACK_MODELS.copy()
        except Exception:
            return cls.FALLBACK_MODELS.copy()

    def summarize(
        self,
        content_data: Dict[str, str],
        language: str = 'de',
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Summarize content using Claude AI.

        Args:
            content_data: Dictionary with content information (from fetchers)
            language: Target language for summary (default: 'de')
            system_prompt: System prompt for the LLM
            user_prompt: User prompt with content filled in

        Returns:
            Dictionary with original data plus 'summary' key
        """
        content = content_data.get('content', '')

        if not content:
            raise ValueError("No content to summarize")

        # Use provided prompts or build fallback
        if system_prompt and user_prompt:
            sys_prompt = system_prompt
            usr_prompt = user_prompt
        else:
            # Fallback: build a simple prompt from content_data
            title = content_data.get('title', 'No title')
            source_type = content_data.get('source_type', 'content')
            if language == 'de':
                sys_prompt = "Du bist ein professioneller Content-Zusammenfasser. Erstelle präzise, informative Zusammenfassungen auf Deutsch."
                usr_prompt = f"Fasse den folgenden Inhalt einer {source_type} zusammen.\n\nTitel: {title}\n\nInhalt:\n{content}\n\nErstelle eine prägnante Zusammenfassung mit etwa 150 Wörtern."
            else:
                sys_prompt = "You are a professional content summarizer. Create concise, informative summaries in English."
                usr_prompt = f"Summarize the following content from a {source_type}.\n\nTitle: {title}\n\nContent:\n{content}\n\nCreate a concise summary of approximately 150 words."

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,  # Increased for consolidated digests with detailed formats
                system=sys_prompt,
                messages=[
                    {"role": "user", "content": usr_prompt}
                ]
            )

            summary = message.content[0].text

            # Extract token counts from Anthropic response
            tokens_in = message.usage.input_tokens if message.usage else 0
            tokens_out = message.usage.output_tokens if message.usage else 0

            # Return original data with summary added
            result = content_data.copy()
            result['summary'] = summary
            result['summary_language'] = language

            # Extract translated title from LLM output if present
            extracted_title = self.extract_title_from_summary(summary)
            if extracted_title:
                result['title'] = extracted_title
            result['model_info'] = {
                **self.get_model_info(),
                'input_tokens': tokens_in,
                'output_tokens': tokens_out,
            }
            # OSS stub - cost is always 0.0, Enterprise calculates actual cost
            result['estimated_cost'] = 0.0

            return result

        except Exception as e:
            raise Exception(f"Failed to generate summary with Claude: {str(e)}")
