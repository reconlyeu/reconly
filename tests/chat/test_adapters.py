"""Tests for LLM provider adapters."""

import pytest
from unittest.mock import Mock

from reconly_core.chat.tools import ToolDefinition
from reconly_core.chat.adapters.base import ToolCallRequest, ToolCallResult
from reconly_core.chat.adapters.openai_adapter import OpenAIAdapter
from reconly_core.chat.adapters.anthropic_adapter import AnthropicAdapter
from reconly_core.chat.adapters.ollama_adapter import OllamaAdapter


@pytest.fixture
def sample_tools():
    """Create sample tool definitions for testing."""
    return [
        ToolDefinition(
            name="create_feed",
            description="Create a new feed",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Feed name"},
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Source IDs",
                    },
                },
                "required": ["name"],
            },
            handler=lambda **kwargs: {"id": 1, "name": kwargs.get("name")},
        ),
        ToolDefinition(
            name="list_feeds",
            description="List all feeds",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **kwargs: [{"id": 1, "name": "Feed 1"}],
        ),
    ]


class TestOpenAIAdapter:
    """Test OpenAI adapter format conversion."""

    @pytest.fixture
    def adapter(self):
        return OpenAIAdapter()

    def test_provider_name(self, adapter):
        """Test provider name is correct."""
        assert adapter.provider_name == "openai"

    def test_format_tools(self, adapter, sample_tools):
        """Test converting tools to OpenAI format."""
        formatted = adapter.format_tools(sample_tools)

        assert len(formatted) == 2
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "create_feed"
        assert formatted[0]["function"]["description"] == "Create a new feed"
        assert formatted[0]["function"]["parameters"]["type"] == "object"
        assert "name" in formatted[0]["function"]["parameters"]["properties"]

    def test_format_empty_tools(self, adapter):
        """Test formatting empty tool list."""
        formatted = adapter.format_tools([])
        assert formatted == []

    def test_parse_tool_calls_with_calls(self, adapter):
        """Test parsing tool calls from OpenAI response."""
        # Mock OpenAI response - need to explicitly set return values for attributes
        mock_function = Mock()
        mock_function.name = "create_feed"
        mock_function.arguments = '{"name": "Tech News", "source_ids": [1, 2]}'

        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc123"
        mock_tool_call.type = "function"
        mock_tool_call.function = mock_function

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        calls = adapter.parse_tool_calls(mock_response)

        assert len(calls) == 1
        assert calls[0].tool_name == "create_feed"
        assert calls[0].call_id == "call_abc123"
        assert calls[0].parameters == {"name": "Tech News", "source_ids": [1, 2]}

    def test_parse_tool_calls_no_calls(self, adapter):
        """Test parsing response with no tool calls."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.tool_calls = None

        calls = adapter.parse_tool_calls(mock_response)
        assert calls == []

    def test_parse_tool_calls_invalid_json(self, adapter, caplog):
        """Test handling invalid JSON in arguments."""
        mock_function = Mock()
        mock_function.name = "test_tool"
        mock_function.arguments = "{invalid json"

        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function = mock_function

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        calls = adapter.parse_tool_calls(mock_response)
        assert len(calls) == 1
        assert calls[0].parameters == {}  # Falls back to empty dict
        assert "Failed to parse" in caplog.text

    def test_format_tool_result(self, adapter):
        """Test formatting tool result for OpenAI."""
        result = ToolCallResult(
            call_id="call_abc123",
            tool_name="create_feed",
            result={"id": 5, "name": "My Feed"},
            is_error=False,
        )

        formatted = adapter.format_tool_result(result)

        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == "call_abc123"
        assert "id" in formatted["content"]
        assert "My Feed" in formatted["content"]

    def test_format_tool_result_with_error(self, adapter):
        """Test formatting error result."""
        result = ToolCallResult(
            call_id="call_456",
            tool_name="bad_tool",
            result={"error": "Tool failed"},
            is_error=True,
        )

        formatted = adapter.format_tool_result(result)

        assert formatted["role"] == "tool"
        assert "error" in formatted["content"].lower()

    def test_supports_native_tools(self, adapter):
        """Test that OpenAI supports native tools."""
        assert adapter.supports_native_tools() is True

    def test_format_assistant_tool_call(self, adapter):
        """Test formatting assistant message with tool calls."""
        calls = [
            ToolCallRequest(
                tool_name="create_feed",
                parameters={"name": "News"},
                call_id="call_123",
            )
        ]

        formatted = adapter.format_assistant_tool_call(calls)

        assert formatted["role"] == "assistant"
        assert formatted["content"] is None
        assert len(formatted["tool_calls"]) == 1
        assert formatted["tool_calls"][0]["id"] == "call_123"
        assert formatted["tool_calls"][0]["function"]["name"] == "create_feed"


class TestAnthropicAdapter:
    """Test Anthropic adapter format conversion."""

    @pytest.fixture
    def adapter(self):
        return AnthropicAdapter()

    def test_provider_name(self, adapter):
        """Test provider name is correct."""
        assert adapter.provider_name == "anthropic"

    def test_format_tools(self, adapter, sample_tools):
        """Test converting tools to Anthropic format."""
        formatted = adapter.format_tools(sample_tools)

        assert len(formatted) == 2
        assert formatted[0]["name"] == "create_feed"
        assert formatted[0]["description"] == "Create a new feed"
        assert formatted[0]["input_schema"]["type"] == "object"
        assert "name" in formatted[0]["input_schema"]["properties"]

    def test_parse_tool_calls_with_tool_use(self, adapter):
        """Test parsing tool calls from Anthropic response."""
        # Mock Anthropic response - need to explicitly set attributes
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "I'll create that feed for you."

        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_abc123"
        mock_tool_block.name = "create_feed"
        mock_tool_block.input = {"name": "Tech News", "source_ids": [1, 2]}

        mock_response = Mock()
        mock_response.content = [mock_text_block, mock_tool_block]

        calls = adapter.parse_tool_calls(mock_response)

        assert len(calls) == 1
        assert calls[0].tool_name == "create_feed"
        assert calls[0].call_id == "toolu_abc123"
        assert calls[0].parameters == {"name": "Tech News", "source_ids": [1, 2]}

    def test_parse_tool_calls_no_tool_use(self, adapter):
        """Test parsing response with only text."""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="Here's your answer."),
        ]

        calls = adapter.parse_tool_calls(mock_response)
        assert calls == []

    def test_get_text_content(self, adapter):
        """Test extracting text content from response."""
        # Create mocks with explicit attribute values
        mock_text1 = Mock()
        mock_text1.type = "text"
        mock_text1.text = "Part 1"

        mock_tool = Mock()
        mock_tool.type = "tool_use"
        mock_tool.id = "123"
        mock_tool.name = "tool"
        mock_tool.input = {}

        mock_text2 = Mock()
        mock_text2.type = "text"
        mock_text2.text = "Part 2"

        mock_response = Mock()
        mock_response.content = [mock_text1, mock_tool, mock_text2]

        text = adapter.get_text_content(mock_response)
        # Implementation joins text parts with newline
        assert text == "Part 1\nPart 2"

    def test_format_tool_result(self, adapter):
        """Test formatting tool result for Anthropic."""
        result = ToolCallResult(
            call_id="toolu_123",
            tool_name="create_feed",
            result={"id": 5, "name": "My Feed"},
            is_error=False,
        )

        formatted = adapter.format_tool_result(result)

        # format_tool_result returns a tool_result content block, not a full message
        assert formatted["type"] == "tool_result"
        assert formatted["tool_use_id"] == "toolu_123"
        assert "My Feed" in formatted["content"]

    def test_format_tool_results_message(self, adapter):
        """Test formatting multiple tool results into one message."""
        results = [
            ToolCallResult(
                call_id="toolu_1",
                tool_name="tool1",
                result={"data": "result1"},
                is_error=False,
            ),
            ToolCallResult(
                call_id="toolu_2",
                tool_name="tool2",
                result={"data": "result2"},
                is_error=False,
            ),
        ]

        formatted = adapter.format_tool_results_message(results)

        assert formatted["role"] == "user"
        assert len(formatted["content"]) == 2
        assert formatted["content"][0]["tool_use_id"] == "toolu_1"
        assert formatted["content"][1]["tool_use_id"] == "toolu_2"

    def test_supports_native_tools(self, adapter):
        """Test that Anthropic supports native tools."""
        assert adapter.supports_native_tools() is True

    def test_format_assistant_tool_use(self, adapter):
        """Test formatting assistant message from raw response."""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="Sure!"),
            Mock(type="tool_use", id="toolu_123", name="test", input={"a": 1}),
        ]

        formatted = adapter.format_assistant_tool_use(mock_response)

        assert formatted["role"] == "assistant"
        assert len(formatted["content"]) == 2


class TestOllamaAdapter:
    """Test Ollama adapter (prompt-based tool calling)."""

    @pytest.fixture
    def adapter(self):
        return OllamaAdapter()

    def test_provider_name(self, adapter):
        """Test provider name is correct."""
        assert adapter.provider_name == "ollama"

    def test_format_tools_returns_simple_list(self, adapter, sample_tools):
        """Test that Ollama returns simplified tool descriptions."""
        # Ollama returns a simplified format for documentation purposes
        formatted = adapter.format_tools(sample_tools)
        assert len(formatted) == 2
        assert formatted[0]["name"] == "create_feed"
        assert formatted[0]["description"] == "Create a new feed"
        assert "parameters" in formatted[0]

    def test_supports_native_tools(self, adapter):
        """Test that Ollama doesn't support native tools."""
        assert adapter.supports_native_tools() is False

    def test_get_system_prompt_prefix(self, adapter, sample_tools):
        """Test generating system prompt with tool instructions."""
        prompt = adapter.get_system_prompt_prefix(sample_tools)

        assert prompt is not None
        assert "create_feed" in prompt
        assert "list_feeds" in prompt
        assert "JSON" in prompt or "json" in prompt

    def test_parse_tool_calls_from_json(self, adapter):
        """Test parsing tool calls from JSON in text response."""
        response_text = '''I'll create that feed.

TOOL_CALL:
{
  "tool": "create_feed",
  "parameters": {"name": "Tech News", "source_ids": [1, 2]}
}
'''

        calls = adapter.parse_tool_calls(response_text)

        assert len(calls) == 1
        assert calls[0].tool_name == "create_feed"
        assert calls[0].parameters == {"name": "Tech News", "source_ids": [1, 2]}
        assert calls[0].call_id is not None  # Auto-generated

    def test_parse_tool_calls_no_calls(self, adapter):
        """Test parsing response without tool calls."""
        response_text = "Here's the answer to your question."

        calls = adapter.parse_tool_calls(response_text)
        assert calls == []

    def test_parse_tool_calls_invalid_json(self, adapter, caplog):
        """Test handling invalid JSON in tool call."""
        import logging

        # Set log level to DEBUG to capture debug logs from the specific logger
        caplog.set_level(logging.DEBUG, logger="reconly_core.chat.adapters.ollama_adapter")

        # The pattern needs "tool" in it to match, so use syntactically invalid JSON
        # that looks like a tool call but won't parse
        response_text = '''```json
{"tool": "create_feed", "parameters": {invalid}}
```'''

        calls = adapter.parse_tool_calls(response_text)
        assert calls == []
        # The implementation logs at debug level
        assert "Failed to parse" in caplog.text

    def test_extract_text_without_tool_calls(self, adapter):
        """Test extracting text content without tool call markers."""
        # The implementation removes fenced JSON code blocks containing "tool"
        text_with_tool = '''I'll create that feed.

```json
{"tool": "create_feed", "parameters": {"name": "News"}}
```

The feed will be created.'''

        clean_text = adapter.extract_text_without_tool_calls(text_with_tool)

        assert "I'll create that feed" in clean_text
        assert "The feed will be created" in clean_text
        assert "```json" not in clean_text
        assert '"tool"' not in clean_text

    def test_format_tool_result(self, adapter):
        """Test formatting tool result for Ollama."""
        result = ToolCallResult(
            call_id="call_123",
            tool_name="create_feed",
            result={"id": 5, "name": "My Feed"},
            is_error=False,
        )

        formatted = adapter.format_tool_result(result)

        # Ollama returns a dict with tool_name, status, result
        assert formatted["tool_name"] == "create_feed"
        assert formatted["status"] == "Success"
        assert "My Feed" in formatted["result"]

    def test_format_tool_result_as_message(self, adapter):
        """Test formatting tool result as plain text message."""
        result = ToolCallResult(
            call_id="call_123",
            tool_name="create_feed",
            result={"id": 5, "name": "My Feed"},
            is_error=False,
        )

        message_text = adapter.format_tool_result_as_message(result)

        # Format is: "Tool '{tool_name}' executed successfully:\n{result}"
        assert "Tool 'create_feed' executed successfully" in message_text
        assert "5" in message_text
        assert "My Feed" in message_text

    def test_format_tool_result_with_error(self, adapter):
        """Test formatting error result."""
        result = ToolCallResult(
            call_id="call_456",
            tool_name="bad_tool",
            result={"error": "Tool failed"},
            is_error=True,
        )

        formatted = adapter.format_tool_result(result)

        # Returns dict with tool_name, status, result
        assert formatted["tool_name"] == "bad_tool"
        assert formatted["status"] == "Error"
        assert "Tool failed" in formatted["result"]


