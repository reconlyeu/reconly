"""LMStudio chat provider using OpenAI-compatible API.

LMStudio runs locally and provides an OpenAI-compatible API, so this provider
uses the OpenAI SDK with a custom base_url. Supports native tool calling and
streaming responses.

Environment Variables:
    LMSTUDIO_BASE_URL: Server URL (default: http://localhost:1234/v1)
    LMSTUDIO_MODEL: Default model (auto-detected if not set)
    PROVIDER_TIMEOUT_LMSTUDIO: Request timeout in seconds (default: 300)
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
    ModelNotFoundError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_TIMEOUT = 300  # 5 minutes for local models
DEFAULT_MAX_TOKENS = 4096


class LMStudioChatProvider(BaseChatProvider):
    """Chat provider for LMStudio using OpenAI-compatible API.

    Supports native tool calling, streaming responses, and token tracking.
    Auto-detects loaded models if LMSTUDIO_MODEL is not set.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        # Get configuration
        self.base_url = base_url or os.getenv("LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)
        self._model = model or os.getenv("LMSTUDIO_MODEL")
        self.max_tokens = max_tokens

        # Get timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv("PROVIDER_TIMEOUT_LMSTUDIO")
            self.timeout = int(env_timeout) if env_timeout else DEFAULT_TIMEOUT

        # Lazy initialization - client created on first use
        self._async_client = None

        # Auto-detect model if not specified
        if not self._model:
            available = self.list_available_models()
            if available:
                self._model = available[0]
                logger.info(f"LMStudio: Auto-detected model '{self._model}'")

    def _get_async_client(self):
        """Get or create async OpenAI client."""
        if self._async_client is None:
            from openai import AsyncOpenAI

            self._async_client = AsyncOpenAI(
                api_key="lm-studio",  # Dummy key - LMStudio ignores this
                base_url=self.base_url,
                timeout=float(self.timeout),
            )
        return self._async_client

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "lmstudio"

    @property
    def model(self) -> str:
        """Return the model being used."""
        return self._model or "unknown"

    def supports_native_tools(self) -> bool:
        """LMStudio has native tool calling support (OpenAI-compatible)."""
        return True

    def is_available(self) -> bool:
        """Check if LMStudio server is reachable."""
        try:
            import httpx

            # Check /v1/models endpoint (OpenAI-compatible)
            response = httpx.get(f"{self.base_url}/models", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> list[str]:
        """Validate the provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("LMStudio base URL is required.")

        if self.base_url and not self.base_url.startswith("http"):
            errors.append("LMStudio base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"LMStudio server is not reachable at {self.base_url}. "
                "Make sure LMStudio is running with the local server enabled. "
                "You can enable it from LMStudio's Developer tab."
            )

        # Check if model exists
        if self._model:
            available = self.list_available_models()
            if available and self._model not in available:
                errors.append(
                    f"Model '{self._model}' is not loaded in LMStudio. "
                    f"Available models: {available}. "
                    "Load the model in LMStudio before using it."
                )
        elif not self.list_available_models():
            errors.append(
                "No model specified and none available. "
                "Load a model in LMStudio before using this provider."
            )

        return errors

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "provider": self.provider_name,
            "model": self._model or "unknown",
            "is_local": True,
            "supports_tools": True,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
        }

    def list_available_models(self) -> list[str]:
        """List models loaded in LMStudio."""
        try:
            import httpx

            response = httpx.get(f"{self.base_url}/models", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                # LMStudio returns OpenAI-compatible format: {"data": [{"id": "model-name", ...}]}
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return []

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncGenerator[StreamChunk, None]:
        """Send a chat request to LMStudio."""
        # Normalize messages
        normalized = self._normalize_messages(messages)

        # Format messages for OpenAI-compatible API
        api_messages = self._format_messages(normalized)

        if stream:
            return self._chat_stream(api_messages, tools)
        else:
            return await self._chat_non_stream(api_messages, tools)

    def _format_messages(
        self, messages: list[ChatMessage]
    ) -> list[dict[str, Any]]:
        """Format messages for OpenAI-compatible API."""
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
                    "content": msg.content or "",
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
        """Non-streaming chat completion."""
        if not self._model:
            raise ChatProviderError(
                "No model available. Load a model in LMStudio before using this provider.",
                provider="lmstudio",
            )

        client = self._get_async_client()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools

        try:
            response = await client.chat.completions.create(**kwargs)
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
        """Streaming chat completion."""
        if not self._model:
            yield StreamChunk(
                type="error",
                error="No model available. Load a model in LMStudio before using this provider.",
            )
            return

        client = self._get_async_client()

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
            stream = await client.chat.completions.create(**kwargs)
        except Exception as e:
            error = self._handle_error(e)
            yield StreamChunk(type="error", error=str(error))
            return

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
        """Convert OpenAI SDK errors to ChatProviderError."""
        from openai import (
            NotFoundError as OpenAINotFoundError,
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
        )

        error_msg = str(error)

        if isinstance(error, OpenAINotFoundError):
            return ModelNotFoundError(
                f"Model not found in LMStudio: {error_msg}. "
                "Make sure the model is loaded in LMStudio.",
                provider="lmstudio",
                original_error=error,
            )
        elif isinstance(error, APIConnectionError):
            return ProviderUnavailableError(
                f"Could not connect to LMStudio at {self.base_url}. "
                "Make sure LMStudio is running with the local server enabled.",
                provider="lmstudio",
                original_error=error,
            )
        elif isinstance(error, APITimeoutError):
            return ProviderUnavailableError(
                f"LMStudio request timed out after {self.timeout}s. "
                "Try a faster model or increase timeout.",
                provider="lmstudio",
                original_error=error,
            )
        elif isinstance(error, APIStatusError):
            return ChatProviderError(
                f"LMStudio API error: {error_msg}",
                provider="lmstudio",
                original_error=error,
            )
        else:
            return ChatProviderError(
                f"LMStudio error: {error_msg}",
                provider="lmstudio",
                original_error=error,
            )

    def format_tool_result(
        self,
        tool_call_id: str,
        result: Any,
        is_error: bool = False,
    ) -> ChatMessage:
        """Format a tool result as a ChatMessage."""
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
        """Format an assistant message with tool calls."""
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
