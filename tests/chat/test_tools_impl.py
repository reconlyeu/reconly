"""Tests for tool handler implementations."""

import pytest
from datetime import datetime

from reconly_core.chat.tools_impl import (
    list_feeds_tool,
    create_feed_tool,
    list_sources_tool,
    create_source_tool,
    search_digests_tool,
    query_knowledge_tool,
)
from reconly_core.database.models import Feed, Source, Digest, Tag


class TestListFeedsTool:
    """Test list_feeds tool handler."""

    @pytest.fixture
    def tool(self):
        """Get the tool definition."""
        return list_feeds_tool()

    @pytest.mark.asyncio
    async def test_list_feeds_empty(self, db_session, tool):
        """Test listing feeds when none exist."""
        result = await tool.handler(db=db_session)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_feeds_with_data(self, db_session, sample_feed, tool):
        """Test listing feeds with existing data."""
        result = await tool.handler(db=db_session)

        assert len(result) >= 1
        feed_data = result[0]

        assert "id" in feed_data
        assert "name" in feed_data
        assert "schedule_enabled" in feed_data
        assert feed_data["name"] == sample_feed.name

    @pytest.mark.asyncio
    async def test_list_feeds_enabled_only(self, db_session, tool):
        """Test filtering for enabled feeds only."""
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
        db_session.add(enabled_feed)
        db_session.add(disabled_feed)
        db_session.commit()

        result = await tool.handler(db=db_session, enabled_only=True)

        assert len(result) >= 1
        assert all(f["schedule_enabled"] for f in result)

    @pytest.mark.asyncio
    async def test_list_feeds_limit(self, db_session, tool):
        """Test limiting number of results."""
        # Create multiple feeds
        for i in range(5):
            feed = Feed(name=f"Feed {i}", schedule_enabled=True)
            db_session.add(feed)
        db_session.commit()

        result = await tool.handler(db=db_session, limit=2)

        assert len(result) == 2

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "list_feeds"
        assert tool.description
        assert tool.parameters["type"] == "object"
        assert tool.category == "feeds"


