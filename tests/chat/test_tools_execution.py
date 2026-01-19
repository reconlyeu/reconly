"""Integration tests for tool execution in the chat system.

This module tests the ToolExecutor class and verifies that all tools can be
executed with valid parameters, handle errors correctly, and integrate properly
with the database.

Tests cover:
- ToolExecutor class functionality (execute, validation, error handling)
- Integration tests for major tools (feeds, sources, digests, analytics)
- Error handling (invalid tool names, missing parameters, database errors)
- Tool confirmation requirements and parameter validation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from reconly_core.chat.executor import ToolExecutor, ToolResult, ToolExecutionError
from reconly_core.chat.tools import ToolRegistry, ToolDefinition, tool_registry
from reconly_core.chat.adapters.base import ToolCallRequest
from reconly_core.database.models import (
    Feed, Source, Digest, Tag, FeedSource, FeedRun,
    PromptTemplate, DigestTag
)


# =============================================================================
# ToolExecutor Unit Tests
# =============================================================================


class TestToolExecutor:
    """Test the ToolExecutor class with mock tools."""

    @pytest.fixture
    def test_registry(self):
        """Create a test registry with sample tools."""
        registry = ToolRegistry()

        # Simple sync tool
        registry.register_tool(
            ToolDefinition(
                name="echo",
                description="Echo back the input",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to echo"}
                    },
                    "required": ["message"],
                },
                handler=lambda message, **kwargs: {"echo": message},
            )
        )

        # Async tool
        async def async_handler(value, **kwargs):
            return {"doubled": value * 2}

        registry.register_tool(
            ToolDefinition(
                name="double",
                description="Double a number",
                parameters={
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer", "description": "Number to double"}
                    },
                    "required": ["value"],
                },
                handler=async_handler,
            )
        )

        # Tool requiring confirmation
        registry.register_tool(
            ToolDefinition(
                name="delete_everything",
                description="Delete all data (dangerous)",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=lambda **kwargs: {"deleted": True},
                requires_confirmation=True,
            )
        )

        return registry

    @pytest.fixture
    def executor(self, test_registry):
        """Create a ToolExecutor with test registry."""
        return ToolExecutor(test_registry)

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self, executor):
        """Test executing a synchronous tool."""
        call = ToolCallRequest(
            tool_name="echo",
            parameters={"message": "Hello"},
            call_id="call_1",
        )

        result = await executor.execute(call)

        assert result.success is True
        assert result.result == {"echo": "Hello"}
        assert result.tool_name == "echo"
        assert result.call_id == "call_1"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_async_tool(self, executor):
        """Test executing an asynchronous tool."""
        call = ToolCallRequest(
            tool_name="double",
            parameters={"value": 21},
            call_id="call_2",
        )

        result = await executor.execute(call)

        assert result.success is True
        assert result.result == {"doubled": 42}
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_invalid_tool(self, executor):
        """Test executing a tool that doesn't exist."""
        call = ToolCallRequest(
            tool_name="nonexistent",
            parameters={},
            call_id="call_3",
        )

        result = await executor.execute(call)

        assert result.success is False
        assert "Unknown tool" in result.error
        assert "nonexistent" in result.error

    @pytest.mark.asyncio
    async def test_execute_missing_required_parameter(self, executor):
        """Test executing tool without required parameter."""
        call = ToolCallRequest(
            tool_name="echo",
            parameters={},  # Missing 'message'
            call_id="call_4",
        )

        result = await executor.execute(call)

        assert result.success is False
        assert "Missing required parameter" in result.error
        assert "message" in result.error

    @pytest.mark.asyncio
    async def test_execute_wrong_parameter_type(self, executor):
        """Test executing tool with wrong parameter type."""
        call = ToolCallRequest(
            tool_name="double",
            parameters={"value": "not a number"},  # Should be integer
            call_id="call_5",
        )

        result = await executor.execute(call)

        assert result.success is False
        assert "wrong type" in result.error.lower()

    @pytest.mark.asyncio
    async def test_confirmation_required_not_confirmed(self, executor):
        """Test that confirmation-required tools are blocked without confirmation."""
        call = ToolCallRequest(
            tool_name="delete_everything",
            parameters={},
            call_id="call_6",
        )

        result = await executor.execute(call, confirmed=False)

        assert result.success is False
        assert "requires user confirmation" in result.error
        assert result.requires_confirmation is True
        assert result.confirmed is False

    @pytest.mark.asyncio
    async def test_confirmation_required_confirmed(self, executor):
        """Test that confirmation-required tools execute when confirmed."""
        call = ToolCallRequest(
            tool_name="delete_everything",
            parameters={},
            call_id="call_7",
        )

        result = await executor.execute(call, confirmed=True)

        assert result.success is True
        assert result.result == {"deleted": True}
        assert result.confirmed is True

    @pytest.mark.asyncio
    async def test_execute_with_context(self, test_registry):
        """Test executing tool with context injection."""
        # Create tool that uses context
        def handler_with_context(message, db=None, **kwargs):
            return {"message": message, "has_db": db is not None}

        test_registry.register_tool(
            ToolDefinition(
                name="context_tool",
                description="Tool that uses context",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"}
                    },
                    "required": ["message"],
                },
                handler=handler_with_context,
            )
        )

        executor = ToolExecutor(test_registry)
        call = ToolCallRequest(
            tool_name="context_tool",
            parameters={"message": "test"},
            call_id="call_8",
        )

        # Execute with context
        mock_db = Mock()
        result = await executor.execute(call, context={"db": mock_db})

        assert result.success is True
        assert result.result["has_db"] is True

    @pytest.mark.asyncio
    async def test_execute_tool_raises_exception(self, test_registry):
        """Test that exceptions in tool handlers are caught."""
        def failing_handler(**kwargs):
            raise ValueError("Something went wrong")

        test_registry.register_tool(
            ToolDefinition(
                name="failing_tool",
                description="A tool that fails",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=failing_handler,
            )
        )

        executor = ToolExecutor(test_registry)
        call = ToolCallRequest(
            tool_name="failing_tool",
            parameters={},
            call_id="call_9",
        )

        result = await executor.execute(call)

        assert result.success is False
        assert "ValueError" in result.error
        assert "Something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_execute_batch(self, executor):
        """Test executing multiple tools in batch."""
        calls = [
            ToolCallRequest(
                tool_name="echo",
                parameters={"message": "First"},
                call_id="call_1",
            ),
            ToolCallRequest(
                tool_name="double",
                parameters={"value": 10},
                call_id="call_2",
            ),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].result == {"echo": "First"}
        assert results[1].success is True
        assert results[1].result == {"doubled": 20}

    def test_get_tool_info(self, executor):
        """Test getting tool information."""
        info = executor.get_tool_info("echo")

        assert info is not None
        assert info["name"] == "echo"
        assert info["description"] == "Echo back the input"
        assert "message" in info["parameters"]["properties"]

    def test_get_tool_info_nonexistent(self, executor):
        """Test getting info for nonexistent tool."""
        info = executor.get_tool_info("nonexistent")
        assert info is None

    def test_list_available_tools(self, executor):
        """Test listing all available tools."""
        tools = executor.list_available_tools()

        assert len(tools) == 3  # echo, double, delete_everything
        tool_names = {t["name"] for t in tools}
        assert "echo" in tool_names
        assert "double" in tool_names
        assert "delete_everything" in tool_names


