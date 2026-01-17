"""Tests for tool registry and definitions."""

import pytest

from reconly_core.chat.tools import ToolDefinition, ToolRegistry, tool_registry


class TestToolDefinition:
    """Test tool definition validation and creation."""

    def test_create_valid_tool(self):
        """Test creating a valid tool definition."""
        def handler(param1: str) -> str:
            return f"Result: {param1}"

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "Test parameter"}
                },
                "required": ["param1"],
            },
            handler=handler,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert callable(tool.handler)
        assert tool.requires_confirmation is False
        assert tool.category is None

    def test_validation_empty_name_raises(self):
        """Test that empty tool name raises ValueError."""
        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            ToolDefinition(
                name="",
                description="Test",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: None,
            )

    def test_validation_empty_description_raises(self):
        """Test that empty description raises ValueError."""
        with pytest.raises(ValueError, match="Tool description cannot be empty"):
            ToolDefinition(
                name="test",
                description="",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: None,
            )

    def test_validation_invalid_parameters_type(self):
        """Test that non-dict parameters raise ValueError."""
        with pytest.raises(ValueError, match="Parameters must be a dict"):
            ToolDefinition(
                name="test",
                description="Test",
                parameters="invalid",  # type: ignore
                handler=lambda: None,
            )

    def test_validation_parameters_missing_type(self):
        """Test that parameters without 'type: object' raise ValueError."""
        with pytest.raises(ValueError, match="Parameters schema must have type: 'object'"):
            ToolDefinition(
                name="test",
                description="Test",
                parameters={"properties": {}},  # Missing type
                handler=lambda: None,
            )

    def test_validation_non_callable_handler(self):
        """Test that non-callable handler raises ValueError."""
        with pytest.raises(ValueError, match="Handler must be callable"):
            ToolDefinition(
                name="test",
                description="Test",
                parameters={"type": "object", "properties": {}, "required": []},
                handler="not_callable",  # type: ignore
            )

    def test_tool_with_category_and_examples(self):
        """Test creating a tool with category and examples."""
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            category="testing",
            examples=[{"input": "test"}],
        )

        assert tool.category == "testing"
        assert len(tool.examples) == 1

    def test_requires_confirmation_flag(self):
        """Test requires_confirmation flag."""
        tool = ToolDefinition(
            name="dangerous_tool",
            description="A dangerous operation",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            requires_confirmation=True,
        )

        assert tool.requires_confirmation is True


