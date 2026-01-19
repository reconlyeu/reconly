"""Tests for FeedService._process_rag_for_feed_run() source content embedding.

Tests the background task that triggers source content embedding after digest creation.
"""
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest

from sqlalchemy import or_

from reconly_core.database.models import (
    Feed, FeedRun, Digest, Source, DigestSourceItem, SourceContent
)
from reconly_core.services.feed_service import FeedService


# Constants
TEST_EMBEDDING_DIM = 1024


def create_source(db_session, name="Test Source"):
    """Helper to create a Source."""
    source = Source(
        name=name,
        type="rss",
        url=f"https://{name.lower().replace(' ', '-')}.example.com/feed",
        config={},
    )
    db_session.add(source)
    db_session.flush()
    return source


def create_feed(db_session, name="Test Feed"):
    """Helper to create a Feed."""
    feed = Feed(
        name=name,
        digest_mode="individual",
    )
    db_session.add(feed)
    db_session.flush()
    return feed


def create_feed_run(db_session, feed):
    """Helper to create a FeedRun."""
    feed_run = FeedRun(
        feed_id=feed.id,
        triggered_by="manual",
        status="completed",
    )
    db_session.add(feed_run)
    db_session.flush()
    return feed_run


def create_digest(db_session, source, feed_run, title="Test Digest", idx=0):
    """Helper to create a Digest."""
    digest = Digest(
        url=f"https://example.com/{title.lower().replace(' ', '-')}-{idx}",
        title=title,
        content="This is the test content.",
        summary="Test summary.",
        source_id=source.id,
        source_type="rss",
        feed_run_id=feed_run.id,
        embedding_status='completed',  # Mark as already embedded to skip digest embedding
    )
    db_session.add(digest)
    db_session.flush()
    return digest


def create_source_content(db_session, digest, source, content="Original article content", idx=0):
    """Helper to create DigestSourceItem and SourceContent."""
    digest_source_item = DigestSourceItem(
        digest_id=digest.id,
        source_id=source.id,
        item_url=f"{digest.url}-item-{idx}",
        item_title=digest.title,
        item_published_at=datetime.now(timezone.utc),
    )
    db_session.add(digest_source_item)
    db_session.flush()

    content_hash = hashlib.sha256(f"{content}-{idx}".encode('utf-8')).hexdigest()
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content=f"{content}-{idx}",
        content_hash=content_hash,
        content_length=len(content),
        fetched_at=datetime.now(timezone.utc),
        embedding_status=None,
    )
    db_session.add(source_content)
    db_session.flush()

    return source_content


def query_unembedded_source_content(db_session, digest_ids):
    """Query for source content that needs embedding.

    This mirrors the query used in _process_rag_for_feed_run().
    """
    return db_session.query(SourceContent).join(
        DigestSourceItem,
        SourceContent.digest_source_item_id == DigestSourceItem.id
    ).filter(
        DigestSourceItem.digest_id.in_(digest_ids),
        or_(
            SourceContent.embedding_status.is_(None),
            SourceContent.embedding_status != 'completed'
        )
    ).all()


class TestProcessRagSourceContent:
    """Tests for source content embedding in _process_rag_for_feed_run()."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()

        async def embed_multi(texts):
            return [[0.1] * TEST_EMBEDDING_DIM for _ in texts]

        provider.embed = AsyncMock(side_effect=embed_multi)
        provider.get_dimension = Mock(return_value=TEST_EMBEDDING_DIM)
        provider.get_provider_name = Mock(return_value='test-provider')
        return provider

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_query_finds_unembedded_content(self, db_session):
        """Test that the query correctly identifies unembedded source content."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        digest = create_digest(db_session, source, feed_run)
        source_content = create_source_content(db_session, digest, source)
        db_session.commit()

        found = query_unembedded_source_content(db_session, [digest.id])

        assert len(found) == 1
        assert found[0].id == source_content.id

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_query_skips_completed(self, db_session):
        """Test that the query skips already-embedded source content."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        digest = create_digest(db_session, source, feed_run)
        source_content = create_source_content(db_session, digest, source)
        source_content.embedding_status = 'completed'
        db_session.commit()

        found = query_unembedded_source_content(db_session, [digest.id])

        assert len(found) == 0

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_query_includes_failed(self, db_session):
        """Test that the query includes failed source content for retry."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        digest = create_digest(db_session, source, feed_run)
        source_content = create_source_content(db_session, digest, source)
        source_content.embedding_status = 'failed'
        db_session.commit()

        found = query_unembedded_source_content(db_session, [digest.id])

        assert len(found) == 1
        assert found[0].id == source_content.id

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_query_multiple_digests(self, db_session):
        """Test that the query handles multiple digests correctly."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)

        digests = []
        for i in range(3):
            digest = create_digest(db_session, source, feed_run, title="Test Digest", idx=i)
            create_source_content(db_session, digest, source, content="Content", idx=i)
            digests.append(digest)
        db_session.commit()

        digest_ids = [d.id for d in digests]
        found = query_unembedded_source_content(db_session, digest_ids)

        assert len(found) == 3

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_query_mixed_statuses(self, db_session):
        """Test query with mixed embedding statuses."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)

        digests = []
        source_contents = []
        for i in range(3):
            digest = create_digest(db_session, source, feed_run, title="Test Digest", idx=i)
            sc = create_source_content(db_session, digest, source, content="Content", idx=i)
            digests.append(digest)
            source_contents.append(sc)

        source_contents[0].embedding_status = 'completed'  # Should skip
        source_contents[1].embedding_status = 'failed'     # Should include
        source_contents[2].embedding_status = None         # Should include
        db_session.commit()

        digest_ids = [d.id for d in digests]
        found = query_unembedded_source_content(db_session, digest_ids)

        assert len(found) == 2

    @pytest.mark.database
    @pytest.mark.unit
    def test_no_source_content_returns_empty(self, db_session):
        """Test that query returns empty when no source content exists."""
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        digest = create_digest(db_session, source, feed_run)
        db_session.commit()

        found = query_unembedded_source_content(db_session, [digest.id])

        assert len(found) == 0

    @pytest.mark.database
    @pytest.mark.unit
    def test_source_content_only_from_feed_run(self, db_session):
        """Test that only source content from the specific feed run is included."""
        source = create_source(db_session)
        feed = create_feed(db_session)

        # First feed run
        feed_run1 = create_feed_run(db_session, feed)
        digest1 = create_digest(db_session, source, feed_run1, title="Digest 1", idx=1)
        sc1 = create_source_content(db_session, digest1, source, content="Content 1", idx=1)

        # Second feed run
        feed_run2 = create_feed_run(db_session, feed)
        digest2 = create_digest(db_session, source, feed_run2, title="Digest 2", idx=2)
        create_source_content(db_session, digest2, source, content="Content 2", idx=2)
        db_session.commit()

        # Query for first feed run only
        digests = db_session.query(Digest).filter(
            Digest.feed_run_id == feed_run1.id
        ).all()
        digest_ids = [d.id for d in digests]

        found = query_unembedded_source_content(db_session, digest_ids)

        assert len(found) == 1
        assert found[0].id == sc1.id


class TestProcessRagIntegration:
    """Integration-style tests for the RAG processing flow."""

    @pytest.mark.database
    @pytest.mark.unit
    def test_process_rag_handles_import_error_gracefully(self, db_session):
        """Test that _process_rag_for_feed_run handles import errors gracefully."""
        # Setup
        source = create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        create_digest(db_session, source, feed_run)
        db_session.commit()

        # Mock the imports to raise ImportError
        with patch.dict('sys.modules', {'reconly_core.rag': None}):
            # Run the RAG processing - should NOT raise
            service = FeedService()
            # This should handle the ImportError gracefully
            service._process_rag_for_feed_run(feed_run, db_session, show_progress=False)

    @pytest.mark.database
    @pytest.mark.unit
    def test_process_rag_no_digests_returns_early(self, db_session):
        """Test that _process_rag_for_feed_run returns early when no digests exist."""
        # Setup: Create feed run without any digests
        create_source(db_session)
        feed = create_feed(db_session)
        feed_run = create_feed_run(db_session, feed)
        # Note: NOT creating any digests
        db_session.commit()

        # Mock to verify early return
        with patch('reconly_core.rag.EmbeddingService') as MockEmbeddingService:
            service = FeedService()
            service._process_rag_for_feed_run(feed_run, db_session, show_progress=False)

            # EmbeddingService should never be instantiated if no digests
            MockEmbeddingService.assert_not_called()
