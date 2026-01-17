"""Provider adapters for converting tool definitions to provider-specific formats.

Each LLM provider has its own format for tool/function calling. These adapters
convert the provider-agnostic ToolDefinition format to the specific format
required by each provider.

Example:
    >>> from reconly_core.chat.tools import tool_registry
    >>> from reconly_core.chat.adapters import OpenAIAdapter, AnthropicAdapter
    >>>
    >>> # Get tools in OpenAI format
    >>> openai_adapter = OpenAIAdapter()
    >>> openai_tools = openai_adapter.format_tools(tool_registry.list_tools())
    >>>
    >>> # Get tools in Anthropic format
    >>> anthropic_adapter = AnthropicAdapter()
    >>> anthropic_tools = anthropic_adapter.format_tools(tool_registry.list_tools())
"""

from reconly_core.chat.adapters.base import BaseToolAdapter, ToolCallRequest
from reconly_core.chat.adapters.openai_adapter import OpenAIAdapter
from reconly_core.chat.adapters.anthropic_adapter import AnthropicAdapter
from reconly_core.chat.adapters.ollama_adapter import OllamaAdapter

__all__ = [
    "BaseToolAdapter",
    "ToolCallRequest",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
]
