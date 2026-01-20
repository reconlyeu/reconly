"""OpenAI adapter for tool calling.

Converts tool definitions to OpenAI's function calling format and parses
tool calls from OpenAI responses.

OpenAI Format:
    {
        "type": "function",
        "function": {
            "name": "create_feed",
            "description": "Create a new feed...",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }

OpenAI Response Format:
    message.tool_calls = [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "create_feed",
                "arguments": "{\"name\": \"Tech News\"}"
            }
        }
    ]
"""

from __future__ import annotations

import json
import logging
from typing import Any

from reconly_core.chat.tools import ToolDefinition
from reconly_core.chat.adapters.base import (
    BaseToolAdapter,
    ToolCallRequest,
    ToolCallResult,
)
from reconly_core.chat.adapters.registry import register_adapter

logger = logging.getLogger(__name__)


@register_adapter("openai")
class OpenAIAdapter(BaseToolAdapter):
    """Adapter for OpenAI's function calling API.

    Converts ToolDefinitions to OpenAI's tool format and parses tool calls
    from OpenAI chat completion responses.

    Example:
        >>> adapter = OpenAIAdapter()
        >>> tools = tool_registry.list_tools()
        >>> openai_tools = adapter.format_tools(tools)
        >>>
        >>> # Use with OpenAI client
        >>> response = client.chat.completions.create(
        ...     model="gpt-4",
        ...     messages=[...],
        ...     tools=openai_tools
        ... )
        >>>
        >>> # Parse tool calls from response
        >>> calls = adapter.parse_tool_calls(response)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to OpenAI format.

        Args:
            tools: List of ToolDefinition objects.

        Returns:
            List of tool definitions in OpenAI format.

        Example:
            >>> tools = [
            ...     ToolDefinition(
            ...         name="create_feed",
            ...         description="Create a new feed",
            ...         parameters={
            ...             "type": "object",
            ...             "properties": {"name": {"type": "string"}},
            ...             "required": ["name"]
            ...         },
            ...         handler=handler
            ...     )
            ... ]
            >>> formatted = adapter.format_tools(tools)
            >>> print(formatted[0]["function"]["name"])
            "create_feed"
        """
        formatted_tools = []

        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            formatted_tools.append(openai_tool)

        return formatted_tools

    def parse_tool_calls(self, response: Any) -> list[ToolCallRequest]:
        """Parse tool calls from an OpenAI response.

        Args:
            response: OpenAI ChatCompletion response object or dict.
                Expects response.choices[0].message.tool_calls format.

        Returns:
            List of ToolCallRequest objects (empty if no tool calls).

        Example:
            >>> response = client.chat.completions.create(...)
            >>> calls = adapter.parse_tool_calls(response)
            >>> if calls:
            ...     for call in calls:
            ...         result = executor.execute(call)
        """
        tool_calls = []

        try:
            # Handle both object and dict responses
            if hasattr(response, "choices"):
                message = response.choices[0].message
            elif isinstance(response, dict):
                message = response.get("choices", [{}])[0].get("message", {})
            else:
                logger.warning(f"Unknown response type: {type(response)}")
                return []

            # Get tool_calls from message
            if hasattr(message, "tool_calls"):
                raw_tool_calls = message.tool_calls
            elif isinstance(message, dict):
                raw_tool_calls = message.get("tool_calls")
            else:
                raw_tool_calls = None

            if not raw_tool_calls:
                return []

            for tc in raw_tool_calls:
                # Handle both object and dict formats
                if hasattr(tc, "id"):
                    call_id = tc.id
                    func_name = tc.function.name
                    func_args = tc.function.arguments
                else:
                    call_id = tc.get("id")
                    func_name = tc.get("function", {}).get("name")
                    func_args = tc.get("function", {}).get("arguments", "{}")

                # Parse arguments JSON
                try:
                    if isinstance(func_args, str):
                        parameters = json.loads(func_args)
                    else:
                        parameters = func_args or {}
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to parse tool arguments for {func_name}: {e}"
                    )
                    parameters = {}

                tool_calls.append(
                    ToolCallRequest(
                        tool_name=func_name,
                        parameters=parameters,
                        call_id=call_id,
                        raw_response=tc,
                    )
                )

        except Exception as e:
            logger.error(f"Error parsing OpenAI tool calls: {e}")

        return tool_calls

    def format_tool_result(self, result: ToolCallResult) -> dict[str, Any]:
        """Format a tool result for OpenAI.

        OpenAI expects tool results as a message with role "tool" and
        the corresponding tool_call_id.

        Args:
            result: The ToolCallResult to format.

        Returns:
            Message dictionary for including in the messages array.

        Example:
            >>> result = ToolCallResult(
            ...     call_id="call_abc123",
            ...     tool_name="create_feed",
            ...     result={"id": 5, "name": "My Feed"}
            ... )
            >>> formatted = adapter.format_tool_result(result)
            >>> # formatted = {
            >>> #     "role": "tool",
            >>> #     "tool_call_id": "call_abc123",
            >>> #     "content": '{"id": 5, "name": "My Feed"}'
            >>> # }
        """
        # Serialize result to JSON string
        if isinstance(result.result, str):
            content = result.result
        else:
            try:
                content = json.dumps(result.result, ensure_ascii=False)
            except (TypeError, ValueError):
                content = str(result.result)

        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "content": content,
        }

    def format_assistant_tool_call(self, calls: list[ToolCallRequest]) -> dict[str, Any]:
        """Format tool calls as an assistant message for conversation history.

        When storing conversation history, tool calls from the assistant need
        to be formatted as an assistant message with tool_calls field.

        Args:
            calls: List of ToolCallRequest objects from the assistant.

        Returns:
            Assistant message dictionary with tool_calls.

        Example:
            >>> calls = adapter.parse_tool_calls(response)
            >>> msg = adapter.format_assistant_tool_call(calls)
            >>> # msg = {
            >>> #     "role": "assistant",
            >>> #     "content": None,
            >>> #     "tool_calls": [...]
            >>> # }
        """
        tool_calls = []
        for call in calls:
            tool_calls.append({
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.tool_name,
                    "arguments": json.dumps(call.parameters, ensure_ascii=False),
                },
            })

        return {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
