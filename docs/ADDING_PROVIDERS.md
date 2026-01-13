# Adding New AI Providers

This guide shows you how to add a new AI provider to Reconly. The self-registering provider architecture makes this straightforward.

## Overview

Reconly uses a **provider registry pattern** that allows new providers to be added without modifying core factory code. Contributors can:

1. Create a new provider class inheriting from `BaseSummarizer`
2. Decorate it with `@register_provider('provider-name')`
3. Implement required abstract methods
4. Inherit from `BaseSummarizerTestSuite` for automatic quality gates

The provider becomes automatically discoverable without touching `factory.py`.

## Step-by-Step Guide

### 1. Create Your Provider Class

Create a new file in `packages/core/reconly_core/summarizers/`:

```python
"""My Custom Provider implementation."""
import os
from typing import Dict, List

from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.summarizers.registry import register_provider
from reconly_core.summarizers.capabilities import ProviderCapabilities


@register_provider('my-provider')  # <-- Register your provider
class MyProviderSummarizer(BaseSummarizer):
    """Summarizes content using My Custom Provider."""

    def __init__(self, api_key: str = None):
        """Initialize the provider."""
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('MY_PROVIDER_API_KEY')

        if not self.api_key:
            raise ValueError(
                "API key required. Set MY_PROVIDER_API_KEY environment variable "
                "or pass api_key parameter."
            )

    # Required abstract methods (see below)
    ...
```

### 2. Implement Required Abstract Methods

Your provider **must** implement these abstract methods:

#### `summarize(content_data, language, system_prompt, user_prompt) -> Dict[str, str]`

Main method that generates summaries. Prompts are passed from the caller (resolved from PromptTemplate):

```python
def summarize(
    self,
    content_data: Dict[str, str],
    language: str = 'de',
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> Dict[str, str]:
    """Summarize content."""
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
            sys_prompt = "Du bist ein professioneller Content-Zusammenfasser."
            usr_prompt = f"Fasse den folgenden Inhalt zusammen.\n\nTitel: {title}\n\nInhalt:\n{content}"
        else:
            sys_prompt = "You are a professional content summarizer."
            usr_prompt = f"Summarize the following content.\n\nTitle: {title}\n\nContent:\n{content}"

    # Call your provider's API with the prompts
    summary = self._call_my_provider_api(sys_prompt, usr_prompt)

    # Return original data with summary added
    result = content_data.copy()
    result['summary'] = summary
    result['summary_language'] = language
    result['model_info'] = self.get_model_info()
    result['estimated_cost'] = self.estimate_cost(len(content))

    return result
```

#### `get_provider_name() -> str`

Return a unique provider name:

```python
def get_provider_name(self) -> str:
    """Get provider name."""
    return 'my-provider'
```

#### `estimate_cost(content_length: int) -> float`

Estimate summarization cost:

```python
def estimate_cost(self, content_length: int) -> float:
    """Estimate cost in USD."""
    # For local/free providers
    return 0.0

    # For paid providers (example)
    input_tokens = content_length / 4  # Rough estimation
    output_tokens = 500  # Assume ~500 tokens for summary

    input_cost = (input_tokens / 1_000_000) * 2.0  # $2 per 1M tokens
    output_cost = (output_tokens / 1_000_000) * 6.0  # $6 per 1M tokens

    return input_cost + output_cost
```

#### `get_capabilities() -> ProviderCapabilities` (classmethod)

Describe your provider's capabilities:

```python
@classmethod
def get_capabilities(cls) -> ProviderCapabilities:
    """Get provider capabilities."""
    return ProviderCapabilities(
        supports_streaming=False,
        supports_async=False,
        requires_api_key=True,
        is_local=False,  # True for local providers like Ollama
        max_context_tokens=8192,
        cost_per_1k_input=2.0,  # USD per 1,000 input tokens
        cost_per_1k_output=6.0  # USD per 1,000 output tokens
    )
```

#### `is_available() -> bool`

Check if provider is currently available:

```python
def is_available(self) -> bool:
    """Check if provider is available."""
    if not self.api_key:
        return False

    # Optional: Ping API to verify availability
    try:
        response = requests.get(f"{self.base_url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False
```

**Important**: This method should **never raise exceptions** - return `True` or `False`.

#### `validate_config() -> List[str]`

Validate configuration and return list of errors:

