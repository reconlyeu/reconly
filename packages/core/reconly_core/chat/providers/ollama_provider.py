"""Ollama chat provider with prompt-based tool calling and streaming support.

This module provides the OllamaChatProvider class for interacting with locally
running Ollama models. Unlike OpenAI and Anthropic, Ollama models may not have
native tool calling support, so this provider implements tool calling via
prompt engineering.

Features:
- Support for any Ollama model (llama3.2, mistral, codellama, etc.)
- Prompt-based tool calling (model outputs JSON tool calls)
- Streaming responses
- Fully offline operation (no API keys required)

Environment Variables:
    OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
    OLLAMA_MODEL: Default model to use (default: llama3.2)
    PROVIDER_TIMEOUT_OLLAMA: Request timeout in seconds (default: 300)

Example:
    >>> from reconly_core.chat.providers import OllamaChatProvider
    >>>
    >>> provider = OllamaChatProvider(model="llama3.2")
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
import re
import uuid
from typing import Any, AsyncGenerator

from reconly_core.chat.providers.base import (
    BaseChatProvider,
    ChatMessage,
    ChatResponse,
    StreamChunk,
    ChatProviderError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 300  # 5 minutes for local models


# Pattern to find JSON tool calls in model output
TOOL_CALL_PATTERN = re.compile(
    r'```(?:json)?\s*(\{[^`]*?"tool"\s*:[^`]*?\})\s*```'  # Fenced code block
    r'|'
    r'(\{[^{}]*?"tool"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^{}]*\}\s*\})',  # Inline JSON
    re.DOTALL
)

# Simpler fallback pattern
SIMPLE_JSON_PATTERN = re.compile(
    r'\{[^{}]*"tool"[^{}]*\}',
    re.DOTALL
)


class OllamaChatProvider(BaseChatProvider):
    """Chat provider for Ollama with prompt-based tool calling.

    This provider communicates with a local Ollama server and implements
    tool calling via prompt engineering since Ollama models don't have
    native tool calling APIs.

    How tool calling works:
    1. Tools are described in the system prompt with JSON format instructions
    2. Model outputs JSON in a code block when it wants to call a tool
    3. Provider parses the JSON and extracts tool calls
    4. Tool results are added as context for the next turn

    Attributes:
        base_url: Ollama server URL.
        _model: The model to use.
        timeout: Request timeout in seconds.

    Example:
        >>> provider = OllamaChatProvider(
        ...     base_url="http://localhost:11434",
        ...     model="mistral"
        ... )
        >>> response = await provider.chat([{"role": "user", "content": "Hi"}])
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        """Initialize the Ollama chat provider.

        Args:
            base_url: Ollama server URL. Falls back to OLLAMA_BASE_URL env var.
            model: Model to use. Falls back to OLLAMA_MODEL env var or llama3.2.
            timeout: Request timeout in seconds (default: 300 for local models).
        """
        # Get configuration
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self._model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

        # Get timeout
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv("PROVIDER_TIMEOUT_OLLAMA")
            self.timeout = int(env_timeout) if env_timeout else DEFAULT_TIMEOUT

        # We'll initialize httpx clients lazily
        self._sync_client = None
        self._async_client = None

    def _get_sync_client(self):
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            import httpx
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=float(self.timeout),
            )
        return self._sync_client

    def _get_async_client(self):
        """Get or create async HTTP client."""
        if self._async_client is None:
            import httpx
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=float(self.timeout),
            )
        return self._async_client

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "ollama"

    @property
    def model(self) -> str:
        """Return the model being used."""
        return self._model

    def supports_native_tools(self) -> bool:
        """Ollama uses prompt-based tools, not native API support."""
        return False

    def is_available(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            import httpx
            response = httpx.get(f"{self.base_url}/api/tags", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> list[str]:
        """Validate the provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("Ollama base URL is required.")

        if not self.base_url.startswith("http"):
            errors.append("Ollama base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"Ollama server is not reachable at {self.base_url}. "
                "Make sure Ollama is running."
            )

        return errors

    def get_model_info(self) -> dict[str, Any]:
        """Get model information."""
        return {
            "provider": self.provider_name,
            "model": self._model,
            "is_local": True,
            "supports_tools": False,  # No native support
            "base_url": self.base_url,
        }

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncGenerator[StreamChunk, None]:
        """Send a chat request to Ollama.

        Args:
            messages: List of conversation messages.
            tools: Optional list of tool definitions (will be added to system prompt).
            stream: If True, return streaming response.

        Returns:
            ChatResponse for non-streaming, AsyncGenerator for streaming.

        Raises:
            ChatProviderError: On API errors.
        """
        # Normalize messages
        normalized = self._normalize_messages(messages)

        # Format messages for Ollama, injecting tool instructions
        api_messages = self._format_messages(normalized, tools)

        if stream:
            return self._chat_stream(api_messages)
        else:
            return await self._chat_non_stream(api_messages)

    def _format_messages(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Format messages for Ollama API.

        If tools are provided, adds tool instructions to the system prompt.

        Args:
            messages: List of ChatMessage objects.
            tools: Optional tools to inject into system prompt.

        Returns:
            List of message dicts for Ollama.
        """
        api_messages = []
        system_prompt = ""

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content or ""
                continue

            if msg.role == "tool" or msg.tool_call_id:
                # Tool result - format as user context
                api_messages.append({
                    "role": "user",
                    "content": f"Tool '{msg.name or 'unknown'}' result:\n{msg.content}",
                })
            elif msg.tool_calls:
                # Assistant with tool calls - already processed, skip
                # The tool result will provide context
                continue
            else:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        # Build final system prompt with tool instructions
        if tools:
            tool_prompt = self._build_tool_prompt(tools)
            system_prompt = tool_prompt + "\n\n" + system_prompt

        if system_prompt:
            api_messages.insert(0, {"role": "system", "content": system_prompt})

        return api_messages

    def _build_tool_prompt(self, tools: list[dict[str, Any]]) -> str:
        """Build system prompt instructions for tool calling.

        Args:
            tools: List of tool definitions in OpenAI format.

        Returns:
            System prompt text with tool instructions.
        """
        if not tools:
            return ""

        tool_descriptions = []

        for i, tool in enumerate(tools, 1):
            func = tool.get("function", tool)  # Handle both OpenAI and direct formats
            name = func.get("name", "unknown")
            description = func.get("description", "")
            parameters = func.get("parameters", {})

            params_text = self._format_parameters(parameters)
            tool_descriptions.append(
                f"{i}. **{name}**: {description}\n{params_text}"
            )

        tools_text = "\n\n".join(tool_descriptions)

        return f"""You have access to the following tools to help users:

{tools_text}

## How to Use Tools

When you need to use a tool, respond with this EXACT JSON format in a code block:

```json
{{"tool": "tool_name", "parameters": {{"param1": "value1", "param2": "value2"}}}}
```

**Important Rules:**
1. Use tools when the user's request requires taking an action or retrieving data
2. Only use one tool at a time
3. After receiving tool results, provide a natural language response to the user
4. If you don't need a tool, respond normally without JSON
5. Always use valid JSON with proper quoting

## Example Tool Usage

User: "Create a new feed called Tech News"
Assistant: I'll create that feed for you.

```json
{{"tool": "create_feed", "parameters": {{"name": "Tech News"}}}}
```

---

"""

    def _format_parameters(self, parameters: dict[str, Any]) -> str:
        """Format parameter schema as human-readable description.

        Args:
            parameters: JSON Schema for the tool's parameters.

        Returns:
            Formatted parameter description.
        """
        properties = parameters.get("properties", {})
        required = set(parameters.get("required", []))

        if not properties:
            return "   Parameters: None"

        lines = ["   Parameters:"]
        for name, schema in properties.items():
            param_type = schema.get("type", "any")
            description = schema.get("description", "")
            req_marker = "(required)" if name in required else "(optional)"

            if "enum" in schema:
                param_type = f"enum[{', '.join(map(str, schema['enum']))}]"

            lines.append(f"   - `{name}` ({param_type}, {req_marker}): {description}")

        return "\n".join(lines)

    async def _chat_non_stream(
        self,
        messages: list[dict[str, Any]],
    ) -> ChatResponse:
        """Non-streaming chat completion.

        Args:
            messages: Formatted messages for API.

        Returns:
            ChatResponse with complete response.
        """
        client = self._get_async_client()

        try:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise self._handle_error(e)

        # Extract response
        content = data.get("message", {}).get("content", "")

        # Parse tool calls from content
        tool_calls = self._parse_tool_calls(content)

        # If there are tool calls, extract the text without the JSON
        if tool_calls:
            content = self._extract_text_without_tools(content)

        # Get usage
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)

        finish_reason = "tool_calls" if tool_calls else "stop"

        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
            raw_response=data,
        )

    async def _chat_stream(
        self,
        messages: list[dict[str, Any]],
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streaming chat completion.

        Note: For Ollama, we stream the content but tool calls are only
        detected after the full response is collected.

        Args:
            messages: Formatted messages for API.

        Yields:
            StreamChunk objects as response streams in.
        """
        client = self._get_async_client()

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()

                full_content = ""
                tokens_in = 0
                tokens_out = 0

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Check if this is the final message
                    if data.get("done"):
                        tokens_in = data.get("prompt_eval_count", 0)
                        tokens_out = data.get("eval_count", 0)
                        break

                    # Extract content from message
                    message = data.get("message", {})
                    chunk_content = message.get("content", "")

                    if chunk_content:
                        full_content += chunk_content
                        yield StreamChunk(type="content", content=chunk_content)

                # After streaming completes, check for tool calls
                tool_calls = self._parse_tool_calls(full_content)
                finish_reason = "tool_calls" if tool_calls else "stop"

                # If we found tool calls, yield them
                for tc in tool_calls:
                    yield StreamChunk(
                        type="tool_call_start",
                        tool_call=tc,
                    )

                # Yield done chunk
                yield StreamChunk(
                    type="done",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    finish_reason=finish_reason,
                )

        except Exception as e:
            yield StreamChunk(type="error", error=str(e))

    def _parse_tool_calls(self, content: str) -> list[dict[str, Any]]:
        """Parse tool calls from model output.

        Looks for JSON tool calls in the format:
        ```json
        {"tool": "name", "parameters": {...}}
        ```

        Args:
            content: Model output text.

        Returns:
            List of tool calls in OpenAI format (for consistency).
        """
        tool_calls = []

        # Try the main pattern first
        matches = TOOL_CALL_PATTERN.findall(content)
        for match in matches:
            # match is a tuple from alternation groups
            json_str = match[0] or match[1]
            if json_str:
                tc = self._parse_json_tool_call(json_str.strip())
                if tc:
                    tool_calls.append(tc)

        # Fallback to simpler pattern
        if not tool_calls:
            simple_matches = SIMPLE_JSON_PATTERN.findall(content)
            for json_str in simple_matches:
                tc = self._parse_json_tool_call(json_str.strip())
                if tc:
                    tool_calls.append(tc)
                    break  # Only take first with simple pattern

        return tool_calls

    def _parse_json_tool_call(self, json_str: str) -> dict[str, Any] | None:
        """Parse a single JSON string as a tool call.

        Args:
            json_str: JSON string potentially containing a tool call.

        Returns:
            Tool call in OpenAI format, or None if invalid.
        """
        try:
            data = json.loads(json_str)

            if not isinstance(data, dict):
                return None

            tool_name = data.get("tool")
            if not tool_name:
                return None

            parameters = data.get("parameters", {})
            if not isinstance(parameters, dict):
                parameters = {}

            # Generate unique call ID
            call_id = f"ollama_{uuid.uuid4().hex[:12]}"

            # Return in OpenAI format for consistency
            return {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(parameters, ensure_ascii=False),
                },
            }

        except json.JSONDecodeError:
            return None

    def _extract_text_without_tools(self, content: str) -> str:
        """Extract natural language text, removing tool call JSON.

        Args:
            content: Full model output.

        Returns:
            Text with tool call JSON removed.
        """
        # Remove fenced code blocks with tool calls
        text = re.sub(
            r'```(?:json)?\s*\{[^`]*?"tool"\s*:[^`]*?\}\s*```',
            '',
            content,
            flags=re.DOTALL
        )

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _handle_error(self, error: Exception) -> ChatProviderError:
        """Convert Ollama errors to ChatProviderError.

        Args:
            error: The original exception.

        Returns:
            Appropriate ChatProviderError subclass.
        """
        import httpx

        error_msg = str(error)

        if isinstance(error, httpx.ConnectError):
            return ProviderUnavailableError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running.",
                provider="ollama",
                original_error=error,
            )
        elif isinstance(error, httpx.TimeoutException):
            return ProviderUnavailableError(
                f"Ollama request timed out after {self.timeout}s. "
                "Try a faster model or increase timeout.",
                provider="ollama",
                original_error=error,
            )
        elif isinstance(error, httpx.HTTPStatusError):
            if error.response.status_code == 404:
                return ChatProviderError(
                    f"Model '{self._model}' not found. Run 'ollama pull {self._model}' to download it.",
                    provider="ollama",
                    original_error=error,
                )
            return ChatProviderError(
                f"Ollama API error: {error_msg}",
                provider="ollama",
                original_error=error,
            )
        else:
            return ChatProviderError(
                f"Ollama error: {error_msg}",
                provider="ollama",
                original_error=error,
            )

    def format_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any,
        is_error: bool = False,
    ) -> ChatMessage:
        """Format a tool result for including in the conversation.

        For Ollama, tool results are formatted as user context messages
        since there's no native tool result format.

        Args:
            tool_call_id: The ID of the tool call.
            tool_name: Name of the tool.
            result: The result data.
            is_error: Whether this is an error result.

        Returns:
            ChatMessage with the tool result.
        """
        if isinstance(result, str):
            result_text = result
        else:
            try:
                result_text = json.dumps(result, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                result_text = str(result)

        if is_error:
            content = f"Tool '{tool_name}' failed with error:\n{result_text}"
        else:
            content = f"Tool '{tool_name}' executed successfully:\n{result_text}"

        return ChatMessage(
            role="user",
            content=content,
            tool_call_id=tool_call_id,
            name=tool_name,
        )

    def list_available_models(self) -> list[str]:
        """List models available on the Ollama server.

        Returns:
            List of model names.
        """
        try:
            client = self._get_sync_client()
            response = client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []
