"""Test configuration and shared fixtures.

This is the single source of truth for database fixtures used across all tests.
Both API tests and core tests should use these fixtures.
"""
import os
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from reconly_core.database.models import (
    Base,
    Digest,
    DigestChunk,
    DigestTag,
    Feed,
    FeedRun,
    FeedSource,
    PromptTemplate,
    ReportTemplate,
    Source,
    Tag,
)

# Import edition fixtures to make them available to all tests
# These are imported via pytest_plugins for proper fixture discovery
pytest_plugins = ["tests.edition_fixtures"]


# =============================================================================
# Database Configuration
# =============================================================================

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://reconly:reconly_dev@localhost:5432/reconly_test"
)


# =============================================================================
# Database Engine & Connection Fixtures
# =============================================================================

# Global flag to track database availability (checked once at session start)
_db_available = None
_db_error = None


def _check_db_available():
    """Check if the test database is available (cached result)."""
    global _db_available, _db_error
    if _db_available is None:
        try:
            engine = create_engine(TEST_DATABASE_URL, echo=False)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            _db_available = True
        except OperationalError as e:
            _db_available = False
            _db_error = str(e)
    return _db_available


def pytest_collection_modifyitems(config, items):
    """Skip API tests if database is unavailable."""
    if not _check_db_available():
        skip_marker = pytest.mark.skip(reason=f"Database unavailable: {_db_error}")
        for item in items:
            # Skip tests in tests/api directory that need DB
            item_path = str(item.fspath)
            if "tests/api" in item_path or "tests\\api" in item_path:
                item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine (session-scoped for efficiency).

    Enables pgvector extension and creates all tables once per test session.
    Skips tests gracefully if database is unavailable.
    """
    if not _check_db_available():
        pytest.skip(f"Database unavailable: {_db_error}")

    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Enable pgvector extension before creating tables
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_connection(test_engine):
    """Create a database connection with transaction rollback isolation.

    All database operations in a test share this connection. The transaction
    is rolled back after each test for clean isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_session(test_connection) -> Session:
    """Create a database session bound to the shared test connection.

    This is the primary fixture for database access in tests.
    Alias: test_db (for backwards compatibility with API tests)
    """
    SessionFactory = sessionmaker(bind=test_connection)
    session = SessionFactory()

    yield session

    session.close()


# Alias for API tests that use test_db naming
@pytest.fixture(scope="function")
def test_db(db_session) -> Session:
    """Alias for db_session - used by API tests."""
    return db_session


# =============================================================================
# Digest Factory Fixture
# =============================================================================

@pytest.fixture
def digest_factory(db_session):
    """Factory fixture for creating test digests with various configurations.

    Usage:
        digest = digest_factory()  # Basic digest
        digest = digest_factory(with_tags=["ai", "ml"])  # With tags
        digest = digest_factory(with_chunks=3)  # With N embedding chunks
        digest = digest_factory(title="Custom", summary="Test")  # Custom fields
    """
    created_digests = []

    def _create_digest(
        *,
        title: str = "Test Digest",
        url: str | None = None,
        summary: str = "Test summary content",
        source_type: str = "rss",
        with_tags: list[str] | None = None,
        with_chunks: int = 0,
        chunk_embedding: list[float] | None = None,
        **kwargs: Any,
    ) -> Digest:
        # Generate unique URL if not provided
        if url is None:
            url = f"https://example.com/article-{len(created_digests)}"

        digest = Digest(
            url=url,
            title=title,
            summary=summary,
            source_type=source_type,
            **kwargs,
        )
        db_session.add(digest)
        db_session.flush()  # Get the ID

        # Add tags if requested
        if with_tags:
            for tag_name in with_tags:
                # Get or create tag
                tag = db_session.query(Tag).filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db_session.add(tag)
                    db_session.flush()

                digest_tag = DigestTag(digest_id=digest.id, tag_id=tag.id)
                db_session.add(digest_tag)

        # Add chunks if requested
        if with_chunks > 0:
            for i in range(with_chunks):
                chunk = DigestChunk(
                    digest_id=digest.id,
                    chunk_index=i,
                    text=f"Chunk {i} text for {title}",
                    embedding=chunk_embedding,
                    token_count=50,
                    start_char=i * 100,
                    end_char=(i + 1) * 100,
                )
                db_session.add(chunk)

        db_session.commit()
        db_session.refresh(digest)
        created_digests.append(digest)
        return digest

    return _create_digest