```python
def validate_config(self) -> List[str]:
    """Validate provider configuration."""
    errors = []

    if not self.api_key:
        errors.append("API key is required but not set. Set MY_PROVIDER_API_KEY environment variable.")

    if not self.base_url.startswith('http'):
        errors.append("Base URL must start with http:// or https://")

    return errors  # Empty list means valid configuration
```

### 3. Create Tests

Create `tests/core/summarizers/test_my_provider.py` that **inherits from `BaseSummarizerTestSuite`**:

```python
"""Tests for My Custom Provider."""
import pytest
from unittest.mock import patch, Mock

from reconly_core.summarizers.my_provider import MyProviderSummarizer
from tests.core.summarizers.base_test_suite import BaseSummarizerTestSuite


class TestMyProviderSummarizer(BaseSummarizerTestSuite):
    """Test suite for MyProviderSummarizer (inherits contract tests)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured summarizer instance."""
        return MyProviderSummarizer(api_key='test-key-12345')

    # You automatically get 15+ contract tests from BaseSummarizerTestSuite!

    # Add provider-specific tests
    def test_api_key_from_environment(self, monkeypatch):
        """Test that API key is read from environment."""
        monkeypatch.setenv('MY_PROVIDER_API_KEY', 'env-key')
        summarizer = MyProviderSummarizer()
        assert summarizer.api_key == 'env-key'

    @patch('requests.post')
    def test_summarize_success(self, mock_post, summarizer):
        """Test successful summarization."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'summary': 'Test summary'}

        content_data = self.create_mock_content_data(
            title='Test Article',
            content='This is test content.'
        )

        result = summarizer.summarize(content_data, language='en')

        assert 'summary' in result
        assert result['summary'] == 'Test summary'
```

By inheriting from `BaseSummarizerTestSuite`, you get these contract tests for free:
- Interface compliance verification
- Provider name validation
- Cost estimation checks
- Capabilities validation
- Config validation checks
- And more!

### 4. Register Your Provider

Your provider is **automatically registered** when the module is imported thanks to the `@register_provider` decorator.

To ensure it's loaded, import it in `factory.py`:

```python
# In factory.py
from reconly_core.summarizers.my_provider import MyProviderSummarizer
```

### 5. Use Your Provider

```python
from reconly_core.summarizers.factory import get_summarizer

# Direct usage
summarizer = get_summarizer(provider='my-provider', api_key='...')
result = summarizer.summarize(content_data, language='en')

# Via environment variable
# export DEFAULT_PROVIDER=my-provider
# export MY_PROVIDER_API_KEY=...
summarizer = get_summarizer()
```

## Configuration Schema (Settings Integration)

Providers can define a configuration schema to enable settings management through the UI. This allows users to configure API keys, base URLs, and provider-specific options.

### Adding Config Schema

Override the `get_config_schema()` method to declare your provider's configuration requirements:

```python
from reconly_core.summarizers.base import BaseSummarizer, ProviderConfigSchema
from reconly_core.summarizers.registry import register_provider
from reconly_core.config_types import ConfigField

@register_provider('gemini')
class GeminiSummarizer(BaseSummarizer):
    """Summarizes content using Google Gemini."""

    def get_config_schema(self) -> ProviderConfigSchema:
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="Your Google Gemini API key",
                    required=True,
                    env_var="GEMINI_API_KEY",
                    editable=False,  # Credential - env only
                    secret=True
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Model",
                    description="Gemini model to use",
                    default="gemini-1.5-flash",
                    required=False
                ),
                ConfigField(
                    key="temperature",
                    type="integer",
                    label="Temperature",
                    description="Sampling temperature (0-100)",
                    default=70,
                    required=False
                ),
            ],
            requires_api_key=True
        )
```

### ConfigField Attributes

| Attribute | Description |
|-----------|-------------|
| `key` | Setting key (e.g., "api_key", "model") |
| `type` | Field type: "string", "boolean", "integer", or "path" |
| `label` | Human-readable label for UI |
| `description` | Help text describing the field |
| `default` | Default value if not configured |
| `required` | Whether field is required for provider to function |
| `placeholder` | Input placeholder text for UI |
| `env_var` | Environment variable name (e.g., "OPENAI_API_KEY") |
| `editable` | Whether field can be edited via UI (False = env-only for secrets) |
| `secret` | Whether field contains sensitive data (masked in responses) |