class TestCreateFeedTool:
    """Test create_feed tool handler."""

    @pytest.fixture
    def tool(self):
        return create_feed_tool()

    @pytest.mark.asyncio
    async def test_create_feed_basic(self, db_session, tool):
        """Test creating a basic feed."""
        result = await tool.handler(
            db=db_session,
            name="Tech News",
            description="Technology news aggregator",
        )

        assert result["id"] is not None
        assert result["name"] == "Tech News"
        assert result["source_count"] == 0

        # Verify in database
        feed = db_session.query(Feed).filter_by(name="Tech News").first()
        assert feed is not None
        assert feed.description == "Technology news aggregator"

    @pytest.mark.asyncio
    async def test_create_feed_with_sources(self, db_session, sample_source, tool):
        """Test creating feed with existing sources."""
        result = await tool.handler(
            db=db_session,
            name="News Feed",
            source_ids=[sample_source.id],
            schedule_cron="0 8 * * *",
            schedule_enabled=True,
        )

        assert result["source_count"] == 1
        assert result["schedule_cron"] == "0 8 * * *"

        # Verify sources are linked
        feed = db_session.query(Feed).filter_by(id=result["id"]).first()
        assert len(feed.feed_sources) == 1

    @pytest.mark.asyncio
    async def test_create_feed_with_inline_sources(self, db_session, tool):
        """Test creating feed with inline source definitions."""
        result = await tool.handler(
            db=db_session,
            name="Inline Sources Feed",
            sources=[
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
        )

        assert result["source_count"] == 2
        assert result["sources_created"] == 2

        # Verify sources were created
        sources = db_session.query(Source).filter(
            Source.name.in_(["TechCrunch", "Hacker News"])
        ).all()
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_create_feed_invalid_digest_mode(self, db_session, tool):
        """Test that invalid digest_mode raises error."""
        with pytest.raises(ValueError, match="Invalid digest_mode"):
            await tool.handler(
                db=db_session,
                name="Bad Feed",
                digest_mode="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_create_feed_with_prompt_template(self, db_session, tool):
        """Test creating feed with inline prompt template."""
        result = await tool.handler(
            db=db_session,
            name="Feed with Template",
            prompt_template={
                "name": "Custom Prompt",
                "system_prompt": "You are a tech summarizer.",
                "user_prompt_template": "Summarize: {content}",
            },
        )

        assert result["prompt_template_id"] is not None

        # Verify template was created
        feed = db_session.query(Feed).filter_by(id=result["id"]).first()
        assert feed.prompt_template is not None
        assert feed.prompt_template.name == "Custom Prompt"

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "create_feed"
        assert "source_ids" in tool.parameters["properties"]
        assert "sources" in tool.parameters["properties"]
        assert tool.category == "feeds"


class TestListSourcesTool:
    """Test list_sources tool handler."""

    @pytest.fixture
    def tool(self):
        return list_sources_tool()

    @pytest.mark.asyncio
    async def test_list_sources_empty(self, db_session, tool):
        """Test listing sources when none exist."""
        result = await tool.handler(db=db_session)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_sources_with_data(self, db_session, sample_source, tool):
        """Test listing sources with existing data."""
        result = await tool.handler(db=db_session)

        assert len(result) >= 1
        source_data = result[0]

        assert "id" in source_data
        assert "name" in source_data
        assert "type" in source_data
        assert "url" in source_data

    @pytest.mark.asyncio
    async def test_list_sources_filter_by_type(self, db_session, tool):
        """Test filtering sources by type."""
        # Create sources of different types
        rss_source = Source(name="RSS Feed", type="rss", url="https://example.com/rss")
        youtube_source = Source(
            name="YT Channel", type="youtube", url="https://youtube.com/channel"
        )
        db_session.add(rss_source)
        db_session.add(youtube_source)
        db_session.commit()

        result = await tool.handler(db=db_session, source_type="rss")

        assert len(result) >= 1
        assert all(s["type"] == "rss" for s in result)

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "list_sources"
        assert tool.category == "sources"


class TestCreateSourceTool:
    """Test create_source tool handler."""

    @pytest.fixture
    def tool(self):
        return create_source_tool()

    @pytest.mark.asyncio
    async def test_create_source(self, db_session, tool):
        """Test creating a source."""
        result = await tool.handler(
            db=db_session,
            name="TechCrunch",
            url="https://techcrunch.com/feed/",
            source_type="rss",
        )

        assert result["id"] is not None
        assert result["name"] == "TechCrunch"
        assert result["type"] == "rss"

        # Verify in database
        source = db_session.query(Source).filter_by(name="TechCrunch").first()
        assert source is not None

    @pytest.mark.asyncio
    async def test_create_source_with_config(self, db_session, tool):
        """Test creating source with custom config."""
        result = await tool.handler(
            db=db_session,
            name="Custom Source",
            url="https://example.com/feed",
            source_type="rss",
            config={"max_items": 20, "fetch_full_content": True},
        )

        source = db_session.query(Source).filter_by(id=result["id"]).first()
        assert source.config["max_items"] == 20

    @pytest.mark.asyncio
    async def test_create_source_invalid_type(self, db_session, tool):
        """Test that invalid source type raises error."""
        with pytest.raises(ValueError, match="Invalid source_type"):
            await tool.handler(
                db=db_session,
                name="Bad Source",
                url="https://example.com",
                source_type="invalid_type",
            )

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "create_source"
        assert "url" in tool.parameters["required"]
        assert tool.category == "sources"


class TestSearchDigestsTool:
    """Test search_digests tool handler."""

    @pytest.fixture
    def tool(self):
        return search_digests_tool()

    @pytest.mark.asyncio
    async def test_search_digests_empty(self, db_session, tool):
        """Test searching when no digests exist."""
        result = await tool.handler(db=db_session)

        assert result["total"] == 0
        assert len(result["digests"]) == 0

    @pytest.mark.asyncio
    async def test_search_digests_with_data(self, db_session, digest_factory, tool):
        """Test searching with existing digests."""
        # Create test digests
        digest_factory(title="Python Tutorial", summary="Learn Python basics")
        digest_factory(title="JavaScript Guide", summary="Master JavaScript")

        result = await tool.handler(db=db_session)

        assert result["total"] >= 2
        assert len(result["digests"]) >= 2

    @pytest.mark.asyncio
    async def test_search_digests_by_query(self, db_session, digest_factory, tool):
        """Test full-text search."""
        # Create digests with different content
        digest_factory(title="Python Tutorial", summary="Learn Python programming")
        digest_factory(title="Java Basics", summary="Introduction to Java")

        result = await tool.handler(db=db_session, query="Python")

        assert result["total"] >= 1
        assert any("Python" in d["title"] for d in result["digests"])

    @pytest.mark.asyncio
    async def test_search_digests_by_tags(
        self, db_session, digest_factory, sample_tags, tool
    ):
        """Test filtering by tags."""
        # Create digest with tags
        digest = digest_factory(with_tags=["python", "tutorial"])

        result = await tool.handler(db=db_session, tags=["python"])

        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_digests_limit(self, db_session, digest_factory, tool):
        """Test limiting search results."""
        # Create multiple digests
        for i in range(5):
            digest_factory(title=f"Digest {i}")

        result = await tool.handler(db=db_session, limit=2)

        assert len(result["digests"]) == 2

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "search_digests"
        assert tool.category == "digests"


class TestQueryKnowledgeTool:
    """Test query_knowledge tool handler (RAG)."""

    @pytest.fixture
    def tool(self):
        return query_knowledge_tool()

    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="Requires embedding provider and LLM setup")
    async def test_query_knowledge_basic(self, db_session, tool):
        """Test basic knowledge query.

        This test is skipped by default as it requires:
        - Embedding provider configured
        - LLM provider configured
        - Digests with embeddings in database
        """
        result = await tool.handler(
            db=db_session,
            question="What is Python?",
        )

        assert "answer" in result
        assert "citations" in result
        assert isinstance(result["citations"], list)

    def test_tool_definition(self, tool):
        """Test tool has correct definition."""
        assert tool.name == "query_knowledge"
        assert "question" in tool.parameters["required"]
        assert tool.category == "knowledge"


class TestToolHandlerErrorHandling:
    """Test error handling in tool handlers."""

    @pytest.mark.asyncio
    async def test_create_feed_with_invalid_cron(self, db_session):
        """Test that invalid cron expression is handled gracefully."""
        tool = create_feed_tool()

        # Should not raise, but log warning
        result = await tool.handler(
            db=db_session,
            name="Feed with Bad Cron",
            schedule_cron="invalid cron",
            schedule_enabled=True,
        )

        # Feed should still be created
        assert result["id"] is not None
        # But next_run_at should be None
        feed = db_session.query(Feed).filter_by(id=result["id"]).first()
        assert feed.next_run_at is None

    @pytest.mark.asyncio
    async def test_search_with_invalid_source_id(self, db_session):
        """Test searching with nonexistent source ID."""
        tool = search_digests_tool()

        # Should not raise, just return empty results
        result = await tool.handler(db=db_session, source_id=99999)

        assert result["total"] == 0


class TestToolParameterValidation:
    """Test that tools validate parameters correctly."""

    def test_list_feeds_parameters(self):
        """Test list_feeds parameter schema."""
        tool = list_feeds_tool()

        assert "enabled_only" in tool.parameters["properties"]
        assert tool.parameters["properties"]["enabled_only"]["type"] == "boolean"

        assert "limit" in tool.parameters["properties"]
        assert tool.parameters["properties"]["limit"]["type"] == "integer"

    def test_create_feed_parameters(self):
        """Test create_feed parameter schema."""
        tool = create_feed_tool()

        assert "name" in tool.parameters["required"]
        assert "digest_mode" in tool.parameters["properties"]
        assert "enum" in tool.parameters["properties"]["digest_mode"]

    def test_search_digests_parameters(self):
        """Test search_digests parameter schema."""
        tool = search_digests_tool()

        properties = tool.parameters["properties"]
        assert "query" in properties
        assert "tags" in properties
        assert properties["tags"]["type"] == "array"
        assert properties["tags"]["items"]["type"] == "string"
