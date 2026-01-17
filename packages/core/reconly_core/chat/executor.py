"""Tool executor for safely invoking tool handlers.

This module provides the ToolExecutor class that safely invokes tool handlers
with proper error handling, parameter validation, and result formatting.
It supports both synchronous and asynchronous handlers.

Example:
    >>> from reconly_core.chat.executor import ToolExecutor
    >>> from reconly_core.chat.tools import tool_registry
    >>> from reconly_core.chat.adapters.base import ToolCallRequest
    >>>
    >>> executor = ToolExecutor(tool_registry)
    >>> call = ToolCallRequest(
    ...     tool_name="list_feeds",
    ...     parameters={},
    ...     call_id="call_123"
    ... )
    >>> result = await executor.execute(call)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from reconly_core.chat.tools import ToolDefinition, ToolRegistry
from reconly_core.chat.adapters.base import ToolCallRequest, ToolCallResult

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when a tool execution fails.

    Attributes:
        tool_name: Name of the tool that failed.
        message: Error message describing the failure.
        original_error: The underlying exception, if any.
        is_validation_error: True if the error was due to parameter validation.
    """

    def __init__(
        self,
        tool_name: str,
        message: str,
        original_error: Exception | None = None,
        is_validation_error: bool = False,
    ):
        self.tool_name = tool_name
        self.message = message
        self.original_error = original_error
        self.is_validation_error = is_validation_error
        super().__init__(f"Tool '{tool_name}' failed: {message}")


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        call_id: The ID from the original tool call request.
        tool_name: Name of the tool that was executed.
        success: True if execution succeeded without errors.
        result: The result data from the handler (if successful).
        error: Error message (if failed).
        execution_time_ms: Time taken to execute in milliseconds.
        requires_confirmation: True if this was a confirmation-required tool.
        confirmed: True if user confirmed (for confirmation-required tools).

    Example:
        >>> result = ToolResult(
        ...     call_id="call_123",
        ...     tool_name="create_feed",
        ...     success=True,
        ...     result={"id": 5, "name": "My Feed"},
        ...     execution_time_ms=150
        ... )
    """

    call_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0
    requires_confirmation: bool = False
    confirmed: bool = True

    def to_tool_call_result(self) -> ToolCallResult:
        """Convert to ToolCallResult for adapter formatting.

        Returns:
            ToolCallResult suitable for passing to adapter.format_tool_result()
        """
        if self.success:
            return ToolCallResult(
                call_id=self.call_id,
                tool_name=self.tool_name,
                result=self.result,
                is_error=False,
            )
        else:
            return ToolCallResult(
                call_id=self.call_id,
                tool_name=self.tool_name,
                result={"error": self.error},
                is_error=True,
            )


class ToolExecutor:
    """Executes tool handlers safely with error handling and validation.

    The executor handles:
    - Looking up tools in the registry
    - Validating parameters against the JSON schema
    - Invoking handlers (sync or async)
    - Catching and formatting errors
    - Timing execution

    Example:
        >>> registry = ToolRegistry()
        >>> # ... register tools ...
        >>> executor = ToolExecutor(registry)
        >>>
        >>> # Execute a tool call
        >>> call = ToolCallRequest(
        ...     tool_name="create_feed",
        ...     parameters={"name": "Tech News"},
        ...     call_id="call_abc123"
        ... )
        >>> result = await executor.execute(call)
        >>>
        >>> if result.success:
        ...     print(f"Created feed: {result.result}")
        ... else:
        ...     print(f"Error: {result.error}")
    """

    def __init__(
        self,
        registry: ToolRegistry,
        validate_parameters: bool = True,
        max_result_size: int = 100_000,
    ):
        """Initialize the tool executor.

        Args:
            registry: The tool registry to look up tools from.
            validate_parameters: Whether to validate parameters against schema.
            max_result_size: Maximum size of result in characters before truncation.
        """
        self.registry = registry
        self.validate_parameters = validate_parameters
        self.max_result_size = max_result_size

    async def execute(
        self,
        call: ToolCallRequest,
        context: dict[str, Any] | None = None,
        confirmed: bool = True,
    ) -> ToolResult:
        """Execute a tool call.

        Args:
            call: The tool call request to execute.
            context: Optional context dict passed to the handler.
                Common keys: 'db' (database session), 'user_id', etc.
            confirmed: For tools requiring confirmation, whether user confirmed.
                If False and tool requires confirmation, execution is skipped.

        Returns:
            ToolResult with success status and result/error.

        Example:
            >>> result = await executor.execute(
            ...     call,
            ...     context={"db": db_session},
            ...     confirmed=True
            ... )
        """
        start_time = datetime.now()

        # Look up the tool
        tool = self.registry.get(call.tool_name)
        if tool is None:
            return ToolResult(
                call_id=call.call_id or "",
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: '{call.tool_name}'. "
                      f"Available tools: {self.registry.list_tool_names()}",
                execution_time_ms=0,
            )

        # Check confirmation for destructive tools
        if tool.requires_confirmation and not confirmed:
            return ToolResult(
                call_id=call.call_id or "",
                tool_name=call.tool_name,
                success=False,
                error="This action requires user confirmation.",
                requires_confirmation=True,
                confirmed=False,
                execution_time_ms=0,
            )

        # Validate parameters
        if self.validate_parameters:
            validation_error = self._validate_parameters(tool, call.parameters)
            if validation_error:
                return ToolResult(
                    call_id=call.call_id or "",
                    tool_name=call.tool_name,
                    success=False,
                    error=f"Parameter validation failed: {validation_error}",
                    execution_time_ms=0,
                )

        # Execute the handler
        try:
            result = await self._invoke_handler(tool.handler, call.parameters, context)

            # Truncate large results
            result = self._truncate_result(result)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return ToolResult(
                call_id=call.call_id or "",
                tool_name=call.tool_name,
                success=True,
                result=result,
                execution_time_ms=execution_time,
                requires_confirmation=tool.requires_confirmation,
                confirmed=confirmed,
            )

        except ToolExecutionError as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Tool execution error: {e}")
            return ToolResult(
                call_id=call.call_id or "",
                tool_name=call.tool_name,
                success=False,
                error=str(e.message),
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(
                f"Unexpected error executing tool '{call.tool_name}': {error_msg}\n"
                f"{traceback.format_exc()}"
            )
            return ToolResult(
                call_id=call.call_id or "",
                tool_name=call.tool_name,
                success=False,
                error=error_msg,
                execution_time_ms=execution_time,
            )

    async def execute_batch(
        self,
        calls: list[ToolCallRequest],
        context: dict[str, Any] | None = None,
        confirmed: bool = True,
    ) -> list[ToolResult]:
        """Execute multiple tool calls sequentially.

        Args:
            calls: List of tool call requests.
            context: Optional context passed to all handlers.
            confirmed: Whether destructive actions are confirmed.

        Returns:
            List of ToolResult objects in the same order as calls.

        Example:
            >>> results = await executor.execute_batch(calls, context={"db": db})
        """
        results = []
        for call in calls:
            result = await self.execute(call, context, confirmed)
            results.append(result)
        return results

    async def _invoke_handler(
        self,
        handler: Any,
        parameters: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> Any:
        """Invoke a tool handler, handling both sync and async handlers.

        Args:
            handler: The handler function/method to call.
            parameters: Parameters to pass to the handler.
            context: Additional context (db session, etc.).

        Returns:
            The handler's return value.
        """
        # Merge context into parameters if the handler accepts **kwargs
        # or specific context keys
        call_kwargs = dict(parameters)
        if context:
            # Add context items that the handler might need
            sig = inspect.signature(handler)
            for key, value in context.items():
                if key in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                ):
                    call_kwargs[key] = value

        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            return await handler(**call_kwargs)
        else:
            # Run sync handler in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: handler(**call_kwargs))

    def _validate_parameters(
        self, tool: ToolDefinition, parameters: dict[str, Any]
    ) -> str | None:
        """Validate parameters against the tool's JSON schema.

        Args:
            tool: The tool definition with parameter schema.
            parameters: The parameters to validate.

        Returns:
            Error message if validation fails, None if valid.
        """
        schema = tool.parameters

        # Check required parameters
        required = schema.get("required", [])
        for param_name in required:
            if param_name not in parameters:
                return f"Missing required parameter: '{param_name}'"

        # Basic type validation for provided parameters
        properties = schema.get("properties", {})
        for param_name, value in parameters.items():
            if param_name not in properties:
                # Unknown parameter - could be strict or lenient
                continue

            param_schema = properties[param_name]
            type_error = self._validate_type(param_name, value, param_schema)
            if type_error:
                return type_error

        return None

    def _validate_type(
        self, name: str, value: Any, schema: dict[str, Any]
    ) -> str | None:
        """Validate a single parameter's type.

        Args:
            name: Parameter name (for error messages).
            value: The value to validate.
            schema: The JSON schema for this parameter.

        Returns:
            Error message if invalid, None if valid.
        """
        expected_type = schema.get("type")
        if expected_type is None:
            return None

        # Handle null values
        if value is None:
            if schema.get("nullable", False):
                return None
            return f"Parameter '{name}' cannot be null"

        # Type mapping from JSON Schema to Python
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        checker = type_checks.get(expected_type)
        if checker and not checker(value):
            return (
                f"Parameter '{name}' has wrong type: "
                f"expected {expected_type}, got {type(value).__name__}"
            )

        # Validate enum values
        if "enum" in schema and value not in schema["enum"]:
            return (
                f"Parameter '{name}' has invalid value: "
                f"expected one of {schema['enum']}, got '{value}'"
            )

        # Validate array items
        if expected_type == "array" and "items" in schema:
            items_schema = schema["items"]
            for i, item in enumerate(value):
                item_error = self._validate_type(f"{name}[{i}]", item, items_schema)
                if item_error:
                    return item_error

        return None

    def _truncate_result(self, result: Any) -> Any:
        """Truncate large results to prevent memory issues.

        Args:
            result: The result to potentially truncate.

        Returns:
            The result, possibly truncated if too large.
        """
        try:
            result_str = json.dumps(result, ensure_ascii=False)
            if len(result_str) > self.max_result_size:
                # Return truncated version with warning
                return {
                    "_truncated": True,
                    "_original_size": len(result_str),
                    "_max_size": self.max_result_size,
                    "message": "Result was truncated due to size limits",
                    "preview": result_str[:1000] + "...",
                }
        except (TypeError, ValueError):
            # Can't serialize, just return as-is
            pass

        return result

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """Get information about a tool for display purposes.

        Args:
            tool_name: Name of the tool.

        Returns:
            Dictionary with tool info, or None if not found.

        Example:
            >>> info = executor.get_tool_info("create_feed")
            >>> print(info["description"])
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "requires_confirmation": tool.requires_confirmation,
            "category": tool.category,
        }

    def list_available_tools(self) -> list[dict[str, Any]]:
        """List all available tools with their info.

        Returns:
            List of tool info dictionaries.

        Example:
            >>> tools = executor.list_available_tools()
            >>> for tool in tools:
            ...     print(f"{tool['name']}: {tool['description']}")
        """
        tools = []
        for tool_def in self.registry.list_tools():
            tools.append({
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
                "requires_confirmation": tool_def.requires_confirmation,
                "category": tool_def.category,
            })
        return tools
