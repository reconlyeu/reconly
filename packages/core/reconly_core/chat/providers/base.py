"""Base class for chat providers.

This module defines the abstract interface that all chat providers must implement.
Providers handle communication with LLM APIs including streaming and tool calling.

The design follows a normalized response format that abstracts away provider-specific
differences, making it easy to add new providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


@dataclass
class ChatMessage:
    """A message in a chat conversation.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: The text content of the message.
        tool_calls: List of tool calls made by assistant (if any).
        tool_call_id: ID of the tool call this message responds to (for tool results).
        name: Name of the function/tool (for tool results).

    Example:
        >>> user_msg = ChatMessage(role="user", content="Hello!")
        >>> assistant_msg = ChatMessage(
        ...     role="assistant",
        ...     content="I'll check that for you.",
        ...     tool_calls=[{
        ...         "id": "call_123",
        ...         "type": "function",
        ...         "function": {"name": "list_feeds", "arguments": "{}"}
        ...     }]
        ... )
    """

    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            result["name"] = self.name
        return result


@dataclass
class ChatResponse:
    """Response from a chat completion request (non-streaming).

    This is the normalized response format returned by all providers,
    abstracting away provider-specific differences.

    Attributes:
        content: The text response from the assistant.
        tool_calls: List of tool calls the assistant wants to make.
            Each tool call has: id, type, function (name, arguments).
        tokens_in: Number of input/prompt tokens used.
        tokens_out: Number of output/completion tokens generated.
        finish_reason: Why the response ended (stop, tool_calls, length, etc.).
        raw_response: The original provider response for debugging.

    Example:
        >>> response = ChatResponse(
        ...     content="Here are your feeds:",
        ...     tool_calls=[{
        ...         "id": "call_abc123",
        ...         "type": "function",
        ...         "function": {
        ...             "name": "list_feeds",
        ...             "arguments": "{}"
        ...         }
        ...     }],
        ...     tokens_in=150,
        ...     tokens_out=200,
        ...     finish_reason="tool_calls"
        ... )
    """

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = "stop"
    raw_response: Any = None


@dataclass
class StreamChunk:
    """A chunk of streaming response.

    Streaming responses are delivered as a series of chunks. Each chunk
    has a type indicating what kind of data it contains.

    Attributes:
        type: Type of chunk:
            - "content": Text content being streamed
            - "tool_call_start": Beginning of a tool call
            - "tool_call_delta": Incremental tool call arguments
            - "done": Stream is complete (includes final usage stats)
            - "error": An error occurred
        content: Text content for "content" chunks.
        tool_call: Tool call info for "tool_call_start" chunks.
            Format: {"id": str, "type": str, "function": {"name": str, "arguments": str}}
        delta: Incremental arguments string for "tool_call_delta" chunks.
        tool_call_id: ID of the tool call being updated (for delta chunks).
        tokens_in: Final input token count (in "done" chunk).
        tokens_out: Final output token count (in "done" chunk).
        finish_reason: Why streaming ended (in "done" chunk).
        error: Error message (for "error" chunks).

    Example:
        >>> # Content streaming
        >>> chunk = StreamChunk(type="content", content="Hello")
        >>>
        >>> # Tool call starting
        >>> chunk = StreamChunk(
        ...     type="tool_call_start",
        ...     tool_call={
        ...         "id": "call_123",
        ...         "type": "function",
        ...         "function": {"name": "list_feeds", "arguments": ""}
        ...     }
        ... )
        >>>
        >>> # Done with stats
        >>> chunk = StreamChunk(
        ...     type="done",
        ...     tokens_in=100,
        ...     tokens_out=50,
        ...     finish_reason="stop"
        ... )
    """

    type: str  # content, tool_call_start, tool_call_delta, done, error
    content: str = ""
    tool_call: dict[str, Any] | None = None
    delta: str = ""
    tool_call_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = ""
    error: str = ""


class ChatProviderError(Exception):
    """Base exception for chat provider errors.

    Attributes:
        message: Human-readable error message.
        provider: Name of the provider that raised the error.
        original_error: The underlying exception, if any.
    """

    def __init__(
        self,
        message: str,
        provider: str = "",
        original_error: Exception | None = None,
    ):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(f"[{provider}] {message}" if provider else message)


class AuthenticationError(ChatProviderError):
    """Raised when authentication fails (invalid/missing API key)."""

    pass


class RateLimitError(ChatProviderError):
    """Raised when rate limits are exceeded."""

    pass


class ModelNotFoundError(ChatProviderError):
    """Raised when the requested model is not found."""

    pass


class ProviderUnavailableError(ChatProviderError):
    """Raised when the provider service is unavailable."""

    pass


class BaseChatProvider(ABC):
    """Abstract base class for chat providers.

    All chat providers must implement this interface to ensure consistent
    behavior across different LLM backends (OpenAI, Anthropic, Ollama, etc.).

    Providers handle:
    - Sending chat messages to the LLM
    - Receiving responses (streaming and non-streaming)
    - Tool/function calling
    - Error handling and normalization

    Example:
        >>> class MyChatProvider(BaseChatProvider):
        ...     @property
        ...     def provider_name(self) -> str:
        ...         return "my_provider"
        ...
        ...     async def chat(self, messages, tools=None, stream=False):
        ...         # Implementation
        ...         pass
        ...
        ...     def supports_native_tools(self) -> bool:
        ...         return True
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "ollama").
        """
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model being used.

        Returns:
            Model name/identifier.
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncGenerator[StreamChunk, None]:
        """Send a chat request to the LLM provider.

        This is the main method for interacting with the LLM. It handles both
        streaming and non-streaming responses, as well as tool calling.

        Args:
            messages: List of conversation messages. Can be ChatMessage objects
                or dictionaries with keys: role, content, tool_calls, tool_call_id.
            tools: Optional list of tool definitions in OpenAI format:
                [{"type": "function", "function": {"name": str, "description": str, "parameters": dict}}]
            stream: If True, returns an async generator yielding StreamChunk objects.
                If False, returns a ChatResponse with the complete response.

        Returns:
            If stream=False: ChatResponse with complete response.
            If stream=True: AsyncGenerator yielding StreamChunk objects.

        Raises:
            ChatProviderError: Base error for provider issues.
            AuthenticationError: If authentication fails.
            RateLimitError: If rate limits are exceeded.
            ModelNotFoundError: If the model is not found.
            ProviderUnavailableError: If the service is down.

        Example:
            >>> # Non-streaming
            >>> response = await provider.chat(
            ...     messages=[{"role": "user", "content": "Hello"}],
            ...     tools=None,
            ...     stream=False
            ... )
            >>> print(response.content)
            >>>
            >>> # Streaming
            >>> async for chunk in await provider.chat(messages, stream=True):
            ...     if chunk.type == "content":
            ...         print(chunk.content, end="", flush=True)
        """
        pass

    @abstractmethod
    def supports_native_tools(self) -> bool:
        """Check if this provider supports native tool/function calling.

        Native tool calling means the provider has built-in API support for
        tools/functions. Providers without native support (like some Ollama
        models) implement tools via prompt engineering.

        Returns:
            True if the provider has native tool calling API.
            False if tools are implemented via prompts.
        """
        pass

    def is_available(self) -> bool:
        """Check if the provider is available and configured.

        This should perform basic checks like API key presence and
        optionally test connectivity.

        Returns:
            True if the provider appears to be usable.
        """
        return True

    def validate_config(self) -> list[str]:
        """Validate the provider configuration.

        Returns:
            List of error messages. Empty list if configuration is valid.
        """
        return []

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model.

        Returns:
            Dictionary with model metadata:
                - provider: Provider name
                - model: Model identifier
                - is_local: Whether it runs locally
                - supports_tools: Whether native tools are supported
        """
        return {
            "provider": self.provider_name,
            "model": self.model,
            "is_local": False,
            "supports_tools": self.supports_native_tools(),
        }

    def _normalize_messages(
        self, messages: list[ChatMessage | dict[str, Any]]
    ) -> list[ChatMessage]:
        """Convert messages to ChatMessage objects.

        Args:
            messages: List of messages (ChatMessage or dict).

        Returns:
            List of ChatMessage objects.
        """
        result = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                result.append(msg)
            elif isinstance(msg, dict):
                result.append(
                    ChatMessage(
                        role=msg.get("role", "user"),
                        content=msg.get("content"),
                        tool_calls=msg.get("tool_calls"),
                        tool_call_id=msg.get("tool_call_id"),
                        name=msg.get("name"),
                    )
                )
            else:
                raise ValueError(f"Invalid message type: {type(msg)}")
        return result
