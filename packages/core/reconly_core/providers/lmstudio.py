"""LMStudio local LLM provider implementation.

LMStudio provides an OpenAI-compatible API at /v1/chat/completions and /v1/models.
This provider uses the OpenAI SDK with a custom base_url to communicate with LMStudio.
"""
import os
import requests
from openai import OpenAI
from typing import Any, Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.registry import register_provider
from reconly_core.providers.capabilities import ProviderCapabilities, ModelInfo


@register_provider('lmstudio')
class LMStudioProvider(BaseProvider):
    """LLM provider using local LMStudio server.

    LMStudio provides an OpenAI-compatible REST API, so this provider uses
    the OpenAI SDK with a custom base_url pointing to the local LMStudio server.
    """

    # Human-readable description for UI
    description = "Local LLM via LMStudio server"

    # Default timeout for local LMStudio models (longer since they run locally)
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used, but kept for interface consistency
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize the LMStudio provider.

        Args:
            api_key: Not used (LMStudio doesn't require API keys)
            model: Model name to use. Auto-detected if None.
            base_url: LMStudio server URL (default: http://localhost:1234/v1)
            timeout: Request timeout in seconds (default: 300s / 5 min for local models)
                     Can be configured via PROVIDER_TIMEOUT_LMSTUDIO env var.
        """
        super().__init__(api_key=None)
        self.base_url = base_url or os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')

        # Timeout priority: param > env var > default
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('PROVIDER_TIMEOUT_LMSTUDIO')
            self.timeout = int(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT

        self.model = model or os.getenv('LMSTUDIO_MODEL')

        # Auto-detect available models if model not specified
        if not self.model:
            available_models = self._fetch_available_models()
            if available_models:
                self.model = available_models[0]  # Use first available model
            else:
                # Default to empty - will fail if no model available
                self.model = None

        # Initialize OpenAI client with LMStudio base URL
        # LMStudio doesn't require an API key, but OpenAI SDK requires a non-empty value
        self.client = OpenAI(
            api_key="lm-studio",  # Dummy key - LMStudio ignores this
            base_url=self.base_url,
            timeout=float(self.timeout),
        )

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'lmstudio'

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            'provider': 'lmstudio',
            'model': self.model or 'unknown',
            'base_url': self.base_url,
            'local': True
        }

    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate cost for LMStudio (always $0.00 for local models).

        Note: Local models are always free. Cost estimation stubbed for interface consistency.

        Args:
            content_length: Length of content in characters

        Returns:
            0.0 (local models are free)
        """
        # OSS stub - local models are always free
        return 0.0

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Get provider capabilities.

        Note: Cost fields are 0.0 (local models are free).
        """
        return ProviderCapabilities(
            supports_streaming=False,
            supports_async=False,
            requires_api_key=False,
            is_local=True,
            max_context_tokens=None,  # Varies by model
            cost_per_1k_input=0.0,  # Local models are free
            cost_per_1k_output=0.0  # Local models are free
        )

    def is_available(self) -> bool:
        """Check if LMStudio server is available."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("LMStudio base URL is required")

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("LMStudio base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"LMStudio server is not reachable at {self.base_url}. "
                "Make sure LMStudio is running with the local server enabled. "
                "You can enable it from LMStudio's Developer tab."
            )

        # Check if model exists
        if self.model:
            available_models = self._fetch_available_models()
            if available_models and self.model not in available_models:
                errors.append(
                    f"Model '{self.model}' is not available. "
                    f"Available models: {available_models}. "
                    "Load the model in LMStudio before using it."
                )
        else:
            # No model specified and couldn't auto-detect
            if not self._fetch_available_models():
                errors.append(
                    "No model specified and none available. "
                    "Load a model in LMStudio before using this provider."
                )

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for LMStudio provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="base_url",
                    type="string",
                    label="Server URL",
                    description="URL of your LMStudio server",
                    default="http://localhost:1234/v1",
                    required=False,
                    env_var="LMSTUDIO_BASE_URL",
                    editable=True,
                    placeholder="http://localhost:1234/v1",
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
            requires_api_key=False,
        )

    def _fetch_available_models(self) -> List[str]:
        """
        Fetch list of available models from LMStudio server.

        Returns:
            List of model names, empty list if server unreachable
        """
        try:
            response = requests.get(f"{self.base_url}/models", timeout=2)
            if response.status_code == 200:
                data = response.json()
                # LMStudio returns OpenAI-compatible format: {"data": [{"id": "model-name", ...}]}
                models = [m['id'] for m in data.get('data', [])]
                return models
        except Exception:
            pass

        return []

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Fetch available models from LMStudio server.

        Args:
            api_key: Not used (LMStudio doesn't require API keys)

        Returns:
            List of ModelInfo for loaded models, empty if server unreachable
        """
        base_url = os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1')
        try:
            response = requests.get(f"{base_url}/models", timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = []
                for i, m in enumerate(data.get('data', [])):
                    model_id = m['id']
                    models.append(ModelInfo(
                        id=model_id,
                        name=model_id,
                        provider='lmstudio',
                        is_default=(i == 0)  # First model is default
                    ))
                return models
        except Exception:
            pass
        return []

    def summarize(
        self,
        content_data: Dict[str, str],
        language: str = 'de',
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Summarize content using LMStudio.

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

        if not self.model:
            raise ValueError(
                "No model available. Load a model in LMStudio before using this provider."
            )

        # Truncate content if too long to prevent context window overflow
        # Most models have 32k context, but we limit to ~20k tokens (~80k chars) to be safe
        MAX_CONTENT_CHARS = 80000
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS] + "\n\n[Content truncated due to length...]"

        # Use provided prompts or build fallback
        if system_prompt and user_prompt:
            sys_prompt = system_prompt
            usr_prompt = user_prompt
        else:
            # Fallback: build a simple prompt from content_data
            title = content_data.get('title', 'No title')
            source_type = content_data.get('source_type', 'content')
            if language == 'de':
                sys_prompt = (
                    "Du bist ein professioneller Content-Zusammenfasser. "
                    "Erstelle präzise, informative Zusammenfassungen auf Deutsch."
                )
                usr_prompt = (
                    f"Fasse den folgenden Inhalt einer {source_type} zusammen.\n\n"
                    f"Titel: {title}\n\n"
                    f"Inhalt:\n{content}\n\n"
                    "Erstelle eine prägnante Zusammenfassung mit etwa 150 Wörtern."
                )
            else:
                sys_prompt = (
                    "You are a professional content summarizer. "
                    "Create concise, informative summaries in English."
                )
                usr_prompt = (
                    f"Summarize the following content from a {source_type}.\n\n"
                    f"Title: {title}\n\n"
                    f"Content:\n{content}\n\n"
                    "Create a concise summary of approximately 150 words."
                )

        try:
            # Call LMStudio via OpenAI-compatible API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": usr_prompt}
                ],
                max_tokens=4096,  # Allow longer outputs for consolidated digests
                temperature=0.7,
                top_p=0.9
            )

            summary = response.choices[0].message.content or ""

            if not summary:
                raise Exception("LMStudio returned empty response")

            # Extract token counts from response
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
            result['estimated_cost'] = 0.0

            return result

        except Exception as e:
            error_msg = str(e)

            # Provide helpful error messages for common issues
            if 'connection' in error_msg.lower() or 'refused' in error_msg.lower():
                raise Exception(
                    f"Could not connect to LMStudio server at {self.base_url}. "
                    "Make sure LMStudio is running with the local server enabled."
                ) from e
            if 'timeout' in error_msg.lower():
                raise Exception(
                    f"LMStudio request timed out after {self.timeout}s. "
                    "Try increasing timeout or using a faster/smaller model."
                ) from e

            raise Exception(
                f"Failed to generate summary with LMStudio ({self.model}): {error_msg}"
            ) from e


# Backwards compatibility alias
LMStudioSummarizer = LMStudioProvider
