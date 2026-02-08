"""Provider adapters for converting tool definitions to provider-specific formats.

Each LLM provider has its own format for tool/function calling. These adapters
convert the provider-agnostic ToolDefinition format to the specific format
required by each provider.

The adapter registry allows dynamic lookup of adapters by provider name,
including support for aliases (e.g., LMStudio uses the OpenAI format).

Adapter aliases are auto-registered lazily from the provider registry based on
each provider's `chat_adapter_format` metadata field when first requested.

Example:
    >>> from reconly_core.chat.tools import tool_registry
    >>> from reconly_core.chat.adapters import get_adapter, list_adapters
    >>>
    >>> # Get adapter by provider name
    >>> adapter = get_adapter("openai")
    >>> openai_tools = adapter.format_tools(tool_registry.list_tools())
    >>>
    >>> # LMStudio uses OpenAI's format (auto-aliased via chat_adapter_format)
    >>> lmstudio_adapter = get_adapter("lmstudio")  # Returns OpenAIAdapter
    >>>
    >>> # List available adapters
    >>> print(list_adapters())  # ['anthropic', 'ollama', 'openai']
"""

# Import registry first to ensure it's available for decorators
from reconly_core.chat.adapters.registry import (
    get_adapter,
    is_adapter_registered,
    list_adapters,
    register_adapter,
    register_adapter_alias,
)

# Import base classes
from reconly_core.chat.adapters.base import BaseToolAdapter, ToolCallRequest

# Import adapters - this triggers their @register_adapter decorators
from reconly_core.chat.adapters.openai_adapter import OpenAIAdapter
from reconly_core.chat.adapters.anthropic_adapter import AnthropicAdapter
from reconly_core.chat.adapters.ollama_adapter import OllamaAdapter

# Note: Provider aliases (e.g., huggingface -> openai) are registered lazily
# by get_adapter() when first requested, based on each provider's
# chat_adapter_format metadata field. This avoids import order issues.

__all__ = [
    # Registry functions
    "get_adapter",
    "is_adapter_registered",
    "list_adapters",
    "register_adapter",
    "register_adapter_alias",
    # Base classes
    "BaseToolAdapter",
    "ToolCallRequest",
    # Adapter classes (for direct instantiation if needed)
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
]