class TestToolRegistry:
    """Test tool registry operations."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return ToolRegistry()

    @pytest.fixture
    def sample_tool(self):
        """Create a sample tool definition."""
        return ToolDefinition(
            name="sample_tool",
            description="A sample tool",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: "sample result",
        )

    def test_register_tool_directly(self, registry, sample_tool):
        """Test registering a tool directly."""
        registry.register_tool(sample_tool)

        assert registry.is_registered("sample_tool")
        assert len(registry) == 1
        assert "sample_tool" in registry

    def test_register_via_decorator(self, registry):
        """Test registering a tool via decorator."""
        @registry.register
        def my_tool_factory():
            return ToolDefinition(
                name="decorated_tool",
                description="Tool from decorator",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: "result",
            )

        assert registry.is_registered("decorated_tool")
        tool = registry.get("decorated_tool")
        assert tool is not None
        assert tool.name == "decorated_tool"

    def test_register_duplicate_tool_warns(self, registry, sample_tool, caplog):
        """Test that registering duplicate tool logs a warning."""
        registry.register_tool(sample_tool)
        registry.register_tool(sample_tool)  # Duplicate

        assert "already registered" in caplog.text.lower()
        assert len(registry) == 1  # Still only one tool

    def test_get_existing_tool(self, registry, sample_tool):
        """Test getting an existing tool."""
        registry.register_tool(sample_tool)

        tool = registry.get("sample_tool")
        assert tool is not None
        assert tool.name == "sample_tool"

    def test_get_nonexistent_tool_returns_none(self, registry):
        """Test getting a nonexistent tool returns None."""
        tool = registry.get("nonexistent")
        assert tool is None

    def test_get_required_existing_tool(self, registry, sample_tool):
        """Test get_required for existing tool."""
        registry.register_tool(sample_tool)

        tool = registry.get_required("sample_tool")
        assert tool.name == "sample_tool"

    def test_get_required_nonexistent_raises(self, registry):
        """Test get_required raises KeyError for nonexistent tool."""
        with pytest.raises(KeyError, match="Tool 'nonexistent' is not registered"):
            registry.get_required("nonexistent")

    def test_list_tools(self, registry):
        """Test listing all tools."""
        tool1 = ToolDefinition(
            name="tool1",
            description="First",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="Second",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)

        tools = registry.list_tools()
        assert len(tools) == 2
        assert any(t.name == "tool1" for t in tools)
        assert any(t.name == "tool2" for t in tools)

    def test_list_tool_names(self, registry):
        """Test listing tool names."""
        tool1 = ToolDefinition(
            name="alpha",
            description="A",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )
        tool2 = ToolDefinition(
            name="beta",
            description="B",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)

        names = registry.list_tool_names()
        assert len(names) == 2
        assert "alpha" in names
        assert "beta" in names

    def test_get_by_category(self, registry):
        """Test filtering tools by category."""
        tool1 = ToolDefinition(
            name="feed_tool",
            description="Feed",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            category="feeds",
        )
        tool2 = ToolDefinition(
            name="source_tool",
            description="Source",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            category="sources",
        )
        tool3 = ToolDefinition(
            name="another_feed_tool",
            description="Another feed",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            category="feeds",
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)
        registry.register_tool(tool3)

        feed_tools = registry.get_by_category("feeds")
        assert len(feed_tools) == 2
        assert all(t.category == "feeds" for t in feed_tools)

    def test_get_safe_tools(self, registry):
        """Test getting safe (non-destructive) tools."""
        safe_tool = ToolDefinition(
            name="safe",
            description="Safe",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            requires_confirmation=False,
        )
        dangerous_tool = ToolDefinition(
            name="dangerous",
            description="Dangerous",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            requires_confirmation=True,
        )

        registry.register_tool(safe_tool)
        registry.register_tool(dangerous_tool)

        safe_tools = registry.get_safe_tools()
        assert len(safe_tools) == 1
        assert safe_tools[0].name == "safe"

    def test_get_destructive_tools(self, registry):
        """Test getting destructive tools."""
        safe_tool = ToolDefinition(
            name="safe",
            description="Safe",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            requires_confirmation=False,
        )
        dangerous_tool = ToolDefinition(
            name="dangerous",
            description="Dangerous",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
            requires_confirmation=True,
        )

        registry.register_tool(safe_tool)
        registry.register_tool(dangerous_tool)

        destructive = registry.get_destructive_tools()
        assert len(destructive) == 1
        assert destructive[0].name == "dangerous"

    def test_clear_registry(self, registry, sample_tool):
        """Test clearing all tools from registry."""
        registry.register_tool(sample_tool)
        assert len(registry) == 1

        registry.clear()
        assert len(registry) == 0
        assert not registry.is_registered("sample_tool")

    def test_registry_len(self, registry):
        """Test __len__ method."""
        assert len(registry) == 0

        registry.register_tool(
            ToolDefinition(
                name="tool1",
                description="T1",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: None,
            )
        )
        assert len(registry) == 1

    def test_registry_contains(self, registry, sample_tool):
        """Test __contains__ method."""
        assert "sample_tool" not in registry

        registry.register_tool(sample_tool)
        assert "sample_tool" in registry

    def test_registry_iter(self, registry):
        """Test __iter__ method returns tool names."""
        tool1 = ToolDefinition(
            name="tool1",
            description="T1",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="T2",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: None,
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)

        names = list(registry)
        assert "tool1" in names
        assert "tool2" in names

    def test_register_invalid_type_raises(self, registry):
        """Test that registering non-ToolDefinition raises TypeError."""
        with pytest.raises(TypeError, match="Expected ToolDefinition"):
            registry.register_tool("not a tool")  # type: ignore

    def test_decorator_returns_factory(self, registry):
        """Test that decorator returns the original factory function."""
        def factory():
            return ToolDefinition(
                name="test",
                description="Test",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=lambda: None,
            )

        decorated = registry.register(factory)
        assert decorated is factory

    def test_decorator_with_non_tooldef_raises(self, registry):
        """Test that decorator raises if factory doesn't return ToolDefinition."""
        with pytest.raises(TypeError, match="must return a ToolDefinition"):
            @registry.register
            def bad_factory():
                return "not a ToolDefinition"


class TestGlobalRegistry:
    """Test the global tool_registry instance."""

    def test_global_registry_exists(self):
        """Test that the global tool_registry exists."""
        assert tool_registry is not None
        assert isinstance(tool_registry, ToolRegistry)

    def test_global_registry_has_tools(self):
        """Test that global registry has tools from tools_impl module."""
        # Import tools_impl to ensure tools are registered
        import reconly_core.chat.tools_impl  # noqa: F401

        # Should have various tools registered
        assert len(tool_registry) > 0

        # Check for some expected tools
        assert tool_registry.is_registered("list_feeds")
        assert tool_registry.is_registered("create_feed")
        assert tool_registry.is_registered("search_digests")

    def test_global_registry_tools_valid(self):
        """Test that all tools in global registry are valid."""
        import reconly_core.chat.tools_impl  # noqa: F401

        for tool in tool_registry.list_tools():
            assert isinstance(tool, ToolDefinition)
            assert tool.name
            assert tool.description
            assert callable(tool.handler)
            assert isinstance(tool.parameters, dict)
            assert tool.parameters.get("type") == "object"