# =============================================================================
# Tool Integration Tests
# =============================================================================


class TestFeedToolsIntegration:
    """Integration tests for feed-related tools."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        # Import to ensure tools are registered
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_list_feeds_empty(self, executor, db_session):
        """Test listing feeds when none exist."""
        call = ToolCallRequest(
            tool_name="list_feeds",
            parameters={},
            call_id="call_1",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result == []

    @pytest.mark.asyncio
    async def test_list_feeds_with_data(self, executor, db_session, sample_feed):
        """Test listing feeds with existing data."""
        call = ToolCallRequest(
            tool_name="list_feeds",
            parameters={"limit": 10},
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["name"] == "Test Feed"
        assert result.result[0]["id"] == sample_feed.id

    @pytest.mark.asyncio
    async def test_list_feeds_enabled_only(self, executor, db_session):
        """Test filtering feeds by enabled status."""
        # Create enabled and disabled feeds
        enabled_feed = Feed(
            name="Enabled Feed",
            schedule_enabled=True,
            schedule_cron="0 9 * * *",
        )
        disabled_feed = Feed(
            name="Disabled Feed",
            schedule_enabled=False,
        )
        db_session.add_all([enabled_feed, disabled_feed])
        db_session.commit()

        call = ToolCallRequest(
            tool_name="list_feeds",
            parameters={"enabled_only": True},
            call_id="call_3",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["name"] == "Enabled Feed"

    @pytest.mark.asyncio
    async def test_create_feed_basic(self, executor, db_session):
        """Test creating a basic feed."""
        call = ToolCallRequest(
            tool_name="create_feed",
            parameters={
                "name": "Tech News",
                "description": "Latest technology news",
                "digest_mode": "individual",
            },
            call_id="call_4",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["name"] == "Tech News"
        assert result.result["id"] is not None

        # Verify in database
        feed = db_session.query(Feed).filter_by(name="Tech News").first()
        assert feed is not None
        assert feed.description == "Latest technology news"

    @pytest.mark.asyncio
    async def test_create_feed_with_sources(self, executor, db_session, sample_source):
        """Test creating a feed with existing sources."""
        call = ToolCallRequest(
            tool_name="create_feed",
            parameters={
                "name": "News Feed",
                "source_ids": [sample_source.id],
                "schedule_cron": "0 8 * * *",
                "schedule_enabled": True,
            },
            call_id="call_5",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["source_count"] == 1

        # Verify feed sources
        feed_id = result.result["id"]
        feed_sources = db_session.query(FeedSource).filter_by(feed_id=feed_id).all()
        assert len(feed_sources) == 1
        assert feed_sources[0].source_id == sample_source.id

    @pytest.mark.asyncio
    async def test_create_feed_with_inline_sources(self, executor, db_session):
        """Test creating a feed with inline source definitions (bundle format)."""
        call = ToolCallRequest(
            tool_name="create_feed",
            parameters={
                "name": "Bundle Feed",
                "sources": [
                    {
                        "name": "TechCrunch",
                        "type": "rss",
                        "url": "https://techcrunch.com/feed/",
                    },
                    {
                        "name": "Hacker News",
                        "type": "rss",
                        "url": "https://news.ycombinator.com/rss",
                    },
                ],
            },
            call_id="call_6",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["sources_created"] == 2
        assert result.result["source_count"] == 2

    @pytest.mark.asyncio
    async def test_create_feed_invalid_digest_mode(self, executor, db_session):
        """Test creating feed with invalid digest_mode fails due to enum validation."""
        call = ToolCallRequest(
            tool_name="create_feed",
            parameters={
                "name": "Invalid Feed",
                "digest_mode": "invalid_mode",  # Not in enum ["individual", "per_source", "all_sources"]
            },
            call_id="call_7",
        )

        result = await executor.execute(call, context={"db": db_session})

        # Should fail at parameter validation (enum check) or runtime validation
        assert result.success is False
        assert "invalid" in result.error.lower() or "digest_mode" in result.error.lower()


class TestSourceToolsIntegration:
    """Integration tests for source-related tools."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_list_sources_empty(self, executor, db_session):
        """Test listing sources when none exist."""
        call = ToolCallRequest(
            tool_name="list_sources",
            parameters={},
            call_id="call_1",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result == []

    @pytest.mark.asyncio
    async def test_list_sources_with_data(self, executor, db_session, sample_source):
        """Test listing sources with existing data."""
        call = ToolCallRequest(
            tool_name="list_sources",
            parameters={"limit": 50},
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["name"] == "Test RSS Feed"
        assert result.result[0]["type"] == "rss"

    @pytest.mark.asyncio
    async def test_list_sources_filter_by_type(self, executor, db_session):
        """Test filtering sources by type."""
        # Create multiple source types
        rss_source = Source(name="RSS", type="rss", url="https://example.com/rss", enabled=True)
        youtube_source = Source(name="YouTube", type="youtube", url="https://youtube.com/@test", enabled=True)
        db_session.add_all([rss_source, youtube_source])
        db_session.commit()

        call = ToolCallRequest(
            tool_name="list_sources",
            parameters={"source_type": "rss"},
            call_id="call_3",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["type"] == "rss"

    @pytest.mark.asyncio
    async def test_create_source_basic(self, executor, db_session):
        """Test creating a basic source."""
        call = ToolCallRequest(
            tool_name="create_source",
            parameters={
                "name": "TechCrunch",
                "url": "https://techcrunch.com/feed/",
                "source_type": "rss",
            },
            call_id="call_4",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["name"] == "TechCrunch"
        assert result.result["url"] == "https://techcrunch.com/feed/"
        assert result.result["id"] is not None

        # Verify in database
        source = db_session.query(Source).filter_by(name="TechCrunch").first()
        assert source is not None
        assert source.enabled is True

    @pytest.mark.asyncio
    async def test_create_source_with_config(self, executor, db_session):
        """Test creating a source with custom config."""
        call = ToolCallRequest(
            tool_name="create_source",
            parameters={
                "name": "My Blog",
                "url": "https://myblog.com/rss",
                "source_type": "blog",
                "config": {"max_items": 20, "fetch_full_content": True},
            },
            call_id="call_5",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True

        # Verify config in database
        source = db_session.query(Source).filter_by(name="My Blog").first()
        assert source.config["max_items"] == 20
        assert source.config["fetch_full_content"] is True

    @pytest.mark.asyncio
    async def test_create_source_invalid_type(self, executor, db_session):
        """Test creating source with invalid type fails due to enum validation."""
        call = ToolCallRequest(
            tool_name="create_source",
            parameters={
                "name": "Invalid Source",
                "url": "https://example.com/feed",
                "source_type": "invalid_type",  # Not in enum ["rss", "youtube", "website", "blog", "imap", "agent"]
            },
            call_id="call_6",
        )

        result = await executor.execute(call, context={"db": db_session})

        # Should fail at parameter validation (enum check) or runtime validation
        assert result.success is False
        assert "invalid" in result.error.lower() or "source_type" in result.error.lower()


class TestDigestToolsIntegration:
    """Integration tests for digest-related tools."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_search_digests_empty(self, executor, db_session):
        """Test searching digests when none exist."""
        call = ToolCallRequest(
            tool_name="search_digests",
            parameters={"query": "test"},
            call_id="call_1",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["total"] == 0
        assert result.result["digests"] == []

    @pytest.mark.asyncio
    async def test_search_digests_by_query(self, executor, db_session, digest_factory):
        """Test full-text search in digests."""
        # Create test digests
        digest_factory(title="Python Tutorial", summary="Learn Python programming")
        digest_factory(title="JavaScript Guide", summary="Modern JavaScript features")
        digest_factory(title="Python Advanced", summary="Advanced Python concepts")

        call = ToolCallRequest(
            tool_name="search_digests",
            parameters={"query": "Python"},
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["total"] >= 2  # Should find both Python digests
        assert any("Python" in d["title"] for d in result.result["digests"])

    @pytest.mark.asyncio
    async def test_search_digests_by_tags(self, executor, db_session, digest_factory):
        """Test filtering digests by tags."""
        # Create digests with tags
        digest_factory(title="AI Article", with_tags=["ai", "ml"])
        digest_factory(title="Python Article", with_tags=["python", "programming"])

        call = ToolCallRequest(
            tool_name="search_digests",
            parameters={"tags": ["ai"]},
            call_id="call_3",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["total"] >= 1
        assert any("ai" in d["tags"] for d in result.result["digests"])

    @pytest.mark.asyncio
    async def test_search_digests_limit(self, executor, db_session, digest_factory):
        """Test search limit parameter."""
        # Create 10 digests
        for i in range(10):
            digest_factory(title=f"Article {i}")

        call = ToolCallRequest(
            tool_name="search_digests",
            parameters={"limit": 5},
            call_id="call_4",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result["digests"]) <= 5

    @pytest.mark.asyncio
    async def test_export_digests_json(self, executor, db_session, digest_factory):
        """Test exporting digests to JSON."""
        digest_factory(title="Export Test 1")
        digest_factory(title="Export Test 2")

        call = ToolCallRequest(
            tool_name="export_digests",
            parameters={"format": "json", "limit": 100},
            call_id="call_5",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["format"] == "json"
        assert result.result["digest_count"] >= 2
        assert "content_preview" in result.result


class TestAnalyticsToolsIntegration:
    """Integration tests for analytics tools."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, executor, db_session):
        """Test getting analytics with no data."""
        call = ToolCallRequest(
            tool_name="get_analytics",
            parameters={"period": "7d"},
            call_id="call_1",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["period"] == "7d"
        assert result.result["token_usage"]["tokens_in"] == 0
        assert result.result["totals"]["feeds"] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_with_data(
        self, executor, db_session, sample_feed, sample_feed_run, digest_factory
    ):
        """Test getting analytics with existing data."""
        # Create some digests
        digest_factory()
        digest_factory()

        call = ToolCallRequest(
            tool_name="get_analytics",
            parameters={"period": "7d"},
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["totals"]["feeds"] >= 1
        assert result.result["totals"]["digests"] >= 2
        assert result.result["feed_runs"]["total_runs"] >= 1


class TestTagToolsIntegration:
    """Integration tests for tag-related tools."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_list_tags_empty(self, executor, db_session):
        """Test listing tags when none exist."""
        call = ToolCallRequest(
            tool_name="list_tags",
            parameters={},
            call_id="call_1",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result == []

    @pytest.mark.asyncio
    async def test_list_tags_with_data(self, executor, db_session, sample_tags):
        """Test listing tags with existing data."""
        call = ToolCallRequest(
            tool_name="list_tags",
            parameters={"limit": 50},
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert len(result.result) == 3
        tag_names = {t["name"] for t in result.result}
        assert "ai" in tag_names
        assert "machine-learning" in tag_names

    @pytest.mark.asyncio
    async def test_create_tag_new(self, executor, db_session):
        """Test creating a new tag."""
        call = ToolCallRequest(
            tool_name="create_tag",
            parameters={"name": "testing"},
            call_id="call_3",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["name"] == "testing"
        assert result.result["already_existed"] is False

        # Verify in database
        tag = db_session.query(Tag).filter_by(name="testing").first()
        assert tag is not None

    @pytest.mark.asyncio
    async def test_create_tag_existing(self, executor, db_session, sample_tags):
        """Test creating a tag that already exists."""
        call = ToolCallRequest(
            tool_name="create_tag",
            parameters={"name": "ai"},  # Already exists
            call_id="call_4",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is True
        assert result.result["name"] == "ai"
        assert result.result["already_existed"] is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestToolExecutionErrors:
    """Test error handling in tool execution."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor with real tool registry."""
        import reconly_core.chat.tools_impl
        return ToolExecutor(tool_registry)

    @pytest.mark.asyncio
    async def test_database_error_handling(self, executor):
        """Test that database errors are caught and reported."""
        # Execute without providing db context
        call = ToolCallRequest(
            tool_name="list_feeds",
            parameters={},
            call_id="call_1",
        )

        result = await executor.execute(call, context={})

        # Should fail because db is missing
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_invalid_parameters_caught(self, executor, db_session):
        """Test that invalid parameters are caught."""
        call = ToolCallRequest(
            tool_name="create_feed",
            parameters={
                # Missing required 'name' parameter
                "description": "Test feed",
            },
            call_id="call_2",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is False
        assert "Missing required parameter" in result.error
        assert "name" in result.error

    @pytest.mark.asyncio
    async def test_enum_validation(self, executor, db_session):
        """Test that enum validation works."""
        call = ToolCallRequest(
            tool_name="get_analytics",
            parameters={"period": "invalid_period"},  # Not in enum
            call_id="call_3",
        )

        result = await executor.execute(call, context={"db": db_session})

        assert result.success is False
        assert "invalid value" in result.error.lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_disabled(self, db_session):
        """Test executing with validation disabled (but tool might still fail)."""
        import reconly_core.chat.tools_impl
        executor = ToolExecutor(tool_registry, validate_parameters=False)

        call = ToolCallRequest(
            tool_name="list_feeds",
            parameters={"invalid_param": "value"},
            call_id="call_4",
        )

        # Should not fail on parameter validation, but the handler may reject unexpected kwargs
        result = await executor.execute(call, context={"db": db_session})

        # The executor doesn't validate, but the handler's signature determines if it accepts extra params
        # list_feeds handler doesn't use **kwargs, so it will fail at runtime
        # This test verifies validation was disabled (no validation error), even if execution fails differently
        if not result.success:
            # Should be a TypeError from handler, not a validation error
            assert "unexpected keyword argument" in result.error.lower()
        else:
            # Handler accepted the param (would need **kwargs in signature)
            assert result.success is True


# =============================================================================
# Tool Result Conversion Tests
# =============================================================================


class TestToolResultConversion:
    """Test ToolResult to ToolCallResult conversion."""

    def test_to_tool_call_result_success(self):
        """Test converting successful result."""
        result = ToolResult(
            call_id="call_123",
            tool_name="test_tool",
            success=True,
            result={"data": "value"},
            execution_time_ms=100,
        )

        converted = result.to_tool_call_result()

        assert converted.call_id == "call_123"
        assert converted.tool_name == "test_tool"
        assert converted.result == {"data": "value"}
        assert converted.is_error is False

    def test_to_tool_call_result_error(self):
        """Test converting error result."""
        result = ToolResult(
            call_id="call_456",
            tool_name="failing_tool",
            success=False,
            error="Something went wrong",
            execution_time_ms=50,
        )

        converted = result.to_tool_call_result()

        assert converted.call_id == "call_456"
        assert converted.tool_name == "failing_tool"
        assert converted.result == {"error": "Something went wrong"}
        assert converted.is_error is True
