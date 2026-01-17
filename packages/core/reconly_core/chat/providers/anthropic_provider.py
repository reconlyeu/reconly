"""Anthropic Claude chat provider with native tool calling and streaming support.

This module provides the AnthropicChatProvider class for interacting with
Anthropic's Messages API. It supports:
- Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku, and future models
- Native tool use (Anthropic's tool_use blocks)
- Streaming responses
- Token tracking

Environment Variables:
    ANTHROPIC_API_KEY: Your Anthropic API key (required)
    PROVIDER_TIMEOUT_ANTHROPIC: Request timeout in seconds (default: 120)

Example:
    >>> from reconly_core.chat.providers import AnthropicChatProvider
    >>>
    >>> provider = AnthropicChatProvider(model="claude-sonnet-4-20250514")
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
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TIMEOUT = 120  # seconds
DEFAULT_MAX_TOKENS = 4096


class AnthropicChatProvider(BaseChatProvider):
    """Chat provider for Anthropic's Claude API with native tool calling.

    This provider uses Anthropic's Messages API with full support for:
    - Tool use (native API support via tool_use content blocks)
    - Streaming responses
    - Token usage tracking

    Attributes:
        client: The Anthropic client instance.
        _model: The model to use.
        timeout: Request timeout in seconds.
        max_tokens: Maximum tokens for completion.

    Example:
        >>> provider = AnthropicChatProvider(
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4-20250514",
        ...     max_tokens=2048
        ... )
        >>> response = await provider.chat([{"role": "user", "content": "Hi"}])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: int | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system_prompt: str | None = None,
    ):
        """Initialize the Anthropic chat provider.

        Args:
            api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            model: Model to use (default: claude-sonnet-4-20250514).
            timeout: Request timeout in seconds (default: 120).
            max_tokens: Maximum tokens for completion (default: 4096).
            system_prompt: Optional system prompt to use for all requests.

        Raises:
            AuthenticationError: If no API key is provided.
        """
        from anthropic import Anthropic, AsyncAnthropic

        self._model = model
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt

        # Get API key
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter.",
                provider="anthropic",
            )

        # Get timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv("PROVIDER_TIMEOUT_ANTHROPIC")
            self.timeout = int(env_timeout) if env_timeout else DEFAULT_TIMEOUT

        # Initialize clients
        self.client = Anthropic(api_key=self.api_key, timeout=float(self.timeout))
        self.async_client = AsyncAnthropic(
            api_key=self.api_key, timeout=float(self.timeout)
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"

    @property
    def model(self) -> str:
        """Return the model being used."""
        return self._model

    def supports_native_tools(self) -> bool:
        """Anthropic has native tool calling support."""
        return True

    def is_available(self) -> bool:
        """Check if the provider is available."""
        return bool(self.api_key)

    def validate_config(self) -> list[str]:
        """Validate the provider configuration."""
        errors = []

        if not self.api_key:
            errors.append(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable."
            )

        if not self._model:
            errors.append("Model name is required.")

        return errors

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "provider": self.provider_name,
            "model": self._model,
            "is_local": False,
            "supports_tools": True,
            "max_tokens": self.max_tokens,
        }

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncGenerator[StreamChunk, None]:
        """Send a chat request to Anthropic.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tool definitions (in OpenAI format, will be converted).
            stream: If True, return streaming response.

        Returns:
            ChatResponse for non-streaming, AsyncGenerator for streaming.

        Raises:
            ChatProviderError: On API errors.
        """
        # Normalize messages
        normalized = self._normalize_messages(messages)

        # Extract system prompt from messages
        system_prompt, api_messages = self._format_messages(normalized)

        # Convert tools from OpenAI format to Anthropic format
        anthropic_tools = self._convert_tools(tools) if tools else None

        if stream:
            return self._chat_stream(system_prompt, api_messages, anthropic_tools)
        else:
            return await self._chat_non_stream(system_prompt, api_messages, anthropic_tools)

    def _format_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Format messages for Anthropic API.

        Anthropic expects system prompt separately and has a different
        format for tool use and tool results.

        Args:
            messages: List of ChatMessage objects.

        Returns:
            Tuple of (system_prompt, api_messages).
        """
        system_prompt = self.system_prompt or ""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content or system_prompt
                continue

            if msg.role == "tool" or msg.tool_call_id:
                # Tool result - needs to be in a user message with tool_result block
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }],
                })
            elif msg.tool_calls:
                # Assistant message with tool calls
                # Convert OpenAI tool_calls format to Anthropic content blocks
                content_blocks = []

                # Add text content if present
                if msg.content:
                    content_blocks.append({
                        "type": "text",
                        "text": msg.content,
                    })

                # Add tool_use blocks
                for tc in msg.tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")

                    # Parse arguments if string
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}

                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args,
                    })

                api_messages.append({
                    "role": "assistant",
                    "content": content_blocks,
                })
            else:
                # Regular message
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        return system_prompt, api_messages

    def _convert_tools(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert tools from OpenAI format to Anthropic format.

        OpenAI format:
            {"type": "function", "function": {"name": str, "description": str, "parameters": dict}}

        Anthropic format:
            {"name": str, "description": str, "input_schema": dict}

        Args:
            tools: Tools in OpenAI format.

        Returns:
            Tools in Anthropic format.
        """
        anthropic_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })
            else:
                # Already in Anthropic format or unknown format
                anthropic_tools.append(tool)

        return anthropic_tools

    async def _chat_non_stream(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> ChatResponse:
        """Non-streaming chat completion.

        Args:
            system_prompt: The system prompt.
            messages: Formatted messages for API.
            tools: Optional tools in Anthropic format.

        Returns:
            ChatResponse with complete response.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = tools

        try:
            response = await self.async_client.messages.create(**kwargs)
        except Exception as e:
            raise self._handle_error(e)

        # Parse response - extract text and tool_use blocks
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                # Convert to OpenAI tool_calls format for consistency
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                })

        # Get usage
        tokens_in = response.usage.input_tokens if response.usage else 0
        tokens_out = response.usage.output_tokens if response.usage else 0

        # Map stop reason
        finish_reason = "stop"
        if response.stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif response.stop_reason == "max_tokens":
            finish_reason = "length"
        elif response.stop_reason:
            finish_reason = response.stop_reason

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
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streaming chat completion.

        Args:
            system_prompt: The system prompt.
            messages: Formatted messages for API.
            tools: Optional tools in Anthropic format.

        Yields:
            StreamChunk objects as response streams in.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = tools

        try:
            async with self.async_client.messages.stream(**kwargs) as stream:
                # Track state
                current_tool_id: str | None = None
                current_tool_name: str | None = None
                current_tool_args: str = ""
                tokens_in = 0
                tokens_out = 0
                finish_reason = "stop"

                async for event in stream:
                    # Handle different event types
                    if event.type == "message_start":
                        if event.message and event.message.usage:
                            tokens_in = event.message.usage.input_tokens

                    elif event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            current_tool_args = ""

                            # Yield tool_call_start
                            yield StreamChunk(
                                type="tool_call_start",
                                tool_call={
                                    "id": current_tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": current_tool_name,
                                        "arguments": "",
                                    },
                                },
                            )

                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamChunk(type="content", content=delta.text)
                        elif delta.type == "input_json_delta":
                            current_tool_args += delta.partial_json
                            yield StreamChunk(
                                type="tool_call_delta",
                                delta=delta.partial_json,
                                tool_call_id=current_tool_id or "",
                            )

                    elif event.type == "content_block_stop":
                        # Tool call complete - reset tracking
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_args = ""

                    elif event.type == "message_delta":
                        if event.usage:
                            tokens_out = event.usage.output_tokens
                        if event.delta and event.delta.stop_reason:
                            if event.delta.stop_reason == "tool_use":
                                finish_reason = "tool_calls"
                            elif event.delta.stop_reason == "max_tokens":
                                finish_reason = "length"
                            else:
                                finish_reason = event.delta.stop_reason

                    elif event.type == "message_stop":
                        pass  # Handled in finally

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
        """Convert Anthropic errors to ChatProviderError.

        Args:
            error: The original exception.

        Returns:
            Appropriate ChatProviderError subclass.
        """
        from anthropic import (
            AuthenticationError as AnthropicAuthError,
            RateLimitError as AnthropicRateError,
            NotFoundError as AnthropicNotFoundError,
            APIConnectionError,
            APIStatusError,
        )

        error_msg = str(error)

        if isinstance(error, AnthropicAuthError):
            return AuthenticationError(
                "Invalid or missing API key. Check your ANTHROPIC_API_KEY.",
                provider="anthropic",
                original_error=error,
            )
        elif isinstance(error, AnthropicRateError):
            return RateLimitError(
                f"Rate limit exceeded: {error_msg}. Wait and try again.",
                provider="anthropic",
                original_error=error,
            )
        elif isinstance(error, AnthropicNotFoundError):
            return ModelNotFoundError(
                f"Model not found: {error_msg}",
                provider="anthropic",
                original_error=error,
            )
        elif isinstance(error, APIConnectionError):
            return ProviderUnavailableError(
                f"Could not connect to Anthropic: {error_msg}",
                provider="anthropic",
                original_error=error,
            )
        elif isinstance(error, APIStatusError):
            return ChatProviderError(
                f"Anthropic API error: {error_msg}",
                provider="anthropic",
                original_error=error,
            )
        else:
            return ChatProviderError(
                f"Anthropic error: {error_msg}",
                provider="anthropic",
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
            tool_call_id: The ID of the tool call (tool_use_id).
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

        # For error results, we might want to indicate this
        if is_error:
            content = f"Error: {content}"

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
            tool_calls: List of tool calls in OpenAI format.

        Returns:
            ChatMessage for the assistant with tool calls.
        """
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
