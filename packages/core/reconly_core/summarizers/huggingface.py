"""HuggingFace Inference API summarizer implementation."""
import os
import requests
import time
from typing import Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.summarizers.registry import register_provider
from reconly_core.summarizers.capabilities import ProviderCapabilities, ModelInfo


@register_provider('huggingface')
class HuggingFaceSummarizer(BaseSummarizer):
    """Summarizes content using HuggingFace Inference API."""

    # Available models with fallback order (key -> full HuggingFace model path)
    # Organized by capability: reasoning, general, coding, compact
    AVAILABLE_MODELS = {
        # Reasoning & Advanced Models
        'qwen-2.5-72b': 'Qwen/Qwen2.5-72B-Instruct',
        'qwen-qwq-32b': 'Qwen/QwQ-32B',
        'llama-3.3-70b': 'meta-llama/Llama-3.3-70B-Instruct',
        'deepseek-r1-70b': 'deepseek-ai/DeepSeek-R1-Distill-Llama-70B',
        # General Purpose
        'mixtral-8x7b': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
        'llama-3.1-70b': 'meta-llama/Llama-3.1-70B-Instruct',
        'gemma-2-27b': 'google/gemma-2-27b-it',
        'mistral-nemo': 'mistralai/Mistral-Nemo-Instruct-2407',
        'phi-4': 'microsoft/phi-4',
        # Efficient / Compact Models
        'qwen-2.5-7b': 'Qwen/Qwen2.5-7B-Instruct',
        'llama-3.2-3b': 'meta-llama/Llama-3.2-3B-Instruct',
        'gemma-2-9b': 'google/gemma-2-9b-it',
        'mistral-7b': 'mistralai/Mistral-7B-Instruct-v0.3',
        'phi-3.5-mini': 'microsoft/Phi-3.5-mini-instruct',
        # Coding & Technical
        'qwen-2.5-coder-32b': 'Qwen/Qwen2.5-Coder-32B-Instruct',
        'deepseek-coder-33b': 'deepseek-ai/deepseek-coder-33b-instruct',
        'codellama-70b': 'meta-llama/CodeLlama-70b-Instruct-hf',
        # Multilingual & Specialized
        'aya-expanse-32b': 'CohereForAI/aya-expanse-32b',
        'command-r': 'CohereForAI/c4ai-command-r-v01',
        'zephyr-7b': 'HuggingFaceH4/zephyr-7b-beta',
    }

    # Reverse lookup: full model path -> short key
    MODEL_PATH_TO_KEY = {v: k for k, v in AVAILABLE_MODELS.items()}

    # Default fallback order (best for summarization first)
    DEFAULT_FALLBACK_ORDER = ['qwen-2.5-72b', 'llama-3.3-70b', 'mixtral-8x7b', 'mistral-7b']

    @classmethod
    def resolve_model(cls, model: str) -> tuple[str, str]:
        """
        Resolve model identifier to (key, full_path).

        Accepts both short keys ('glm-4') and full paths ('zai-org/GLM-4.7').

        Returns:
            Tuple of (model_key, model_full_path)
        """
        # Check if it's a short key
        if model in cls.AVAILABLE_MODELS:
            return model, cls.AVAILABLE_MODELS[model]

        # Check if it's a full model path
        if model in cls.MODEL_PATH_TO_KEY:
            key = cls.MODEL_PATH_TO_KEY[model]
            return key, model

        # Unknown model - fall back to default
        return 'llama-3.3-70b', cls.AVAILABLE_MODELS['llama-3.3-70b']

    # Default timeout for cloud API calls
    DEFAULT_TIMEOUT = 120  # 2 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = 'llama-3.3-70b',
        timeout: Optional[int] = None,
    ):
        """
        Initialize the HuggingFace summarizer.

        Args:
            api_key: HuggingFace API token (if not provided, reads from HUGGINGFACE_API_KEY env var)
            model: Model identifier (default: 'llama-3.3-70b')
            timeout: Request timeout in seconds (default: 120s)
                     Can be configured via PROVIDER_TIMEOUT_HUGGINGFACE env var.
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('HUGGINGFACE_API_KEY')
        if not self.api_key:
            raise ValueError(
                "HuggingFace API key required. Set HUGGINGFACE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_key, self.model = self.resolve_model(model)

        # Timeout priority: param > env var > default
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('PROVIDER_TIMEOUT_HUGGINGFACE')
            self.timeout = int(env_timeout) if env_timeout else self.DEFAULT_TIMEOUT
        # Use new router API with OpenAI-compatible chat completions format
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "huggingface"

    def get_model_info(self) -> Dict[str, str]:
        """Get model information."""
        return {
            'provider': 'huggingface',
            'model': self.model,
            'model_key': self.model_key
        }

    def estimate_cost(self, content_length: int) -> float:
        """
        Estimate cost for HuggingFace API.

        Note: Cost estimation is stubbed in OSS edition (returns 0.0).
        HuggingFace free tier has no cost. Enterprise may track Pro tier usage.

        Args:
            content_length: Length of content in characters

        Returns:
            0.0 in OSS edition
        """
        # OSS stub - always free for HuggingFace free tier
        return 0.0

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Get provider capabilities.

        Note: Cost fields are 0.0 (HuggingFace free tier). Enterprise may track Pro usage.
        """
        return ProviderCapabilities(
            supports_streaming=False,
            supports_async=False,
            requires_api_key=True,
            is_local=False,
            max_context_tokens=4096,  # Varies by model
            cost_per_1k_input=0.0,  # OSS stub - free tier
            cost_per_1k_output=0.0  # OSS stub - free tier
        )

    def is_available(self) -> bool:
        """Check if provider is available (API key is set)."""
        return self.api_key is not None and len(self.api_key) > 0

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.api_key:
            errors.append("HuggingFace API key is required but not set. Set HUGGINGFACE_API_KEY environment variable.")

        if self.model_key not in self.AVAILABLE_MODELS:
            available = list(self.AVAILABLE_MODELS.keys()) + list(self.MODEL_PATH_TO_KEY.keys())
            errors.append(f"Unknown model '{self.model_key}'. Available: {available}")

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for HuggingFace provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="HuggingFace API token",
                    env_var="HUGGINGFACE_API_KEY",
                    editable=False,
                    secret=True,
                    required=True,
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Model",
                    description="Model to use (e.g., llama-3.3-70b, qwen-2.5-72b)",
                    default="llama-3.3-70b",
                    editable=True,
                    placeholder="llama-3.3-70b",
                ),
            ],
            requires_api_key=True,
        )

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Return available HuggingFace models.

        Note: Returns curated list of models available via HuggingFace Inference API.
        Uses short keys for display and maps to full model paths internally.

        Args:
            api_key: Not used (curated list doesn't require API)

        Returns:
            List of ModelInfo for available HuggingFace models
        """
        return [
            ModelInfo(id='llama-3.3-70b', name='Llama 3.3 70B', provider='huggingface', is_default=True),
            ModelInfo(id='qwen-2.5-72b', name='Qwen 2.5 72B', provider='huggingface'),
            ModelInfo(id='mixtral-8x7b', name='Mixtral 8x7B', provider='huggingface'),
            ModelInfo(id='mistral-7b', name='Mistral 7B', provider='huggingface'),
        ]

    def _query_api(self, payload: dict, max_retries: int = 3) -> dict:
        """
        Query the HuggingFace Inference API.

        Args:
            payload: Request payload
            max_retries: Maximum number of retries

        Returns:
            API response

        Raises:
            Exception: If request fails
        """
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    if attempt < max_retries - 1:
                        wait_time = min(20, 2 ** attempt)  # Exponential backoff
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Model loading timeout: {response.text}")
                else:
                    raise Exception(f"API error {response.status_code}: {response.text}")

            except requests.Timeout:
                if attempt < max_retries - 1:
                    continue
                raise Exception("Request timeout")
            except requests.RequestException as e:
                raise Exception(f"Request failed: {str(e)}")

        raise Exception("Max retries exceeded")

    def summarize(
        self,
        content_data: Dict[str, str],
        language: str = 'de',
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Summarize content using HuggingFace Inference API.

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

        # Truncate user prompt if too long (to fit model context)
        max_prompt_length = 3000
        if len(usr_prompt) > max_prompt_length:
            usr_prompt = usr_prompt[:max_prompt_length] + "...\n\nCreate a concise summary of approximately 150 words."

        try:
            # Query API using OpenAI-compatible chat completions format
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": usr_prompt}
                ],
                "max_tokens": 4096,  # Increased for consolidated digests
                "temperature": 0.7,
                "top_p": 0.9
            }

            response = self._query_api(payload)

            # Extract summary from chat completions response
            if isinstance(response, dict) and 'choices' in response:
                message = response['choices'][0]['message']
                # GLM-4.7 and other reasoning models use 'reasoning_content'
                summary = message.get('content', '').strip()
                if not summary and 'reasoning_content' in message:
                    summary = message['reasoning_content'].strip()
                if not summary:
                    raise Exception("Empty response from model")
            else:
                raise Exception(f"Unexpected response format: {response}")

            # Extract token counts from OpenAI-compatible response (if available)
            usage = response.get('usage', {})
            tokens_in = usage.get('prompt_tokens', 0)
            tokens_out = usage.get('completion_tokens', 0)

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
            result['estimated_cost'] = self.estimate_cost(len(content))

            return result

        except Exception as e:
            raise Exception(f"Failed to generate summary with {self.model_key}: {str(e)}")
