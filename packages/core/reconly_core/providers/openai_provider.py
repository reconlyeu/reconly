"""OpenAI API LLM provider implementation."""
import os
from openai import OpenAI
from typing import Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.registry import register_provider
from reconly_core.providers.capabilities import ProviderCapabilities, ModelInfo


@register_provider('openai')
class OpenAIProvider(BaseProvider):
    """LLM provider using OpenAI API (GPT models)."""

    # Human-readable description for UI
    description = "OpenAI GPT models (GPT-4, GPT-4o)"

    # Model pricing (per 1M tokens) - OSS stub with zero values
    # Enterprise edition overrides with actual pricing
    MODEL_PRICING = {
        'gpt-4': (0.0, 0.0),
        'gpt-4-turbo': (0.0, 0.0),
        'gpt-3.5-turbo': (0.0, 0.0),
    }

    # Default timeout for cloud API calls
    DEFAULT_TIMEOUT = 120  # 2 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = 'gpt-4-turbo',
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize the OpenAI summarizer.

        Args:
            api_key: OpenAI API key (if not provided, reads from OPENAI_API_KEY env var)
            model: Model to use (default: 'gpt-4-turbo')
            base_url: Base URL for OpenAI-compatible endpoints (optional)
            timeout: Request timeout in seconds (default: 120s)
                     Can be configured via PROVIDER_TIMEOUT_OPENAI env var.
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')

        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.base_url = base_url or os.getenv('OPENAI_BASE_URL')

        # Timeout priority: param > env var > default
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('PROVIDER_TIMEOUT_OPENAI')
            self.timeout = int(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT

        # Initialize OpenAI client with timeout
        client_kwargs = {"api_key": self.api_key, "timeout": float(self.timeout)}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = OpenAI(**client_kwargs)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'openai'

    def get_model_info(self) -> Dict[str, str]:
        """Get model information."""
        info = {
            'provider': 'openai',
            'model': self.model
        }

        if self.base_url:
            info['base_url'] = self.base_url
            info['compatible_endpoint'] = True

        return info

    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate cost for OpenAI API based on model pricing.

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
            max_context_tokens=128_000,  # GPT-4-turbo context window
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
            errors.append("OpenAI API key is required but not set. Set OPENAI_API_KEY environment variable.")

        if not self.model:
            errors.append("Model name is required")

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("Base URL must start with http:// or https://")

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for OpenAI provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="OpenAI API key",
                    required=True,
                    env_var="OPENAI_API_KEY",
                    editable=False,
                    secret=True,
                ),
                ConfigField(
                    key="model",
                    type="select",
                    label="Default Model",
                    description="Model to use for summarization",
                    required=False,
                    editable=True,
                    options_from="models",
                ),
            ],
            requires_api_key=True,
        )

    # Fallback models when API is unavailable
    FALLBACK_MODELS = [
        ModelInfo(id='gpt-4o', name='GPT-4o', provider='openai', is_default=True),
        ModelInfo(id='gpt-4o-mini', name='GPT-4o Mini', provider='openai'),
        ModelInfo(id='gpt-4-turbo', name='GPT-4 Turbo', provider='openai'),
        ModelInfo(id='gpt-4', name='GPT-4', provider='openai'),
        ModelInfo(id='gpt-3.5-turbo', name='GPT-3.5 Turbo', provider='openai'),
    ]

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Fetch available models from OpenAI API.

        Args:
            api_key: Optional API key (uses OPENAI_API_KEY env if not provided)

        Returns:
            List of ModelInfo for chat-compatible models
        """
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return cls.FALLBACK_MODELS.copy()

        try:
            client = OpenAI(api_key=api_key)
            models_response = client.models.list()

            # Filter for chat-compatible models
            chat_prefixes = ('gpt-4', 'gpt-3.5', 'o1', 'o3')
            chat_models = []
            for m in models_response.data:
                if m.id.startswith(chat_prefixes):
                    chat_models.append(ModelInfo(
                        id=m.id,
                        name=m.id,
                        provider='openai',
                        is_default=(m.id == 'gpt-4o')
                    ))

            # Sort by model id (newest first)
            chat_models.sort(key=lambda x: x.id, reverse=True)
            return chat_models if chat_models else cls.FALLBACK_MODELS.copy()
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
        Summarize content using OpenAI API.

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
            # Call OpenAI Chat Completions API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": usr_prompt}
                ],
                max_tokens=4096,  # Increased for consolidated digests
                temperature=0.7,
                top_p=0.9
            )

            summary = response.choices[0].message.content

            # Extract token counts
            usage = response.usage
            tokens_in = usage.prompt_tokens if usage else 0
            tokens_out = usage.completion_tokens if usage else 0

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
            error_msg = str(e)

            # Provide helpful error messages
            if 'rate_limit' in error_msg.lower():
                raise Exception(
                    f"OpenAI rate limit exceeded: {error_msg}. "
                    "Wait a moment and try again, or upgrade your API plan."
                )
            elif 'authentication' in error_msg.lower() or 'api_key' in error_msg.lower():
                raise Exception(
                    f"OpenAI authentication failed: {error_msg}. "
                    "Check that your OPENAI_API_KEY is valid."
                )
            elif 'model' in error_msg.lower() and 'not found' in error_msg.lower():
                raise Exception(
                    f"Model '{self.model}' not found: {error_msg}. "
                    f"Available models: {list(self.MODEL_PRICING.keys())}"
                )
            else:
                raise Exception(f"Failed to generate summary with OpenAI ({self.model}): {error_msg}")


# Backwards compatibility alias
OpenAISummarizer = OpenAIProvider
