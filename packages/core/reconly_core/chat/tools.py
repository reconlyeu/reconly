"""Tool definition and registry for LLM chat tool calling.

This module provides a decorator-based registry for tools that can be called
by the LLM during chat conversations. Tools are defined in a provider-agnostic
format and converted to provider-specific formats at runtime.

Example:
    >>> from reconly_core.chat.tools import tool_registry, ToolDefinition
    >>>
    >>> @tool_registry.register
    >>> def list_feeds_tool():
    ...     return ToolDefinition(
    ...         name="list_feeds",
    ...         description="List all feeds in the system",
    ...         parameters={
    ...             "type": "object",
    ...             "properties": {},
    ...             "required": []
    ...         },
    ...         handler=list_feeds_handler
    ...     )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Type for tool handlers - can be sync or async
ToolHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the LLM.

    Attributes:
        name: Unique identifier for the tool (e.g., "create_feed", "search_digests")
        description: Human-readable description of what the tool does.
            This is sent to the LLM to help it decide when to use the tool.
        parameters: JSON Schema defining the tool's parameters.
            Must be a valid JSON Schema object with "type": "object".
        handler: Callable that executes the tool. Can be sync or async.
            Receives keyword arguments matching the parameters schema.
        requires_confirmation: If True, the UI should prompt for user
            confirmation before executing (for destructive actions).
        category: Optional category for grouping tools in documentation/UI.
        examples: Optional list of example invocations for documentation.

    Example:
        >>> ToolDefinition(
        ...     name="create_feed",
        ...     description="Create a new feed with specified sources and schedule",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "name": {"type": "string", "description": "Feed name"},
        ...             "source_ids": {
        ...                 "type": "array",
        ...                 "items": {"type": "integer"},
        ...                 "description": "IDs of sources to include"
        ...             },
        ...             "cron_schedule": {
        ...                 "type": "string",
        ...                 "description": "Cron expression for schedule"
        ...             }
        ...         },
        ...         "required": ["name"]
        ...     },
        ...     handler=create_feed_handler,
        ...     requires_confirmation=False
        ... )
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    requires_confirmation: bool = False
    category: str | None = None
    examples: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate the tool definition."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not self.description:
            raise ValueError("Tool description cannot be empty")
        if not isinstance(self.parameters, dict):
            raise ValueError("Parameters must be a dict (JSON Schema)")
        if self.parameters.get("type") != "object":
            raise ValueError("Parameters schema must have type: 'object'")
        if not callable(self.handler):
            raise ValueError("Handler must be callable")


class ToolRegistry:
    """Registry for tools that can be called by the LLM.

    The registry provides decorator-based registration and lookup of tools.
    Tools are stored by name and can be retrieved individually or as a list.

    Example:
        >>> registry = ToolRegistry()
        >>>
        >>> @registry.register
        >>> def my_tool():
        ...     return ToolDefinition(
        ...         name="my_tool",
        ...         description="Does something useful",
        ...         parameters={"type": "object", "properties": {}, "required": []},
        ...         handler=my_handler
        ...     )
        >>>
        >>> # Get a specific tool
        >>> tool = registry.get("my_tool")
        >>>
        >>> # Get all tools
        >>> all_tools = registry.list_tools()
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self, factory: Callable[[], ToolDefinition]
    ) -> Callable[[], ToolDefinition]:
        """Decorator to register a tool factory function.

        The factory function should return a ToolDefinition. It is called
        immediately upon registration and the tool is stored in the registry.

        Args:
            factory: A callable that returns a ToolDefinition.

        Returns:
            The original factory function (unchanged).

        Raises:
            TypeError: If factory doesn't return a ToolDefinition.
            ValueError: If tool name is already registered.

        Example:
            >>> @tool_registry.register
            >>> def create_feed_tool():
            ...     return ToolDefinition(
            ...         name="create_feed",
            ...         description="Create a new feed",
            ...         parameters={"type": "object", "properties": {}, "required": []},
            ...         handler=create_feed_handler
            ...     )
        """
        # Call the factory to get the tool definition
        tool_def = factory()

        if not isinstance(tool_def, ToolDefinition):
            raise TypeError(
                f"Tool factory {factory.__name__} must return a ToolDefinition, "
                f"got {type(tool_def).__name__}"
            )

        # Check for duplicate registration
        if tool_def.name in self._tools:
            logger.warning(
                f"Tool '{tool_def.name}' is already registered, overwriting"
            )

        self._tools[tool_def.name] = tool_def
        logger.debug(f"Registered tool '{tool_def.name}'")

        return factory

    def register_tool(self, tool_def: ToolDefinition) -> None:
        """Register a tool definition directly (without decorator).

        Args:
            tool_def: The tool definition to register.

        Raises:
            TypeError: If tool_def is not a ToolDefinition.
            ValueError: If tool name is already registered.

        Example:
            >>> tool = ToolDefinition(
            ...     name="my_tool",
            ...     description="Does something",
            ...     parameters={"type": "object", "properties": {}, "required": []},
            ...     handler=my_handler
            ... )
            >>> tool_registry.register_tool(tool)
        """
        if not isinstance(tool_def, ToolDefinition):
            raise TypeError(
                f"Expected ToolDefinition, got {type(tool_def).__name__}"
            )

        if tool_def.name in self._tools:
            logger.warning(
                f"Tool '{tool_def.name}' is already registered, overwriting"
            )

        self._tools[tool_def.name] = tool_def
        logger.debug(f"Registered tool '{tool_def.name}' (direct)")

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name.

        Args:
            name: The tool name to look up.

        Returns:
            The ToolDefinition if found, None otherwise.

        Example:
            >>> tool = tool_registry.get("create_feed")
            >>> if tool:
            ...     print(tool.description)
        """
        return self._tools.get(name)

    def get_required(self, name: str) -> ToolDefinition:
        """Get a tool by name, raising if not found.

        Args:
            name: The tool name to look up.

        Returns:
            The ToolDefinition.

        Raises:
            KeyError: If the tool is not registered.

        Example:
            >>> tool = tool_registry.get_required("create_feed")
        """
        tool = self._tools.get(name)
        if tool is None:
            available = list(self._tools.keys())
            raise KeyError(
                f"Tool '{name}' is not registered. "
                f"Available tools: {available}"
            )
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        """Get all registered tools.

        Returns:
            List of all ToolDefinition objects.

        Example:
            >>> tools = tool_registry.list_tools()
            >>> for tool in tools:
            ...     print(f"{tool.name}: {tool.description}")
        """
        return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.

        Example:
            >>> names = tool_registry.list_tool_names()
            >>> print(names)  # ['create_feed', 'list_feeds', ...]
        """
        return list(self._tools.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: The tool name to check.

        Returns:
            True if the tool is registered, False otherwise.

        Example:
            >>> if tool_registry.is_registered("create_feed"):
            ...     print("Tool exists!")
        """
        return name in self._tools

    def get_by_category(self, category: str) -> list[ToolDefinition]:
        """Get all tools in a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of tools in the specified category.

        Example:
            >>> feed_tools = tool_registry.get_by_category("feeds")
        """
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]

    def get_safe_tools(self) -> list[ToolDefinition]:
        """Get all tools that don't require confirmation.

        Returns:
            List of tools that are safe to execute without confirmation.

        Example:
            >>> safe_tools = tool_registry.get_safe_tools()
        """
        return [
            tool for tool in self._tools.values()
            if not tool.requires_confirmation
        ]

    def get_destructive_tools(self) -> list[ToolDefinition]:
        """Get all tools that require confirmation.

        Returns:
            List of tools that require user confirmation before execution.

        Example:
            >>> dangerous_tools = tool_registry.get_destructive_tools()
        """
        return [
            tool for tool in self._tools.values()
            if tool.requires_confirmation
        ]

    def clear(self) -> None:
        """Remove all registered tools.

        Primarily useful for testing.

        Example:
            >>> tool_registry.clear()
        """
        self._tools.clear()
        logger.debug("Cleared all tools from registry")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool name is registered."""
        return name in self._tools

    def __iter__(self):
        """Iterate over tool names."""
        return iter(self._tools)


# Global registry instance
tool_registry = ToolRegistry()
