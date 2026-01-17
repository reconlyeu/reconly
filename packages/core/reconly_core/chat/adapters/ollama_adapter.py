"""Ollama adapter for tool calling via prompt engineering.

Ollama models may not have native tool calling support, so this adapter uses
prompt-based instructions to enable tool calling behavior. The model is
instructed to output JSON in a specific format when it needs to use a tool.

Ollama Prompt-Based Format:
    System prompt includes tool descriptions and instructions to output:
    ```json
    {"tool": "create_feed", "parameters": {"name": "Tech News"}}
    ```

    The adapter parses this JSON from the model's text response.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from reconly_core.chat.tools import ToolDefinition
from reconly_core.chat.adapters.base import (
    BaseToolAdapter,
    ToolCallRequest,
    ToolCallResult,
)

logger = logging.getLogger(__name__)


# Pattern to find JSON tool calls in model output
# Matches ```json {...} ``` or just {...} with tool/parameters keys
TOOL_CALL_PATTERN = re.compile(
    r'```(?:json)?\s*(\{[^`]*?"tool"\s*:[^`]*?\})\s*```'  # Fenced code block
    r'|'
    r'(\{[^{}]*?"tool"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^{}]*\}\s*\})',  # Inline JSON
    re.DOTALL
)

# Simpler fallback pattern for basic JSON detection
SIMPLE_JSON_PATTERN = re.compile(
    r'\{[^{}]*"tool"[^{}]*\}',
    re.DOTALL
)


class OllamaAdapter(BaseToolAdapter):
    """Adapter for Ollama using prompt-based tool calling.

    Since Ollama models may not have native tool support, this adapter:
    1. Injects tool descriptions and usage instructions into the system prompt
    2. Parses JSON tool calls from the model's text output
    3. Formats tool results as context for the next turn

    Example:
        >>> adapter = OllamaAdapter()
        >>> tools = tool_registry.list_tools()
        >>>
        >>> # Get system prompt with tool instructions
        >>> system_prefix = adapter.get_system_prompt_prefix(tools)
        >>>
        >>> # Send to Ollama and parse response
        >>> response_text = "I'll create that for you: ```json{...}```"
        >>> calls = adapter.parse_tool_calls(response_text)
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "ollama"

    def supports_native_tools(self) -> bool:
        """Ollama uses prompt-based tools, not native API support."""
        return False

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Convert tool definitions to a simple format for documentation.

        For Ollama, tools are communicated via system prompt rather than
        a tools array. This method returns a simple list for reference.

        Args:
            tools: List of ToolDefinition objects.

        Returns:
            List of simplified tool descriptions.
        """
        formatted_tools = []

        for tool in tools:
            formatted_tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })

        return formatted_tools

    def get_system_prompt_prefix(self, tools: list[ToolDefinition]) -> str:
        """Generate system prompt instructions for tool calling.

        This creates detailed instructions that teach the model how to
        use tools by outputting structured JSON.

        Args:
            tools: List of available tools.

        Returns:
            System prompt text to prepend to the base system prompt.

        Example:
            >>> prefix = adapter.get_system_prompt_prefix(tools)
            >>> full_system = prefix + "\\n\\n" + base_system_prompt
        """
        if not tools:
            return ""

        tool_descriptions = []
        for i, tool in enumerate(tools, 1):
            params_desc = self._format_parameters_description(tool.parameters)
            tool_descriptions.append(
                f"{i}. **{tool.name}**: {tool.description}\n{params_desc}"
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

    def _format_parameters_description(self, parameters: dict[str, Any]) -> str:
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

    def parse_tool_calls(self, response: Any) -> list[ToolCallRequest]:
        """Parse tool calls from Ollama's text response.

        Looks for JSON tool calls in the model's output, either in
        fenced code blocks or inline.

        Args:
            response: The text response from Ollama, or a dict with 'response' key.

        Returns:
            List of ToolCallRequest objects (empty if no tool calls found).

        Example:
            >>> text = '''I'll help with that.
            ... ```json
            ... {"tool": "list_feeds", "parameters": {}}
            ... ```'''
            >>> calls = adapter.parse_tool_calls(text)
            >>> print(calls[0].tool_name)  # "list_feeds"
        """
        # Extract text from various response formats
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            text = response.get("response", "") or response.get("content", "")
        elif hasattr(response, "response"):
            text = response.response
        elif hasattr(response, "content"):
            text = response.content
        else:
            logger.warning(f"Unknown response type for Ollama: {type(response)}")
            return []

        if not text:
            return []

        tool_calls = []

        # Try the main pattern first (handles code blocks and structured JSON)
        matches = TOOL_CALL_PATTERN.findall(text)
        for match in matches:
            # match is a tuple from the alternation groups
            json_str = match[0] or match[1]
            if json_str:
                call = self._parse_json_tool_call(json_str.strip())
                if call:
                    tool_calls.append(call)

        # If no matches, try the simpler pattern as fallback
        if not tool_calls:
            simple_matches = SIMPLE_JSON_PATTERN.findall(text)
            for json_str in simple_matches:
                call = self._parse_json_tool_call(json_str.strip())
                if call:
                    tool_calls.append(call)
                    break  # Only take the first valid match with simple pattern

        return tool_calls

    def _parse_json_tool_call(self, json_str: str) -> ToolCallRequest | None:
        """Parse a single JSON string as a tool call.

        Args:
            json_str: JSON string potentially containing a tool call.

        Returns:
            ToolCallRequest if valid, None otherwise.
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

            # Generate a unique call ID since Ollama doesn't provide one
            call_id = f"ollama_{uuid.uuid4().hex[:12]}"

            return ToolCallRequest(
                tool_name=tool_name,
                parameters=parameters,
                call_id=call_id,
                raw_response=json_str,
            )

        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse potential tool call JSON: {e}")
            return None

    def format_tool_result(self, result: ToolCallResult) -> dict[str, Any]:
        """Format a tool result for Ollama.

        For Ollama, tool results are formatted as context text since there's
        no native tool result format.

        Args:
            result: The ToolCallResult to format.

        Returns:
            Dictionary with formatted result text.

        Example:
            >>> result = ToolCallResult(
            ...     call_id="ollama_abc123",
            ...     tool_name="create_feed",
            ...     result={"id": 5, "name": "My Feed"}
            ... )
            >>> formatted = adapter.format_tool_result(result)
        """
        # Serialize result
        if isinstance(result.result, str):
            result_text = result.result
        else:
            try:
                result_text = json.dumps(result.result, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                result_text = str(result.result)

        status = "Error" if result.is_error else "Success"

        return {
            "tool_name": result.tool_name,
            "status": status,
            "result": result_text,
        }

    def format_tool_result_as_message(self, result: ToolCallResult) -> str:
        """Format a tool result as a text message for the conversation.

        Since Ollama doesn't have structured tool result handling, we format
        results as clear text that the model can understand.

        Args:
            result: The ToolCallResult to format.

        Returns:
            Text message describing the tool result.

        Example:
            >>> text = adapter.format_tool_result_as_message(result)
            >>> # "Tool 'create_feed' executed successfully:\n{...}"
        """
        formatted = self.format_tool_result(result)

        if result.is_error:
            return (
                f"Tool '{formatted['tool_name']}' failed with error:\n"
                f"{formatted['result']}"
            )
        else:
            return (
                f"Tool '{formatted['tool_name']}' executed successfully:\n"
                f"{formatted['result']}"
            )

    def has_tool_call(self, response: Any) -> bool:
        """Check if a response contains a tool call without fully parsing it.

        Useful for quick checks before doing full parsing.

        Args:
            response: The response to check.

        Returns:
            True if the response likely contains a tool call.
        """
        # Extract text
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            text = response.get("response", "") or response.get("content", "")
        elif hasattr(response, "response"):
            text = response.response
        else:
            return False

        # Quick pattern check
        return '"tool"' in text and '"parameters"' in text

    def extract_text_without_tool_calls(self, response: Any) -> str:
        """Extract the natural language text, removing tool call JSON.

        Args:
            response: The response to process.

        Returns:
            Text with tool call JSON blocks removed.

        Example:
            >>> text = '''I'll create that feed.
            ... ```json
            ... {"tool": "create_feed", "parameters": {}}
            ... ```'''
            >>> clean = adapter.extract_text_without_tool_calls(text)
            >>> print(clean)  # "I'll create that feed."
        """
        # Extract text
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            text = response.get("response", "") or response.get("content", "")
        elif hasattr(response, "response"):
            text = response.response
        else:
            return ""

        # Remove fenced code blocks containing tool calls
        text = re.sub(
            r'```(?:json)?\s*\{[^`]*?"tool"\s*:[^`]*?\}\s*```',
            '',
            text,
            flags=re.DOTALL
        )

        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