# =============================================================================
# Sample Entity Fixtures
# =============================================================================

@pytest.fixture
def sample_source(db_session) -> Source:
    """Create a sample RSS source for testing."""
    source = Source(
        name="Test RSS Feed",
        type="rss",
        url="https://example.com/feed.xml",
        enabled=True,
        config={"max_items": 10},
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def sample_prompt_template(db_session) -> PromptTemplate:
    """Create a sample prompt template for testing."""
    template = PromptTemplate(
        name="Test Prompt Template",
        description="A test template",
        system_prompt="You are a helpful assistant.",
        user_prompt_template="Summarize: {{ content }}",
        language="en",
        target_length=150,
        origin="user",
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def sample_report_template(db_session) -> ReportTemplate:
    """Create a sample report template for testing."""
    template = ReportTemplate(
        name="Test Report Template",
        description="A test report template",
        format="markdown",
        template_content="# Report\n\n{content}",
        origin="user",
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def sample_feed(
    db_session,
    sample_source,
    sample_prompt_template,
    sample_report_template,
) -> Feed:
    """Create a sample feed with source and templates for testing."""
    feed = Feed(
        name="Test Feed",
        description="A test feed",
        schedule_cron="0 9 * * *",
        schedule_enabled=True,
        prompt_template_id=sample_prompt_template.id,
        report_template_id=sample_report_template.id,
    )
    db_session.add(feed)
    db_session.commit()
    db_session.refresh(feed)

    # Link source to feed
    feed_source = FeedSource(
        feed_id=feed.id,
        source_id=sample_source.id,
        priority=0,
        enabled=True,
    )
    db_session.add(feed_source)
    db_session.commit()

    db_session.refresh(feed)
    return feed


@pytest.fixture
def sample_feed_run(db_session, sample_feed) -> FeedRun:
    """Create a sample completed feed run for testing."""
    feed_run = FeedRun(
        feed_id=sample_feed.id,
        triggered_by="manual",
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        sources_total=1,
        sources_processed=1,
        sources_failed=0,
        items_processed=5,
        total_tokens_in=1000,
        total_tokens_out=500,
        total_cost=0.01,
        trace_id="test-trace-id-12345",
    )
    db_session.add(feed_run)
    db_session.commit()
    db_session.refresh(feed_run)
    return feed_run


@pytest.fixture
def sample_failed_feed_run(db_session, sample_feed) -> FeedRun:
    """Create a sample failed feed run for testing."""
    feed_run = FeedRun(
        feed_id=sample_feed.id,
        triggered_by="schedule",
        status="failed",
        started_at=datetime.utcnow() - timedelta(minutes=2),
        completed_at=datetime.utcnow(),
        sources_total=1,
        sources_processed=0,
        sources_failed=1,
        items_processed=0,
        total_tokens_in=0,
        total_tokens_out=0,
        total_cost=0,
        trace_id="test-trace-id-failed",
        error_log="Error: Connection failed",
        error_details={
            "errors": [
                {
                    "source_id": 1,
                    "source_name": "Test Source",
                    "error_type": "FetchError",
                    "message": "Connection timeout",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
            "summary": "1 source(s) failed during processing",
        },
    )
    db_session.add(feed_run)
    db_session.commit()
    db_session.refresh(feed_run)
    return feed_run


@pytest.fixture
def sample_tags(db_session) -> list[Tag]:
    """Create sample tags for testing."""
    tags = []
    for name in ["ai", "machine-learning", "python"]:
        tag = Tag(name=name)
        db_session.add(tag)
        tags.append(tag)
    db_session.commit()
    for tag in tags:
        db_session.refresh(tag)
    return tags


@pytest.fixture
def sample_digest(db_session) -> Digest:
    """Create a basic sample digest for testing."""
    digest = Digest(
        url="https://example.com/article",
        title="Test Article",
        summary="This is a test summary.",
        source_type="rss",
    )
    db_session.add(digest)
    db_session.commit()
    db_session.refresh(digest)
    return digest


@pytest.fixture
def sample_digests(db_session) -> list[Digest]:
    """Create multiple sample digests for testing."""
    digests = []
    for i in range(3):
        digest = Digest(
            url=f"https://example.com/article-{i}",
            title=f"Test Article {i}",
            summary=f"Summary for article {i}.",
            source_type="rss",
        )
        db_session.add(digest)
        digests.append(digest)
    db_session.commit()
    for digest in digests:
        db_session.refresh(digest)
    return digests