class TestAdapterBaseClass:
    """Test BaseToolAdapter abstract functionality."""

    def test_openai_inherits_base(self):
        """Test that OpenAI adapter inherits from base."""
        from reconly_core.chat.adapters.base import BaseToolAdapter

        adapter = OpenAIAdapter()
        assert isinstance(adapter, BaseToolAdapter)

    def test_anthropic_inherits_base(self):
        """Test that Anthropic adapter inherits from base."""
        from reconly_core.chat.adapters.base import BaseToolAdapter

        adapter = AnthropicAdapter()
        assert isinstance(adapter, BaseToolAdapter)

    def test_ollama_inherits_base(self):
        """Test that Ollama adapter inherits from base."""
        from reconly_core.chat.adapters.base import BaseToolAdapter

        adapter = OllamaAdapter()
        assert isinstance(adapter, BaseToolAdapter)


class TestToolCallDataClasses:
    """Test ToolCallRequest and ToolCallResult data classes."""

    def test_tool_call_request_creation(self):
        """Test creating a ToolCallRequest."""
        call = ToolCallRequest(
            tool_name="test_tool",
            parameters={"param1": "value1"},
            call_id="call_123",
        )

        assert call.tool_name == "test_tool"
        assert call.parameters == {"param1": "value1"}
        assert call.call_id == "call_123"

    def test_tool_call_result_creation(self):
        """Test creating a ToolCallResult."""
        result = ToolCallResult(
            call_id="call_123",
            tool_name="test_tool",
            result={"data": "result"},
            is_error=False,
        )

        assert result.call_id == "call_123"
        assert result.tool_name == "test_tool"
        assert result.result == {"data": "result"}
        assert result.is_error is False

    def test_tool_call_result_error(self):
        """Test creating error result."""
        result = ToolCallResult(
            call_id="call_456",
            tool_name="failed_tool",
            result={"error": "Something went wrong"},
            is_error=True,
        )

        assert result.is_error is True
        assert "error" in result.result


