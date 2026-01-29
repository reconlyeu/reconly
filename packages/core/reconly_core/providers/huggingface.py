"""HuggingFace Inference API LLM provider implementation."""
import logging
import os
import re
import requests
import time
from typing import Dict, List, Optional

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.metadata import ProviderMetadata
from reconly_core.providers.registry import register_provider
from reconly_core.providers.capabilities import ProviderCapabilities, ModelInfo

logger = logging.getLogger(__name__)


@register_provider('huggingface')
class HuggingFaceProvider(BaseProvider):
    """LLM provider using HuggingFace Inference API."""

    # Human-readable description for UI
    description = "HuggingFace Inference API (free tier available)"

    # Provider metadata
    metadata = ProviderMetadata(
        name='huggingface',
        display_name='HuggingFace',
        description='HuggingFace Inference API models',
        icon='simple-icons:huggingface',
        is_local=False,
        requires_api_key=True,
        api_key_env_var='HUGGINGFACE_API_KEY',
        timeout_env_var='PROVIDER_TIMEOUT_HUGGINGFACE',
        timeout_default=120,
    )

    # HuggingFace Hub API endpoint for model discovery
    HUB_API_URL = "https://huggingface.co/api/models"

    # Inference providers to query for available models
    # These are serverless providers that support the router API
    INFERENCE_PROVIDERS = "together,fireworks-ai,groq,cerebras,sambanova,novita"

    # Fallback models if API discovery fails (known to work via inference providers)
    FALLBACK_MODELS = {
        'meta-llama/Llama-3.3-70B-Instruct': 'Llama 3.3 70B Instruct',
        'meta-llama/Llama-3.1-8B-Instruct': 'Llama 3.1 8B Instruct',
        'Qwen/Qwen2.5-72B-Instruct': 'Qwen 2.5 72B Instruct',
        'Qwen/Qwen3-32B': 'Qwen 3 32B',
        'deepseek-ai/DeepSeek-V3': 'DeepSeek V3',
        'mistralai/Mixtral-8x7B-Instruct-v0.1': 'Mixtral 8x7B Instruct',
    }

    # Default model
    DEFAULT_MODEL = 'meta-llama/Llama-3.3-70B-Instruct'

    # Patterns to identify instruction-tuned models (good for summarization)
    INSTRUCT_PATTERNS = [
        r'-[Ii]nstruct',  # -Instruct, -instruct
        r'-it$',          # -it (e.g., gemma-2-27b-it)
        r'[Cc]hat',       # Chat models
    ]

    # Patterns to exclude (not ideal for general summarization)
    EXCLUDE_PATTERNS = [
        r'[Cc]oder',      # Coding-focused models
        r'[Cc]ode[Ll]lama',
        r'-code-',
        r'safeguard',     # Safety/moderation models
        r'guard',
        r'embed',         # Embedding models
        r'rerank',        # Reranking models
    ]

    @classmethod
    def _is_instruct_model(cls, model_id: str) -> bool:
        """Check if model is instruction-tuned (good for summarization)."""
        return any(re.search(p, model_id) for p in cls.INSTRUCT_PATTERNS)

    @classmethod
    def _should_exclude(cls, model_id: str) -> bool:
        """Check if model should be excluded (coding/specialized models)."""
        return any(re.search(p, model_id) for p in cls.EXCLUDE_PATTERNS)

    @classmethod
    def _format_model_name(cls, model_id: str) -> str:
        """
        Format model ID into a human-readable name.

        Example: 'meta-llama/Llama-3.3-70B-Instruct' -> 'Llama 3.3 70B Instruct'
        """
        # Extract model name (after the org/)
        if '/' in model_id:
            name = model_id.split('/')[-1]
        else:
            name = model_id

        # Replace hyphens/underscores with spaces
        name = re.sub(r'[-_]', ' ', name)

        # Clean up common patterns
        name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single
        name = name.strip()

        return name

    @classmethod
    def _estimate_model_size(cls, model_id: str) -> str:
        """
        Estimate model size category from model ID.

        Returns: 'small' (<10B), 'medium' (10-40B), 'large' (>40B), or 'unknown'
        """
        # Look for size indicators in model name
        size_match = re.search(r'(\d+)[Bb]', model_id)
        if size_match:
            size_b = int(size_match.group(1))
            if size_b < 10:
                return 'small'
            elif size_b <= 40:
                return 'medium'
            else:
                return 'large'

        # MoE models (e.g., 8x7B, 235B-A22B)
        moe_match = re.search(r'(\d+)x(\d+)[Bb]', model_id)
        if moe_match:
            return 'large'  # MoE models are typically large

        return 'unknown'

    @classmethod
    def resolve_model(cls, model: str) -> tuple[str, str]:
        """
        Resolve model identifier to (key, full_path).

        Accepts full HuggingFace model paths (e.g., 'meta-llama/Llama-3.3-70B-Instruct').
        For backwards compatibility, also accepts the model path as the key.

        Returns:
            Tuple of (model_key, model_full_path)
        """
        # If it looks like a full model path (contains /), use it directly
        if '/' in model:
            return model, model

        # Check fallback models for backwards compatibility
        for full_path, name in cls.FALLBACK_MODELS.items():
            # Check if model matches a known short name pattern
            short_name = full_path.split('/')[-1].lower()
            if model.lower() == short_name or model.lower().replace('-', '') == short_name.replace('-', ''):
                return full_path, full_path

        # Unknown model - assume it's a valid model path and try it
        # This allows users to use any model available on HuggingFace
        return model, model

    # Default timeout for cloud API calls
    DEFAULT_TIMEOUT = 120  # 2 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_content_chars: Optional[int] = None,
    ):
        """
        Initialize the HuggingFace summarizer.

        Args:
            api_key: HuggingFace API token (if not provided, reads from HUGGINGFACE_API_KEY env var)
            model: Model identifier - full HuggingFace path (e.g., 'meta-llama/Llama-3.3-70B-Instruct')
            timeout: Request timeout in seconds (default: 120s)
                     Can be configured via PROVIDER_TIMEOUT_HUGGINGFACE env var.
            max_content_chars: Maximum content length for summarization.
                     If None, uses global setting or 30K default. 0 means no limit.
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('HUGGINGFACE_API_KEY')
        if not self.api_key:
            raise ValueError(
                "HuggingFace API key required. Set HUGGINGFACE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_key, self.model = self.resolve_model(model or self.DEFAULT_MODEL)
        self.max_content_chars = max_content_chars  # Used by _truncate_content()

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

        # Model validation is lenient - we allow any model path since HuggingFace
        # has thousands of models and we can't enumerate them all
        if not self.model:
            errors.append("Model is required but not set.")

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
                    required=True,
                    env_var="HUGGINGFACE_API_KEY",
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

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[ModelInfo]:
        """
        Dynamically fetch available models from HuggingFace Inference Providers.

        Queries the HuggingFace Hub API for models available via serverless inference
        providers (Together, Fireworks, Groq, Cerebras, etc.). Filters for instruction-
        tuned models suitable for summarization and excludes coding-focused models.

        Args:
            api_key: Not required for model discovery (public API)

        Returns:
            List of ModelInfo for available HuggingFace models, sorted by popularity
        """
        try:
            models = cls._fetch_available_models()
            if models:
                return models
        except Exception as e:
            logger.warning(f"Failed to fetch HuggingFace models from API: {e}")

        # Fallback to curated list if API fails
        return cls._get_fallback_models()

    @classmethod
    def _fetch_available_models(cls, limit: int = 50, max_results: int = 15) -> List[ModelInfo]:
        """
        Fetch available models from HuggingFace Hub API.

        Args:
            limit: Number of models to fetch from API
            max_results: Maximum number of models to return after filtering

        Returns:
            List of ModelInfo for available models
        """
        response = requests.get(
            cls.HUB_API_URL,
            params={
                "pipeline_tag": "text-generation",
                "inference_provider": cls.INFERENCE_PROVIDERS,
                "sort": "downloads",
                "direction": "-1",
                "limit": limit,
            },
            timeout=10,
        )
        response.raise_for_status()
        models_data = response.json()

        # Filter and process models
        filtered_models = []

        for model in models_data:
            model_id = model.get('id', model.get('modelId', ''))
            if not model_id:
                continue

            # Skip excluded models (coders, safeguards, etc.)
            if cls._should_exclude(model_id):
                continue

            # Extract org for diversity tracking
            org = model_id.split('/')[0] if '/' in model_id else 'unknown'

            # Prioritize instruct models, but include popular base models too
            is_instruct = cls._is_instruct_model(model_id)
            downloads = model.get('downloads', 0)

            # Score: instruct models get priority, then by downloads
            score = (1 if is_instruct else 0, downloads)

            filtered_models.append({
                'id': model_id,
                'name': cls._format_model_name(model_id),
                'downloads': downloads,
                'is_instruct': is_instruct,
                'org': org,
                'size': cls._estimate_model_size(model_id),
                'score': score,
            })

        # Sort by score (instruct first, then by downloads)
        filtered_models.sort(key=lambda x: x['score'], reverse=True)

        # Select top models with some diversity (not all from same org)
        result = []
        org_counts = {}
        max_per_org = 4  # Limit models per organization for diversity

        for model in filtered_models:
            org = model['org']
            if org_counts.get(org, 0) >= max_per_org:
                continue

            org_counts[org] = org_counts.get(org, 0) + 1
            is_default = model['id'] == cls.DEFAULT_MODEL

            result.append(ModelInfo(
                id=model['id'],
                name=model['name'],
                provider='huggingface',
                is_default=is_default,
            ))

            if len(result) >= max_results:
                break

        # Ensure default model is in the list
        default_in_list = any(m.id == cls.DEFAULT_MODEL for m in result)
        if not default_in_list and result:
            # Add default model at the beginning
            result.insert(0, ModelInfo(
                id=cls.DEFAULT_MODEL,
                name=cls._format_model_name(cls.DEFAULT_MODEL),
                provider='huggingface',
                is_default=True,
            ))
            # Remove last item to maintain max_results
            if len(result) > max_results:
                result = result[:max_results]

        return result

    @classmethod
    def _get_fallback_models(cls) -> List[ModelInfo]:
        """
        Return fallback model list when API discovery fails.

        Returns:
            List of ModelInfo for known working models
        """
        return [
            ModelInfo(
                id=model_id,
                name=name,
                provider='huggingface',
                is_default=(model_id == cls.DEFAULT_MODEL),
            )
            for model_id, name in cls.FALLBACK_MODELS.items()
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

        # Truncate content if needed (preserves prompt structure)
        content = self._truncate_content(content)

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


# Backwards compatibility alias
HuggingFaceSummarizer = HuggingFaceProvider
