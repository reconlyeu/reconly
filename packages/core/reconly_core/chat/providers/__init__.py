"""Chat providers for LLM interaction with tool calling and streaming support.

This module provides a unified interface for interacting with different LLM
providers (OpenAI, Anthropic, Ollama, LMStudio) for chat conversations with tool calling.

Key Components:
    BaseChatProvider: Abstract base class defining the provider interface
    ChatResponse: Response from non-streaming chat requests
    StreamChunk: Individual chunk from streaming responses

    OpenAIChatProvider: OpenAI GPT models with native tool calling
    AnthropicChatProvider: Anthropic Claude models with native tool use
    OllamaChatProvider: Local Ollama models with prompt-based tools
    LMStudioChatProvider: Local LMStudio models with native tool calling

    create_provider: Factory function to create providers by name
    get_default_provider: Auto-detect and create the best available provider
    create_provider_with_fallback: Create provider with fallback options

Typical Usage:
    >>> from reconly_core.chat.providers import (
    ...     get_default_provider,
    ...     create_provider,
    ...     StreamChunk,
    ... )
    >>>
    >>> # Get best available provider automatically
    >>> provider = get_default_provider()
    >>>
    >>> # Non-streaming chat
    >>> response = await provider.chat(
    ...     messages=[{"role": "user", "content": "Hello!"}],
    ...     tools=[...],  # Optional tool definitions
    ... )
    >>> print(response.content)
    >>> print(f"Used {response.tokens_in} input, {response.tokens_out} output tokens")
    >>>
    >>> # Streaming chat
    >>> async for chunk in await provider.chat(
    ...     messages=[{"role": "user", "content": "Tell me a story"}],
    ...     stream=True,
    ... ):
    ...     if chunk.type == "content":
    ...         print(chunk.content, end="", flush=True)
    ...     elif chunk.type == "tool_call_start":
    ...         print(f"[Calling {chunk.tool_call['function']['name']}]")
    ...     elif chunk.type == "done":
    ...         print(f"\\nTokens: {chunk.tokens_in}in/{chunk.tokens_out}out")

Error Handling:
    >>> from reconly_core.chat.providers import (
    ...     ChatProviderError,
    ...     AuthenticationError,
    ...     RateLimitError,
    ... )
    >>>
    >>> try:
    ...     response = await provider.chat(messages)
    ... except AuthenticationError:
    ...     print("Check your API key")
    ... except RateLimitError:
    ...     print("Too many requests, slow down")
    ... except ChatProviderError as e:
    ...     print(f"Provider error: {e}")

Environment Variables:
    DEFAULT_CHAT_PROVIDER: Preferred provider (openai, anthropic, ollama, lmstudio)
    OPENAI_API_KEY: OpenAI API key
    OPENAI_BASE_URL: Custom OpenAI-compatible endpoint
    ANTHROPIC_API_KEY: Anthropic API key
    OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
    OLLAMA_MODEL: Default Ollama model (default: llama3.2)
    LMSTUDIO_BASE_URL: LMStudio server URL (default: http://localhost:1234/v1)
    LMSTUDIO_MODEL: Default LMStudio model (auto-detected if not set)
"""

# Base classes and types
from reconly_core.chat.providers.base import (
    BaseChatProvider,
    ChatMessage,
    ChatResponse,
    StreamChunk,
    ChatProviderError,
    AuthenticationError,
    RateLimitError,
    ModelNotFoundError,
    ProviderUnavailableError,
)

# Provider implementations
from reconly_core.chat.providers.openai_provider import OpenAIChatProvider
from reconly_core.chat.providers.anthropic_provider import AnthropicChatProvider
from reconly_core.chat.providers.ollama_provider import OllamaChatProvider
from reconly_core.chat.providers.lmstudio_provider import LMStudioChatProvider

# Factory functions
from reconly_core.chat.providers.factory import (
    create_provider,
    get_default_provider,
    get_available_providers,
    create_provider_with_fallback,
    get_provider_info,
    get_cached_provider,
    clear_provider_cache,
    ProviderFactoryError,
    NoAvailableProviderError,
)


__all__ = [
    # Base classes and types
    "BaseChatProvider",
    "ChatMessage",
    "ChatResponse",
    "StreamChunk",
    # Errors
    "ChatProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ModelNotFoundError",
    "ProviderUnavailableError",
    "ProviderFactoryError",
    "NoAvailableProviderError",
    # Provider implementations
    "OpenAIChatProvider",
    "AnthropicChatProvider",
    "OllamaChatProvider",
    "LMStudioChatProvider",
    # Factory functions
    "create_provider",
    "get_default_provider",
    "get_available_providers",
    "create_provider_with_fallback",
    "get_provider_info",
    "get_cached_provider",
    "clear_provider_cache",
]
