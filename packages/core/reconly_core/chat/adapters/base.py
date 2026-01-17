"""Base adapter for converting tool definitions to provider-specific formats.

This module defines the abstract base class for tool adapters and common
data structures used across all adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from reconly_core.chat.tools import ToolDefinition


@dataclass
class ToolCallRequest:
    """Represents a parsed tool call from an LLM response.

    This is the standardized format returned by all adapters when parsing
    tool calls from LLM responses, regardless of the provider.

    Attributes:
        tool_name: Name of the tool to call.
        parameters: Dictionary of parameter values.
        call_id: Provider-specific call ID (for correlating responses).
            OpenAI and Anthropic provide this; Ollama generates one.
        raw_response: The original provider response for debugging.

    Example:
        >>> call = ToolCallRequest(
        ...     tool_name="create_feed",
        ...     parameters={"name": "Tech News", "source_ids": [1, 2, 3]},
        ...     call_id="call_abc123"
        ... )
    """

    tool_name: str
    parameters: dict[str, Any]
    call_id: str | None = None
    raw_response: Any = None


@dataclass
class ToolCallResult:
    """Result of a tool execution, formatted for the LLM.

    Attributes:
        call_id: The call_id from the original ToolCallRequest.
        tool_name: Name of the tool that was called.
        result: The result data from the tool (will be JSON serialized).
        is_error: True if the tool execution failed.

    Example:
        >>> result = ToolCallResult(
        ...     call_id="call_abc123",
        ...     tool_name="create_feed",
        ...     result={"id": 5, "name": "Tech News"},
        ...     is_error=False
        ... )
    """

    call_id: str
    tool_name: str
    result: Any
    is_error: bool = False


class BaseToolAdapter(ABC):
    """Abstract base class for tool adapters.

    Each LLM provider requires tools to be formatted differently. Adapters
    handle the conversion from ToolDefinition to provider-specific format
    and from provider responses back to standardized ToolCallRequest.

    Subclasses must implement:
        - format_tools(): Convert ToolDefinitions to provider format
        - parse_tool_calls(): Extract tool calls from LLM response
        - format_tool_result(): Format tool results for the LLM

    Example:
        >>> class MyProviderAdapter(BaseToolAdapter):
        ...     def format_tools(self, tools):
        ...         # Convert to provider format
        ...         pass
        ...
        ...     def parse_tool_calls(self, response):
        ...         # Extract tool calls from response
        ...         pass
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider this adapter handles.

        Returns:
            Provider name (e.g., "openai", "anthropic", "ollama").
        """
        pass

    @abstractmethod
    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to provider-specific format.

        Args:
            tools: List of ToolDefinition objects to convert.

        Returns:
            List of dictionaries in the provider's expected format.

        Example:
            >>> tools = tool_registry.list_tools()
            >>> formatted = adapter.format_tools(tools)
        """
        pass

    @abstractmethod
    def parse_tool_calls(self, response: Any) -> list[ToolCallRequest]:
        """Parse tool calls from an LLM response.

        Args:
            response: The raw response from the LLM provider.
                Type varies by provider (dict, object, etc.).

        Returns:
            List of ToolCallRequest objects (empty if no tool calls).

        Example:
            >>> response = llm.chat(messages, tools)
            >>> calls = adapter.parse_tool_calls(response)
            >>> for call in calls:
            ...     print(f"Tool: {call.tool_name}, Params: {call.parameters}")
        """
        pass

    @abstractmethod
    def format_tool_result(self, result: ToolCallResult) -> dict[str, Any]:
        """Format a tool result for inclusion in the next LLM request.

        Args:
            result: The ToolCallResult to format.

        Returns:
            Dictionary in the provider's expected format for tool results.

        Example:
            >>> result = ToolCallResult(
            ...     call_id="call_123",
            ...     tool_name="create_feed",
            ...     result={"id": 5, "name": "My Feed"}
            ... )
            >>> formatted = adapter.format_tool_result(result)
        """
        pass

    def supports_native_tools(self) -> bool:
        """Check if this provider supports native tool calling.

        Returns:
            True if the provider has native tool/function calling API,
            False if tools are implemented via prompt engineering.

        Default implementation returns True. Override in adapters
        that use prompt-based tools (e.g., Ollama).
        """
        return True

    def get_system_prompt_prefix(self, tools: list[ToolDefinition]) -> str | None:
        """Get any system prompt additions needed for tool support.

        Some providers (especially Ollama) need instructions in the system
        prompt to enable tool calling behavior.

        Args:
            tools: List of tools being made available.

        Returns:
            System prompt text to prepend, or None if not needed.

        Default implementation returns None. Override in adapters
        that need prompt modifications.
        """
        return None