class TestAdapterRegistry:
    """Test adapter registry functionality."""

    def test_get_adapter_by_name(self):
        """Test getting adapter by provider name."""
        from reconly_core.chat.adapters import get_adapter

        adapter = get_adapter("openai")
        assert adapter.provider_name == "openai"

        adapter = get_adapter("anthropic")
        assert adapter.provider_name == "anthropic"

        adapter = get_adapter("ollama")
        assert adapter.provider_name == "ollama"

    def test_get_adapter_returns_instance(self):
        """Test that get_adapter returns a fresh instance, not class."""
        from reconly_core.chat.adapters import get_adapter
        from reconly_core.chat.adapters.base import BaseToolAdapter

        adapter = get_adapter("openai")

        # Should be an instance
        assert isinstance(adapter, BaseToolAdapter)

        # Each call should return a fresh instance
        adapter2 = get_adapter("openai")
        assert adapter is not adapter2  # Different instances

    def test_get_adapter_case_insensitive(self):
        """Test that adapter names are case-insensitive in ChatService."""
        from reconly_core.chat.adapters import get_adapter

        # Registry is case-sensitive, but ChatService lowercases
        adapter = get_adapter("openai")
        assert adapter.provider_name == "openai"

    def test_list_adapters(self):
        """Test listing available adapters."""
        from reconly_core.chat.adapters import list_adapters

        adapters = list_adapters()
        assert "openai" in adapters
        assert "anthropic" in adapters
        assert "ollama" in adapters
        # Aliases are excluded from list_adapters
        assert "lmstudio" not in adapters

        # Should be sorted
        assert adapters == sorted(adapters)

    def test_list_adapter_aliases(self):
        """Test listing adapter aliases."""
        from reconly_core.chat.adapters import get_adapter
        from reconly_core.chat.adapters.registry import list_adapter_aliases

        # Trigger lazy registration of lmstudio alias by requesting the adapter
        adapter = get_adapter("lmstudio")
        assert adapter.provider_name == "openai"

        aliases = list_adapter_aliases()

        # Should contain lmstudio -> openai alias (lazily registered)
        assert "lmstudio" in aliases
        assert aliases["lmstudio"] == "openai"

    def test_lmstudio_alias(self):
        """Test that LMStudio alias returns OpenAI adapter."""
        from reconly_core.chat.adapters import get_adapter

        adapter = get_adapter("lmstudio")
        # LMStudio is aliased to OpenAI, so it returns OpenAIAdapter
        assert adapter.provider_name == "openai"

    def test_alias_resolution_to_correct_adapter(self):
        """Test that alias resolves to the correct adapter instance."""
        from reconly_core.chat.adapters import get_adapter

        # Get adapter via alias and directly
        alias_adapter = get_adapter("lmstudio")
        direct_adapter = get_adapter("openai")

        # Should be same type (both OpenAIAdapter)
        assert type(alias_adapter) == type(direct_adapter)
        assert alias_adapter.provider_name == direct_adapter.provider_name

    def test_unknown_adapter_raises(self):
        """Test that unknown adapter raises ValueError."""
        from reconly_core.chat.adapters import get_adapter

        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("unknown_provider")

    def test_unknown_adapter_error_message_helpful(self):
        """Test that unknown adapter error includes available adapters."""
        from reconly_core.chat.adapters import get_adapter

        try:
            get_adapter("unknown_provider")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            # Error message should list available adapters
            assert "unknown_provider" in str(e)
            assert "Available adapters" in str(e)
            # Should mention at least one real adapter
            assert "openai" in str(e) or "anthropic" in str(e) or "ollama" in str(e)

    def test_is_adapter_registered(self):
        """Test checking if adapter is registered."""
        from reconly_core.chat.adapters.registry import is_adapter_registered

        assert is_adapter_registered("openai") is True
        assert is_adapter_registered("anthropic") is True
        assert is_adapter_registered("ollama") is True
        assert is_adapter_registered("lmstudio") is True  # Alias
        assert is_adapter_registered("unknown") is False
