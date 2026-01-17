"""OpenAI chat provider with native tool calling and streaming support.

This module provides the OpenAIChatProvider class for interacting with OpenAI's
Chat Completions API. It supports:
- GPT-4, GPT-4-turbo, GPT-3.5-turbo, and o1/o3 models
- Native function/tool calling
- Streaming responses
- Token tracking

Environment Variables:
    OPENAI_API_KEY: Your OpenAI API key (required)
    OPENAI_BASE_URL: Custom base URL for OpenAI-compatible endpoints (optional)
    PROVIDER_TIMEOUT_OPENAI: Request timeout in seconds (default: 120)

Example:
    >>> from reconly_core.chat.providers import OpenAIChatProvider
    >>>
    >>> provider = OpenAIChatProvider(model="gpt-4o")
    >>>
    >>> # Non-streaming
    >>> response = await provider.chat(
    ...     messages=[{"role": "user", "content": "Hello!"}]
    ... )
    >>> print(response.content)
    >>>
    >>> # Streaming
    >>> async for chunk in await provider.chat(
    ...     messages=[{"role": "user", "content": "Hello!"}],
    ...     stream=True
    ... ):
    ...     if chunk.type == "content":
    ...         print(chunk.content, end="")
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncGenerator

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

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_MODEL = "gpt-4o"
DEFAULT_TIMEOUT = 120  # seconds
DEFAULT_MAX_TOKENS = 4096


class OpenAIChatProvider(BaseChatProvider):
    """Chat provider for OpenAI's API with native tool calling.

    This provider uses OpenAI's Chat Completions API with full support for:
    - Function/tool calling (native API support)
    - Streaming responses
    - Token usage tracking
    - OpenAI-compatible endpoints (Azure, local proxies)

    Attributes:
        client: The OpenAI client instance.
        _model: The model to use.
        base_url: Optional custom base URL.
        timeout: Request timeout in seconds.
        max_tokens: Maximum tokens for completion.

    Example:
        >>> provider = OpenAIChatProvider(
        ...     api_key="sk-...",
        ...     model="gpt-4-turbo",
        ...     max_tokens=2048
        ... )
        >>> response = await provider.chat([{"role": "user", "content": "Hi"}])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str | None = None,
        timeout: int | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        """Initialize the OpenAI chat provider.

        Args:
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            model: Model to use (default: gpt-4o).
            base_url: Custom base URL for OpenAI-compatible endpoints.
            timeout: Request timeout in seconds (default: 120).
            max_tokens: Maximum tokens for completion (default: 4096).

        Raises:
            AuthenticationError: If no API key is provided.
        """
        from openai import OpenAI, AsyncOpenAI

        self._model = model
        self.max_tokens = max_tokens

        # Get API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter.",
                provider="openai",
            )

        # Get base URL
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

        # Get timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv("PROVIDER_TIMEOUT_OPENAI")
            self.timeout = int(env_timeout) if env_timeout else DEFAULT_TIMEOUT

        # Initialize clients
        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": float(self.timeout),
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def model(self) -> str:
        """Return the model being used."""
        return self._model

    def supports_native_tools(self) -> bool:
        """OpenAI has native tool calling support."""
        return True

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return bool(self.api_key)

    def validate_config(self) -> list[str]:
        """Validate the provider configuration."""
        errors = []

        if not self.api_key:
            errors.append(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
            )

        if not self._model:
            errors.append("Model name is required.")

        if self.base_url and not self.base_url.startswith("http"):
            errors.append("Base URL must start with http:// or https://")

        return errors

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        info = {
            "provider": self.provider_name,
            "model": self._model,
            "is_local": False,
            "supports_tools": True,
            "max_tokens": self.max_tokens,
        }

        if self.base_url:
            info["base_url"] = self.base_url
            info["compatible_endpoint"] = True

        return info

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncGenerator[StreamChunk, None]:
        """Send a chat request to OpenAI.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tool definitions.
            stream: If True, return streaming response.

        Returns:
            ChatResponse for non-streaming, AsyncGenerator for streaming.

        Raises:
            ChatProviderError: On API errors.
        """
        # Normalize messages
        normalized = self._normalize_messages(messages)

        # Format messages for OpenAI
        api_messages = self._format_messages(normalized)

        if stream:
            return self._chat_stream(api_messages, tools)
        else:
            return await self._chat_non_stream(api_messages, tools)

    def _format_messages(
        self, messages: list[ChatMessage]
    ) -> list[dict[str, Any]]:
        """Format messages for OpenAI API.

        Args:
            messages: List of ChatMessage objects.

        Returns:
            List of message dicts in OpenAI format.
        """
        api_messages = []

        for msg in messages:
            if msg.role == "tool" or msg.tool_call_id:
                # Tool result message
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content or "",
                })
            elif msg.tool_calls:
                # Assistant message with tool calls
                api_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",  # Content can be None with tool calls
                    "tool_calls": msg.tool_calls,
                })
            else:
                # Regular message
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        return api_messages

    async def _chat_non_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> ChatResponse:
        """Non-streaming chat completion.

        Args:
            messages: Formatted messages for API.
            tools: Optional tools.

        Returns:
            ChatResponse with complete response.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools

        try:
            response = await self.async_client.chat.completions.create(**kwargs)
        except Exception as e:
            raise self._handle_error(e)

        # Parse response
        message = response.choices[0].message
        content = message.content or ""
        finish_reason = response.choices[0].finish_reason or "stop"

        # Parse tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

        # Get usage
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            raw_response=response,
        )

    async def _chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streaming chat completion.

        Args:
            messages: Formatted messages for API.
            tools: Optional tools.

        Yields:
            StreamChunk objects as response streams in.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = tools

        try:
            stream = await self.async_client.chat.completions.create(**kwargs)
        except Exception as e:
            raise self._handle_error(e)

        # Track state for tool calls being built
        current_tool_calls: dict[int, dict[str, Any]] = {}
        tokens_in = 0
        tokens_out = 0
        finish_reason = "stop"

        try:
            async for chunk in stream:
                # Check for usage info (comes in final chunk)
                if chunk.usage:
                    tokens_in = chunk.usage.prompt_tokens
                    tokens_out = chunk.usage.completion_tokens

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                chunk_finish = chunk.choices[0].finish_reason

                if chunk_finish:
                    finish_reason = chunk_finish

                # Handle content
                if delta.content:
                    yield StreamChunk(type="content", content=delta.content)

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index

                        if idx not in current_tool_calls:
                            # New tool call starting
                            current_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "type": "function",
                                "function": {
                                    "name": tc_delta.function.name if tc_delta.function else "",
                                    "arguments": "",
                                },
                            }

                            # Yield tool_call_start if we have enough info
                            if tc_delta.id and tc_delta.function and tc_delta.function.name:
                                yield StreamChunk(
                                    type="tool_call_start",
                                    tool_call=current_tool_calls[idx].copy(),
                                )

                        # Update tool call
                        tc = current_tool_calls[idx]
                        if tc_delta.id:
                            tc["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tc["function"]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tc["function"]["arguments"] += tc_delta.function.arguments

                                # Yield argument delta
                                yield StreamChunk(
                                    type="tool_call_delta",
                                    delta=tc_delta.function.arguments,
                                    tool_call_id=tc["id"],
                                )

            # Yield done chunk with final stats
            yield StreamChunk(
                type="done",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                finish_reason=finish_reason,
            )

        except Exception as e:
            yield StreamChunk(type="error", error=str(e))

    def _handle_error(self, error: Exception) -> ChatProviderError:
        """Convert OpenAI errors to ChatProviderError.

        Args:
            error: The original exception.

        Returns:
            Appropriate ChatProviderError subclass.
        """
        from openai import (
            AuthenticationError as OpenAIAuthError,
            RateLimitError as OpenAIRateError,
            NotFoundError as OpenAINotFoundError,
            APIConnectionError,
            APIStatusError,
        )

        error_msg = str(error)

        if isinstance(error, OpenAIAuthError):
            return AuthenticationError(
                "Invalid or missing API key. Check your OPENAI_API_KEY.",
                provider="openai",
                original_error=error,
            )
        elif isinstance(error, OpenAIRateError):
            return RateLimitError(
                f"Rate limit exceeded: {error_msg}. Wait and try again.",
                provider="openai",
                original_error=error,
            )
        elif isinstance(error, OpenAINotFoundError):
            return ModelNotFoundError(
                f"Model not found: {error_msg}",
                provider="openai",
                original_error=error,
            )
        elif isinstance(error, APIConnectionError):
            return ProviderUnavailableError(
                f"Could not connect to OpenAI: {error_msg}",
                provider="openai",
                original_error=error,
            )
        elif isinstance(error, APIStatusError):
            return ChatProviderError(
                f"OpenAI API error: {error_msg}",
                provider="openai",
                original_error=error,
            )
        else:
            return ChatProviderError(
                f"OpenAI error: {error_msg}",
                provider="openai",
                original_error=error,
            )

    def format_tool_result(
        self,
        tool_call_id: str,
        result: Any,
        is_error: bool = False,
    ) -> ChatMessage:
        """Format a tool result for including in the conversation.

        Args:
            tool_call_id: The ID of the tool call.
            result: The result data.
            is_error: Whether this is an error result.

        Returns:
            ChatMessage with the tool result.
        """
        if isinstance(result, str):
            content = result
        else:
            try:
                content = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                content = str(result)

        return ChatMessage(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
        )

    def format_assistant_with_tool_calls(
        self,
        content: str | None,
        tool_calls: list[dict[str, Any]],
    ) -> ChatMessage:
        """Format an assistant message with tool calls.

        Args:
            content: Optional text content.
            tool_calls: List of tool calls.

        Returns:
            ChatMessage for the assistant with tool calls.
        """
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