### Settings Auto-Registration

When you use the `@register_provider` decorator, the provider's settings are automatically registered with the pattern:

```
provider.{name}.{field}
```

**Examples:**
- `provider.openai.api_key` - OpenAI API key
- `provider.anthropic.api_key` - Anthropic API key
- `provider.gemini.model` - Gemini model selection
- `provider.ollama.base_url` - Ollama server URL

### Accessing Configuration

Settings configured via the UI are available through the settings service. Access them in your provider:

```python
from reconly_core.services.settings_service import SettingsService

class MyProviderSummarizer(BaseSummarizer):
    def __init__(self):
        settings = SettingsService()
        self.api_key = settings.get('provider.my-provider.api_key')
        self.model = settings.get('provider.my-provider.model', 'default-model')

        if not self.api_key:
            raise ValueError("API key not configured")
```

### Best Practices for Configuration

1. **Use `secret=True`** for API keys and sensitive credentials
2. **Set `editable=False`** for credentials to enforce environment-only configuration
3. **Provide `env_var`** names for all fields that map to environment variables
4. **Mark `api_key` as `required=True`** if the provider cannot function without it
5. **Set `requires_api_key=True`** in ProviderConfigSchema for API-based providers
6. **Provide sensible defaults** for optional fields like temperature, max_tokens

## Environment Variables

Follow this naming convention:

- `MY_PROVIDER_API_KEY` - API key (maps to `provider.my-provider.api_key`)
- `MY_PROVIDER_BASE_URL` - Base URL (maps to `provider.my-provider.base_url`)
- `MY_PROVIDER_MODEL` - Model selection (maps to `provider.my-provider.model`)

The environment variables should match the `env_var` attribute in your ConfigField definitions.

## Testing Checklist

Before submitting your provider:

- [ ] All abstract methods implemented
- [ ] Test class inherits from `BaseSummarizerTestSuite`
- [ ] At least 20 total test cases (contract tests + provider-specific)
- [ ] `pytest tests/core/summarizers/test_my_provider.py` passes
- [ ] `validate_config()` returns helpful error messages
- [ ] `is_available()` does not raise exceptions
- [ ] Prompts passed to summarize() are used (with fallback)

## Provider Architecture

```
┌─────────────────────────────────────────────────┐
│ BaseSummarizer (Abstract)                       │
│ - summarize()                                   │
│ - get_provider_name()                           │
│ - estimate_cost()                               │
│ - get_capabilities() [classmethod]              │
│ - is_available()                                │
│ - validate_config()                             │
└─────────────────────────────────────────────────┘
                     ▲
                     │ inherits
        ┌────────────┴────────────┐
        │                         │
┌───────────────┐         ┌───────────────┐
│ @register_provider('foo')    @register_provider('bar')
│ FooSummarizer │         │ BarSummarizer │
└───────────────┘         └───────────────┘
        │                         │
        └────────────┬────────────┘
                     │ registered in
           ┌─────────────────────┐
           │ _PROVIDER_REGISTRY  │
           │ {                   │
           │   'foo': FooClass   │
           │   'bar': BarClass   │
           │ }                   │
           └─────────────────────┘
                     │
                     │ used by
              ┌──────────────┐
              │ get_provider │
              └──────────────┘
```

## Best Practices

1. **Handle prompts correctly** - use provided `system_prompt`/`user_prompt` with built-in fallback
2. **Don't modify factory.py** - use the registry pattern
3. **Inherit from `BaseSummarizerTestSuite`** to get quality gates
4. **Return clear error messages** in `validate_config()`
5. **Never raise in `is_available()`** - return `True`/`False`
6. **Document environment variables** in docstrings
7. **Estimate costs conservatively** - better to overestimate than surprise users

## Examples

Look at existing providers for examples:

- `ollama.py` - Local provider (no API key, $0 cost, is_local=True)
- `openai_provider.py` - Cloud provider (API key, paid, pricing tiers)
- `anthropic.py` - Cloud provider (API key, paid, single model)
- `huggingface.py` - Cloud provider (API key, free tier, multiple models)

## Questions?

- Check existing providers in `packages/core/reconly_core/summarizers/`
- Review test examples in `tests/core/summarizers/`
- Open an issue on GitHub if stuck

Happy contributing! 🎉
