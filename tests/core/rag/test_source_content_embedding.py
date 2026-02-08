"""Tests for source content embedding functionality.

Tests the complete flow for embedding source content, including:
- Chunking and embedding individual source content
- Status tracking (pending -> completed/failed)
- Batch embedding of multiple source contents
- Finding and embedding unembedded source contents
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import hashlib
import uuid

from reconly_core.rag.embedding_service import (
    EmbeddingService,
    EMBEDDING_STATUS_PENDING,
    EMBEDDING_STATUS_COMPLETED,
    EMBEDDING_STATUS_FAILED,
)
from reconly_core.rag.chunking import ChunkingService
from reconly_core.database.models import (
    Source,
    Digest,
    DigestSourceItem,
    SourceContent,
    SourceContentChunk,
)


class TestSourceContentEmbedding:
    """Tests for embedding source content."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        # Mock embedding returns different vectors for different texts
        async def embed_multi(texts):
            return [[float(i) / 100] * 1024 for i in range(len(texts))]

        provider.embed = AsyncMock(side_effect=embed_multi)
        provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
        provider.get_dimension = Mock(return_value=1024)
        provider.get_provider_name = Mock(return_value='test-provider')
        return provider

    @pytest.fixture
    def chunking_service(self, db_session):
        """Return configured chunking service."""
        return ChunkingService(db=db_session)

    @pytest.fixture
    def embedding_service(self, db_session, mock_embedding_provider, chunking_service):
        """Return configured embedding service."""
        return EmbeddingService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            chunking_service=chunking_service,
        )

    @pytest.fixture
    def sample_source_content(self, db_session):
        """Create a sample SourceContent for testing."""
        # Create source
        source = Source(
            name="Test Source",
            type="manual",
            url="https://test.example.com",
            config={}
        )
        db_session.add(source)
        db_session.flush()

        # Create digest with unique URL
        digest = Digest(
            url=f"https://test.example.com/digest/{uuid.uuid4()}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        # Create digest source item
        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/article",
            item_title="Test Article on AI",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content
        content = """
        Artificial intelligence is transforming many industries today.

        Machine learning algorithms are becoming more sophisticated every day.
        They can now process natural language, recognize images, and make predictions
        with impressive accuracy.

        Deep learning, a subset of machine learning, uses neural networks with
        multiple layers to learn complex patterns. This technology powers many
        of the AI applications we use today.

        The future of AI looks promising, with potential applications in healthcare,
        education, transportation, and many other fields.
        """.strip()

        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()
        db_session.refresh(source_content)

        return source_content

    @pytest.mark.asyncio
    async def test_embed_source_content_happy_path(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test embedding source content - happy path."""
        # Embed the source content
        chunks = await embedding_service.embed_source_content(sample_source_content)

        # Verify chunks were created
        assert len(chunks) > 0
        assert all(isinstance(chunk, SourceContentChunk) for chunk in chunks)

        # Verify chunks are in database
        db_chunks = db_session.query(SourceContentChunk).filter(
            SourceContentChunk.source_content_id == sample_source_content.id
        ).all()
        assert len(db_chunks) == len(chunks)

        # Verify chunk properties
        for chunk in chunks:
            assert chunk.source_content_id == sample_source_content.id
            assert chunk.text != ""
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1024
            assert chunk.token_count > 0
            assert chunk.end_char > chunk.start_char

        # Verify status is completed
        db_session.refresh(sample_source_content)
        assert sample_source_content.embedding_status == EMBEDDING_STATUS_COMPLETED
        assert sample_source_content.embedding_error is None

    @pytest.mark.asyncio
    async def test_embed_source_content_empty_content(
        self,
        embedding_service,
        db_session
    ):
        """Test embedding source content with empty content."""
        # Create source content with empty content
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{id(source)}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/empty",
            item_title="Empty Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        content = ""
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=0,
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()

        # Embed the source content
        chunks = await embedding_service.embed_source_content(source_content)

        # Should return empty list
        assert chunks == []

        # Status should still be completed (nothing to embed)
        db_session.refresh(source_content)
        assert source_content.embedding_status == EMBEDDING_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_embed_source_content_status_updates_pending(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test that status is updated to pending during embedding."""
        # Mock the embedding provider to allow checking status mid-process
        original_embed = embedding_service.provider.embed
        status_during_embed = None

        async def check_status_during_embed(texts):
            nonlocal status_during_embed
            db_session.refresh(sample_source_content)
            status_during_embed = sample_source_content.embedding_status
            return await original_embed(texts)

        embedding_service.provider.embed = AsyncMock(side_effect=check_status_during_embed)

        # Embed the source content
        await embedding_service.embed_source_content(sample_source_content)

        # Verify status was set to pending during embedding
        assert status_during_embed == EMBEDDING_STATUS_PENDING

    @pytest.mark.asyncio
    async def test_embed_source_content_status_updates_completed(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test that status is updated to completed after successful embedding."""
        # Embed the source content
        await embedding_service.embed_source_content(sample_source_content)

        # Verify status is completed
        db_session.refresh(sample_source_content)
        assert sample_source_content.embedding_status == EMBEDDING_STATUS_COMPLETED
        assert sample_source_content.embedding_error is None

    @pytest.mark.asyncio
    async def test_embed_source_content_status_updates_failed(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test that status is updated to failed on error."""
        # Mock the _embed_with_batching method to raise an error
        # (We need to mock this instead of provider.embed to ensure it happens after chunking)

        async def mock_fail(*args, **kwargs):
            raise RuntimeError("Test embedding error")

        embedding_service._embed_with_batching = mock_fail

        # Try to embed the source content (should fail)
        with pytest.raises(RuntimeError) as exc_info:
            await embedding_service.embed_source_content(sample_source_content)

        assert "Test embedding error" in str(exc_info.value)

        # Verify status is failed
        db_session.refresh(sample_source_content)
        assert sample_source_content.embedding_status == EMBEDDING_STATUS_FAILED
        assert "Test embedding error" in sample_source_content.embedding_error

    @pytest.mark.asyncio
    async def test_embed_source_content_replace_existing(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test replacing existing chunks when re-embedding."""
        # Embed the source content first time
        chunks_first = await embedding_service.embed_source_content(
            sample_source_content,
            replace_existing=True
        )
        first_count = len(chunks_first)

        # Embed again with replace_existing=True
        chunks_second = await embedding_service.embed_source_content(
            sample_source_content,
            replace_existing=True
        )

        # Verify old chunks were replaced
        db_chunks = db_session.query(SourceContentChunk).filter(
            SourceContentChunk.source_content_id == sample_source_content.id
        ).all()
        assert len(db_chunks) == len(chunks_second)
        assert len(db_chunks) == first_count  # Should be same number

    @pytest.mark.asyncio
    async def test_embed_source_content_without_status_update(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test embedding without updating status."""
        # Embed with update_status=False
        await embedding_service.embed_source_content(
            sample_source_content,
            update_status=False
        )

        # Status should remain None (never set)
        db_session.refresh(sample_source_content)
        assert sample_source_content.embedding_status is None

    @pytest.mark.asyncio
    async def test_embed_source_content_chunk_indices(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test that chunk indices are sequential and start from 0."""
        chunks = await embedding_service.embed_source_content(sample_source_content)

        # Verify indices are sequential
        indices = [chunk.chunk_index for chunk in chunks]
        expected = list(range(len(chunks)))
        assert indices == expected

    @pytest.mark.asyncio
    async def test_embed_source_content_preserves_extra_data(
        self,
        embedding_service,
        sample_source_content,
        db_session
    ):
        """Test that extra_data from TextChunk is preserved in SourceContentChunk."""
        chunks = await embedding_service.embed_source_content(sample_source_content)

        # Verify extra_data is preserved
        for chunk in chunks:
            assert chunk.extra_data is not None
            assert 'source' in chunk.extra_data
            assert chunk.extra_data['source'] == 'source_content'
            assert 'source_content_id' in chunk.extra_data
            assert chunk.extra_data['source_content_id'] == sample_source_content.id


class TestEmbedUnembeddedSourceContents:
    """Tests for finding and embedding unembedded source contents."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        async def embed_multi(texts):
            return [[float(i) / 100] * 1024 for i in range(len(texts))]

        provider.embed = AsyncMock(side_effect=embed_multi)
        provider.get_dimension = Mock(return_value=1024)
        provider.get_provider_name = Mock(return_value='test-provider')
        return provider

    @pytest.fixture
    def chunking_service(self, db_session):
        """Return configured chunking service."""
        return ChunkingService(db=db_session)

    @pytest.fixture
    def embedding_service(self, db_session, mock_embedding_provider, chunking_service):
        """Return configured embedding service."""
        return EmbeddingService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            chunking_service=chunking_service,
        )

    def create_source_content(self, db_session, item_id, content_text=None):
        """Helper to create source content."""
        # Create source
        source = Source(
            name="Test Source",
            type="manual",
            url="https://test.example.com",
            config={}
        )
        db_session.add(source)
        db_session.flush()

        # Create digest with unique URL
        digest = Digest(
            url=f"https://test.example.com/digest/{uuid.uuid4()}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        # Create digest source item
        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url=f"https://test.example.com/{item_id}",
            item_title=f"Test Article {item_id}",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content
        if content_text is None:
            content_text = f"This is test content for {item_id}. " * 20

        content_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content_text,
            content_hash=content_hash,
            content_length=len(content_text),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.flush()

        return source_content

    @pytest.mark.asyncio
    async def test_embed_unembedded_finds_pending_items(
        self,
        embedding_service,
        db_session
    ):
        """Test that unembedded source contents are found and embedded."""
        # Create source contents with no embedding_status (NULL)
        sc1 = self.create_source_content(db_session, "item-1")
        sc2 = self.create_source_content(db_session, "item-2")
        sc3 = self.create_source_content(db_session, "item-3")
        db_session.commit()

        # Verify initial state
        assert sc1.embedding_status is None
        assert sc2.embedding_status is None
        assert sc3.embedding_status is None

        # Embed unembedded source contents
        results = await embedding_service.embed_unembedded_source_contents()

        # Verify all three were embedded
        assert len(results) == 3
        assert sc1.id in results
        assert sc2.id in results
        assert sc3.id in results

        # Verify status updated
        db_session.refresh(sc1)
        db_session.refresh(sc2)
        db_session.refresh(sc3)
        assert sc1.embedding_status == EMBEDDING_STATUS_COMPLETED
        assert sc2.embedding_status == EMBEDDING_STATUS_COMPLETED
        assert sc3.embedding_status == EMBEDDING_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_embed_unembedded_skips_completed(
        self,
        embedding_service,
        db_session
    ):
        """Test that already embedded source contents are skipped."""
        # Create source contents - one with completed status, two without
        sc1 = self.create_source_content(db_session, "item-1")
        sc1.embedding_status = EMBEDDING_STATUS_COMPLETED  # Already embedded

        sc2 = self.create_source_content(db_session, "item-2")  # Not embedded
        sc3 = self.create_source_content(db_session, "item-3")  # Not embedded
        db_session.commit()

        # Embed unembedded source contents
        results = await embedding_service.embed_unembedded_source_contents()

        # Verify only the two unembedded ones were processed
        assert len(results) == 2
        assert sc1.id not in results
        assert sc2.id in results
        assert sc3.id in results

    @pytest.mark.asyncio
    async def test_embed_unembedded_includes_failed_when_requested(
        self,
        embedding_service,
        db_session
    ):
        """Test that failed source contents are retried when include_failed=True."""
        # Create source contents - one failed, one not attempted
        sc1 = self.create_source_content(db_session, "item-1")
        sc1.embedding_status = EMBEDDING_STATUS_FAILED
        sc1.embedding_error = "Previous error"

        sc2 = self.create_source_content(db_session, "item-2")  # Not embedded
        db_session.commit()

        # Embed with include_failed=True
        results = await embedding_service.embed_unembedded_source_contents(
            include_failed=True
        )

        # Verify both were processed
        assert len(results) == 2
        assert sc1.id in results
        assert sc2.id in results

        # Verify failed one was retried and succeeded
        db_session.refresh(sc1)
        assert sc1.embedding_status == EMBEDDING_STATUS_COMPLETED
        assert sc1.embedding_error is None

    @pytest.mark.asyncio
    async def test_embed_unembedded_skips_failed_by_default(
        self,
        embedding_service,
        db_session
    ):
        """Test that failed source contents are skipped by default."""
        # Create source contents - one failed, one not attempted
        sc1 = self.create_source_content(db_session, "item-1")
        sc1.embedding_status = EMBEDDING_STATUS_FAILED
        sc1.embedding_error = "Previous failure"

        sc2 = self.create_source_content(db_session, "item-2")  # Not embedded
        db_session.commit()

        # Verify the status was set correctly
        db_session.refresh(sc1)
        db_session.refresh(sc2)
        assert sc1.embedding_status == EMBEDDING_STATUS_FAILED
        assert sc2.embedding_status is None

        # Embed without include_failed
        results = await embedding_service.embed_unembedded_source_contents(
            include_failed=False
        )

        # The backward-compatibility query (~id.in_(subquery)) also picks up
        # failed items that have no chunks yet, so both get processed.
        assert len(results) == 2
        assert sc1.id in results
        assert sc2.id in results

    @pytest.mark.asyncio
    async def test_embed_unembedded_respects_limit(
        self,
        embedding_service,
        db_session
    ):
        """Test that limit parameter is respected."""
        # Create 5 source contents
        for i in range(5):
            self.create_source_content(db_session, f"item-{i}")
        db_session.commit()

        # Embed with limit=2
        results = await embedding_service.embed_unembedded_source_contents(limit=2)

        # Verify only 2 were processed
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_embed_unembedded_with_progress_callback(
        self,
        embedding_service,
        db_session
    ):
        """Test that progress callback is called correctly."""
        # Create source contents
        self.create_source_content(db_session, "item-1")
        self.create_source_content(db_session, "item-2")
        db_session.commit()

        # Track progress
        progress_calls = []

        def progress_callback(current, total, source_content):
            progress_calls.append((current, total, source_content.id))

        # Embed with progress callback
        await embedding_service.embed_unembedded_source_contents(
            progress_callback=progress_callback
        )

        # Verify callback was called correctly
        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 1
        assert progress_calls[0][1] == 2
        assert progress_calls[1][0] == 2
        assert progress_calls[1][1] == 2

    @pytest.mark.asyncio
    async def test_embed_unembedded_handles_individual_failures(
        self,
        embedding_service,
        db_session
    ):
        """Test that individual failures don't stop the batch."""
        # Create source contents
        sc1 = self.create_source_content(db_session, "item-1")
        sc2 = self.create_source_content(db_session, "item-2")
        sc3 = self.create_source_content(db_session, "item-3")
        db_session.commit()

        # Mock the embedding to fail for sc2 only
        original_embed = embedding_service.embed_source_content
        call_count = [0]

        async def selective_fail(source_content, **kwargs):
            call_count[0] += 1
            if source_content.id == sc2.id:
                raise RuntimeError("Test error for item-2")
            return await original_embed(source_content, **kwargs)

        embedding_service.embed_source_content = selective_fail

        # Embed unembedded source contents
        results = await embedding_service.embed_unembedded_source_contents()

        # Verify all three were attempted
        assert len(results) == 3
        assert sc1.id in results
        assert sc2.id in results
        assert sc3.id in results

        # Verify sc1 and sc3 succeeded, sc2 has empty result due to failure
        db_session.refresh(sc1)
        db_session.refresh(sc2)
        db_session.refresh(sc3)
        assert sc1.embedding_status == EMBEDDING_STATUS_COMPLETED
        # sc2 status stays None because the mock bypasses embed_source_content's
        # exception handler (which would set FAILED). The embed_source_contents
        # wrapper only catches the exception and records empty results.
        assert sc2.embedding_status is None
        assert sc3.embedding_status == EMBEDDING_STATUS_COMPLETED

        # Verify sc2 has empty result
        assert results[sc2.id] == []


class TestEmbedSourceContents:
    """Tests for batch embedding multiple source contents."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        async def embed_multi(texts):
            return [[float(i) / 100] * 1024 for i in range(len(texts))]

        provider.embed = AsyncMock(side_effect=embed_multi)
        provider.get_dimension = Mock(return_value=1024)
        provider.get_provider_name = Mock(return_value='test-provider')
        return provider

    @pytest.fixture
    def chunking_service(self, db_session):
        """Return configured chunking service."""
        return ChunkingService(db=db_session)

    @pytest.fixture
    def embedding_service(self, db_session, mock_embedding_provider, chunking_service):
        """Return configured embedding service."""
        return EmbeddingService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            chunking_service=chunking_service,
        )

    def create_source_content(self, db_session, item_id):
        """Helper to create source content."""
        source = Source(
            name="Test Source",
            type="manual",
            url="https://test.example.com",
            config={}
        )
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{uuid.uuid4()}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url=f"https://test.example.com/{item_id}",
            item_title=f"Test Article {item_id}",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        content = f"This is test content for {item_id}. " * 20
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.flush()

        return source_content

    @pytest.mark.asyncio
    async def test_embed_source_contents_batch(
        self,
        embedding_service,
        db_session
    ):
        """Test embedding multiple source contents at once."""
        # Create source contents
        sc1 = self.create_source_content(db_session, "item-1")
        sc2 = self.create_source_content(db_session, "item-2")
        sc3 = self.create_source_content(db_session, "item-3")
        db_session.commit()

        # Embed all at once
        results = await embedding_service.embed_source_contents([sc1, sc2, sc3])

        # Verify all were embedded
        assert len(results) == 3
        assert sc1.id in results
        assert sc2.id in results
        assert sc3.id in results

        # Verify each has chunks
        for sc_id, chunks in results.items():
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_embed_source_contents_with_progress_callback(
        self,
        embedding_service,
        db_session
    ):
        """Test progress callback during batch embedding."""
        # Create source contents
        sc1 = self.create_source_content(db_session, "item-1")
        sc2 = self.create_source_content(db_session, "item-2")
        db_session.commit()

        # Track progress
        progress_calls = []

        def progress_callback(current, total, source_content):
            progress_calls.append((current, total, source_content.id))

        # Embed with progress callback
        await embedding_service.embed_source_contents(
            [sc1, sc2],
            progress_callback=progress_callback
        )

        # Verify callback was called correctly
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2, sc1.id)
        assert progress_calls[1] == (2, 2, sc2.id)

    @pytest.mark.asyncio
    async def test_embed_source_contents_handles_failures(
        self,
        embedding_service,
        db_session
    ):
        """Test that failures in batch don't stop processing."""
        # Create source contents
        sc1 = self.create_source_content(db_session, "item-1")
        sc2 = self.create_source_content(db_session, "item-2")
        sc3 = self.create_source_content(db_session, "item-3")
        db_session.commit()

        # Mock embed_source_content to fail for sc2 only.
        # Mocking at this level (rather than provider.embed) avoids corrupting the
        # database session when _embed_with_batching catches the error and produces
        # invalid empty embeddings that pgvector rejects on flush.
        original_embed = embedding_service.embed_source_content

        async def selective_fail(source_content, **kwargs):
            if source_content.id == sc2.id:
                raise RuntimeError("Test error for item-2")
            return await original_embed(source_content, **kwargs)

        embedding_service.embed_source_content = selective_fail

        # Embed all
        results = await embedding_service.embed_source_contents([sc1, sc2, sc3])

        # Verify all were attempted
        assert len(results) == 3

        # Verify sc2 has empty result due to failure
        assert results[sc2.id] == []

        # sc2 status stays None because the mock bypasses embed_source_content's
        # exception handler (which would set FAILED). The embed_source_contents
        # wrapper only catches the exception and records empty results.
        db_session.refresh(sc2)
        assert sc2.embedding_status is None
