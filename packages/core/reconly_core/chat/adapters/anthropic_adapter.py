"""Anthropic adapter for tool calling.

Converts tool definitions to Anthropic's tool use format and parses
tool calls from Anthropic responses.

Anthropic Format:
    {
        "name": "create_feed",
        "description": "Create a new feed...",
        "input_schema": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }

Anthropic Response Format:
    message.content = [
        {"type": "text", "text": "I'll create that feed for you."},
        {
            "type": "tool_use",
            "id": "toolu_01abc123",
            "name": "create_feed",
            "input": {"name": "Tech News"}
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

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseToolAdapter):
    """Adapter for Anthropic's tool use API.

    Converts ToolDefinitions to Anthropic's tool format and parses tool use
    blocks from Anthropic message responses.

    Example:
        >>> adapter = AnthropicAdapter()
        >>> tools = tool_registry.list_tools()
        >>> anthropic_tools = adapter.format_tools(tools)
        >>>
        >>> # Use with Anthropic client
        >>> response = client.messages.create(
        ...     model="claude-3-sonnet-20240229",
        ...     messages=[...],
        ...     tools=anthropic_tools
        ... )
        >>>
        >>> # Parse tool calls from response
        >>> calls = adapter.parse_tool_calls(response)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to Anthropic format.

        Args:
            tools: List of ToolDefinition objects.

        Returns:
            List of tool definitions in Anthropic format.

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
            >>> print(formatted[0]["name"])
            "create_feed"
        """
        formatted_tools = []

        for tool in tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            formatted_tools.append(anthropic_tool)

        return formatted_tools

    def parse_tool_calls(self, response: Any) -> list[ToolCallRequest]:
        """Parse tool calls from an Anthropic response.

        Args:
            response: Anthropic Message response object or dict.
                Expects response.content to be a list with potential
                tool_use blocks.

        Returns:
            List of ToolCallRequest objects (empty if no tool calls).

        Example:
            >>> response = client.messages.create(...)
            >>> calls = adapter.parse_tool_calls(response)
            >>> if calls:
            ...     for call in calls:
            ...         result = executor.execute(call)
        """
        tool_calls = []

        try:
            # Handle both object and dict responses
            if hasattr(response, "content"):
                content_blocks = response.content
            elif isinstance(response, dict):
                content_blocks = response.get("content", [])
            else:
                logger.warning(f"Unknown response type: {type(response)}")
                return []

            if not content_blocks:
                return []

            for block in content_blocks:
                # Handle both object and dict formats
                if hasattr(block, "type"):
                    block_type = block.type
                else:
                    block_type = block.get("type")

                if block_type != "tool_use":
                    continue

                # Extract tool use data
                if hasattr(block, "id"):
                    call_id = block.id
                    tool_name = block.name
                    parameters = block.input
                else:
                    call_id = block.get("id")
                    tool_name = block.get("name")
                    parameters = block.get("input", {})

                tool_calls.append(
                    ToolCallRequest(
                        tool_name=tool_name,
                        parameters=parameters if isinstance(parameters, dict) else {},
                        call_id=call_id,
                        raw_response=block,
                    )
                )

        except Exception as e:
            logger.error(f"Error parsing Anthropic tool calls: {e}")

        return tool_calls

    def format_tool_result(self, result: ToolCallResult) -> dict[str, Any]:
        """Format a tool result for Anthropic.

        Anthropic expects tool results as a user message containing a
        tool_result content block.

        Args:
            result: The ToolCallResult to format.

        Returns:
            Content block dictionary for including in a user message.

        Example:
            >>> result = ToolCallResult(
            ...     call_id="toolu_01abc123",
            ...     tool_name="create_feed",
            ...     result={"id": 5, "name": "My Feed"}
            ... )
            >>> formatted = adapter.format_tool_result(result)
            >>> # formatted = {
            >>> #     "type": "tool_result",
            >>> #     "tool_use_id": "toolu_01abc123",
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

        tool_result = {
            "type": "tool_result",
            "tool_use_id": result.call_id,
            "content": content,
        }

        if result.is_error:
            tool_result["is_error"] = True

        return tool_result

    def format_tool_results_message(
        self, results: list[ToolCallResult]
    ) -> dict[str, Any]:
        """Format multiple tool results as a user message.

        Anthropic expects all tool results to be in a single user message
        with multiple tool_result content blocks.

        Args:
            results: List of ToolCallResult objects.

        Returns:
            User message dictionary with tool results.

        Example:
            >>> results = [result1, result2]
            >>> msg = adapter.format_tool_results_message(results)
            >>> # msg = {
            >>> #     "role": "user",
            >>> #     "content": [
            >>> #         {"type": "tool_result", "tool_use_id": "...", ...},
            >>> #         {"type": "tool_result", "tool_use_id": "...", ...}
            >>> #     ]
            >>> # }
        """
        return {
            "role": "user",
            "content": [self.format_tool_result(r) for r in results],
        }

    def format_assistant_tool_use(self, response: Any) -> dict[str, Any]:
        """Extract the assistant message with tool use for conversation history.

        When storing conversation history, we need to preserve the assistant's
        message including any tool_use blocks.

        Args:
            response: The Anthropic Message response.

        Returns:
            Assistant message dictionary suitable for history.

        Example:
            >>> msg = adapter.format_assistant_tool_use(response)
            >>> # msg = {
            >>> #     "role": "assistant",
            >>> #     "content": [...]
            >>> # }
        """
        # Handle both object and dict responses
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content", [])
        else:
            content = []

        # Convert content blocks to serializable format
        serialized_content = []
        for block in content:
            if hasattr(block, "type"):
                if block.type == "text":
                    serialized_content.append({
                        "type": "text",
                        "text": block.text,
                    })
                elif block.type == "tool_use":
                    serialized_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
            elif isinstance(block, dict):
                serialized_content.append(block)

        return {
            "role": "assistant",
            "content": serialized_content,
        }

    def get_text_content(self, response: Any) -> str:
        """Extract text content from an Anthropic response.

        Filters out tool_use blocks and returns only the text content.

        Args:
            response: The Anthropic Message response.

        Returns:
            Combined text content from all text blocks.

        Example:
            >>> text = adapter.get_text_content(response)
            >>> print(text)  # "I'll create that feed for you."
        """
        text_parts = []

        # Handle both object and dict responses
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content", [])
        else:
            return ""

        for block in content:
            if hasattr(block, "type"):
                if block.type == "text":
                    text_parts.append(block.text)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

        return "\n".join(text_parts)
