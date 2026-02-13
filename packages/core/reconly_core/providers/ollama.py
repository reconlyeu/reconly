"""Ollama local LLM provider implementation."""
import os
import requests
from typing import Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.metadata import ProviderMetadata
from reconly_core.providers.registry import register_provider
from reconly_core.providers.capabilities import ProviderCapabilities, ModelInfo


@register_provider('ollama')
class OllamaProvider(BaseProvider):
    """LLM provider using local Ollama server."""

    # Human-readable description for UI
    description = "Local LLM via Ollama server"

    # Provider metadata
    metadata = ProviderMetadata(
        name='ollama',
        display_name='Ollama',
        description='Local LLM via Ollama server',
        icon='simple-icons:ollama',
        is_local=True,
        requires_api_key=False,
        base_url_env_var='OLLAMA_BASE_URL',
        base_url_default='http://localhost:11434',
        timeout_env_var='PROVIDER_TIMEOUT_OLLAMA',
        timeout_default=300,
        availability_endpoint='/api/tags',
    )

    # Default timeout for local Ollama models (longer since they run locally)
    DEFAULT_TIMEOUT = 900  # 15 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used, but kept for interface consistency
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_content_chars: Optional[int] = None,
    ):
        """
        Initialize the Ollama summarizer.

        Args:
            api_key: Not used (Ollama doesn't require API keys)
            model: Model name to use (e.g., 'llama3.2', 'mistral'). Auto-detected if None.
            base_url: Ollama server URL (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 900s / 15 min for local models)
                     Can be configured via PROVIDER_TIMEOUT_OLLAMA env var.
            max_content_chars: Max content length for summarization (None = use global default)
        """
        super().__init__(api_key=None)
        self.max_content_chars = max_content_chars  # Used by _truncate_content()
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

        # Timeout priority: param > env var > default
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('PROVIDER_TIMEOUT_OLLAMA')
            self.timeout = int(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT

        self.model = model or os.getenv('OLLAMA_MODEL')

        # Auto-detect available models if model not specified
        if not self.model:
            available_models = self._fetch_available_models()
            if available_models:
                self.model = available_models[0]  # Use first available model
            else:
                # Default to llama3.2 if can't fetch models
                self.model = 'llama3.2'

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'ollama'

    def get_model_info(self) -> Dict[str, str]:
        """Get model information."""
        return {
            'provider': 'ollama',
            'model': self.model,
            'base_url': self.base_url,
            'local': True
        }

    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate cost for Ollama (always $0.00 for local models).

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
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("Ollama base URL is required")

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("Ollama base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"Ollama server is not reachable at {self.base_url}. "
                "Make sure Ollama is running. Install from https://ollama.ai"
            )

        # Check if model exists
        available_models = self._fetch_available_models()
        if available_models and self.model not in available_models:
            errors.append(
                f"Model '{self.model}' is not available. "
                f"Available models: {available_models}. "
                f"Run 'ollama pull {self.model}' to download it."
            )

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for Ollama provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="base_url",
                    type="string",
                    label="Server URL",
                    description="URL of your Ollama server",
                    default="http://localhost:11434",
                    required=False,
                    env_var="OLLAMA_BASE_URL",
                    editable=True,
                    placeholder="http://localhost:11434",
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
                ConfigField(
                    key="max_content_chars",
                    type="integer",
                    label="Max Content Length",
                    description="Max chars for summarization (0 = no limit, empty = use global default)",
                    required=False,
                    env_var="OLLAMA_MAX_CONTENT_CHARS",
                    editable=True,
                ),
            ],
            requires_api_key=False,
        )

    def _fetch_available_models(self) -> List[str]:
        """
        Fetch list of available models from Ollama server.

        Returns:
            List of model names, empty list if server unreachable
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                return models
        except Exception:
            pass

        return []


    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Fetch available models from Ollama server.

        Args:
            api_key: Not used (Ollama doesn't require API keys)

        Returns:
            List of ModelInfo for installed models, empty if server unreachable
        """
        base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = []
                for i, m in enumerate(data.get('models', [])):
                    model_name = m['name']
                    param_size = m.get('details', {}).get('parameter_size')
                    models.append(ModelInfo(
                        id=model_name,
                        name=model_name,
                        provider='ollama',
                        is_default=(i == 0),  # First model is default
                        parameter_size=param_size,
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
        Summarize content using Ollama.

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

        # Truncate content using configurable limit
        content = self._truncate_content(content)

        # Use provided prompts or build fallback
        if system_prompt and user_prompt:
            prompt = f"{system_prompt}\n\n{user_prompt}"
        else:
            # Fallback: build a simple prompt from content_data
            title = content_data.get('title', 'No title')
            source_type = content_data.get('source_type', 'content')
            if language == 'de':
                prompt = f"""Du bist ein professioneller Content-Zusammenfasser.
Erstelle präzise, informative Zusammenfassungen auf Deutsch.

Fasse den folgenden Inhalt einer {source_type} zusammen.

Titel: {title}

Inhalt:
{content}

Erstelle eine prägnante Zusammenfassung mit etwa 150 Wörtern."""
            else:
                prompt = f"""You are a professional content summarizer.
Create concise, informative summaries in English.

Summarize the following content from a {source_type}.

Title: {title}

Content:
{content}

Create a concise summary of approximately 150 words."""

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_ctx": 32768,  # Ensure large context window for long content
                        "num_predict": 4096  # Allow longer outputs for consolidated digests
                    }
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                raise Exception(f"Ollama API error {response.status_code}: {response.text}")

            result_data = response.json()
            summary = result_data.get('response', '').strip()

            if not summary:
                raise Exception("Ollama returned empty response")

            # Extract token counts from Ollama response
            tokens_in = result_data.get('prompt_eval_count', 0)
            tokens_out = result_data.get('eval_count', 0)

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

        except requests.Timeout:
            raise Exception(
                f"Ollama request timed out after {self.timeout}s. "
                "Try increasing timeout or using a faster model."
            )
        except requests.ConnectionError:
            raise Exception(
                f"Could not connect to Ollama server at {self.base_url}. "
                "Make sure Ollama is running. Install from https://ollama.ai"
            )
        except Exception as e:
            raise Exception(f"Failed to generate summary with Ollama ({self.model}): {str(e)}")


# Backwards compatibility alias
OllamaSummarizer = OllamaProvider
