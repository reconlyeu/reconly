"""Tests for VectorSearchService."""
import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from reconly_core.rag.search.vector import VectorSearchService, VectorSearchResult
from reconly_core.database.models import Digest, DigestChunk, FeedRun, Source


class TestVectorSearchService:
    """Test suite for VectorSearchService."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
        provider.get_dimension = Mock(return_value=1024)
        provider.get_model_info = Mock(return_value={
            'provider': 'ollama',
            'model': 'bge-m3',
            'dimension': 1024,
        })
        return provider

    @pytest.fixture
    def vector_service(self, db_session, mock_embedding_provider):
        """Return configured vector search service."""
        return VectorSearchService(db_session, mock_embedding_provider)

    @pytest.fixture
    def sample_digest_with_chunks(self, db_session):
        """Create sample digest with embedded chunks."""
        # Create source
        source = Source(
            name="Test Source",
            type="manual",
            url="https://example.com", config={}
        )
        db_session.add(source)
        db_session.flush()

        # Create digest
        digest = Digest(
            title="Sample Digest",
            content="This is a sample digest about AI and machine learning.",
            source_id=source.id,
        )
        db_session.add(digest)
        db_session.flush()

        # Create chunks with embeddings (pgvector format - list of floats)
        embeddings = [
            np.random.rand(1024).astype(np.float32).tolist(),
            np.random.rand(1024).astype(np.float32).tolist(),
        ]

        for idx, emb in enumerate(embeddings):
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=idx,
                text=f"Chunk {idx} content",
                token_count=50,
                start_char=idx * 100,
                end_char=(idx + 1) * 100,
                embedding=emb,
            )
            db_session.add(chunk)

        db_session.commit()
        return digest

    def test_initialization(self, db_session, mock_embedding_provider):
        """Test service initialization."""
        service = VectorSearchService(db_session, mock_embedding_provider)
        assert service.db == db_session
        assert service.embedding_provider == mock_embedding_provider
        assert service._is_postgres is True  # PostgreSQL in tests

    def test_detect_postgres(self, db_session, mock_embedding_provider):
        """Test PostgreSQL detection."""
        service = VectorSearchService(db_session, mock_embedding_provider)
        # Should be True for PostgreSQL test database
        assert service._is_postgres is True

    @pytest.mark.asyncio
    async def test_get_query_embedding(self, vector_service, mock_embedding_provider):
        """Test query embedding generation."""
        query = "test query"
        embedding = await vector_service.get_query_embedding(query)

        assert embedding == [0.1] * 1024
        mock_embedding_provider.embed_single.assert_called_once_with(query)

    def test_get_embedding_dimension(self, vector_service, mock_embedding_provider):
        """Test getting embedding dimension."""
        dim = vector_service.get_embedding_dimension()
        assert dim == 1024
        mock_embedding_provider.get_dimension.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_results(self, vector_service, sample_digest_with_chunks):
        """Test search returns results."""
        results = await vector_service.search("machine learning", limit=10)

        assert isinstance(results, list)
        # Should find chunks from sample digest
        assert len(results) > 0

        for result in results:
            assert isinstance(result, VectorSearchResult)
            assert result.chunk_id > 0
            assert result.digest_id == sample_digest_with_chunks.id
            assert result.text != ""
            assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_search_empty_results(self, vector_service, db_session):
        """Test search with no matching chunks."""
        # No digests in database
        results = await vector_service.search("test query", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_limit(self, vector_service, sample_digest_with_chunks):
        """Test search respects limit parameter."""
        results = await vector_service.search("test", limit=1)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_search_with_feed_filter(self, vector_service, db_session, sample_digest_with_chunks):
        """Test search with feed_id filter."""
        # Create feed and feed run
        from reconly_core.database.models import Feed

        feed = Feed(name="Test Feed", type="rss", url="https://example.com", config={})
        db_session.add(feed)
        db_session.flush()

        feed_run = FeedRun(feed_id=feed.id, status="completed")
        db_session.add(feed_run)
        db_session.flush()

        # Update digest with feed_run_id
        sample_digest_with_chunks.feed_run_id = feed_run.id
        db_session.commit()

        results = await vector_service.search("test", feed_id=feed.id)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_with_source_filter(self, vector_service, sample_digest_with_chunks):
        """Test search with source_id filter."""
        results = await vector_service.search("test", source_id=sample_digest_with_chunks.source_id)
        assert len(results) > 0

        # Search with different source_id should return no results
        results = await vector_service.search("test", source_id=9999)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_days_filter(self, vector_service, sample_digest_with_chunks):
        """Test search with days filter."""
        results = await vector_service.search("test", days=30)
        # Should find recent digest
        assert len(results) > 0

        # Search with 0 days might not find results depending on timing
        results = await vector_service.search("test", days=0)
        # Just verify it doesn't error
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_min_score(self, vector_service, sample_digest_with_chunks):
        """Test search with minimum score filter."""
        # Search with high threshold might filter out results
        results_high = await vector_service.search("test", min_score=0.95)
        results_low = await vector_service.search("test", min_score=0.0)

        # Low threshold should return more or equal results
        assert len(results_low) >= len(results_high)

    def test_search_sync(self, vector_service, sample_digest_with_chunks):
        """Test synchronous search with pre-computed embedding."""
        query_embedding = [0.1] * 1024
        results = vector_service.search_sync(query_embedding, limit=10)

        assert isinstance(results, list)
        assert len(results) > 0

        for result in results:
            assert isinstance(result, VectorSearchResult)

    def test_deserialize_embedding_list(self, vector_service):
        """Test deserializing list embedding (pgvector format)."""
        embedding = [0.1, 0.2, 0.3]
        result = vector_service._deserialize_embedding(embedding)
        assert result == embedding

    def test_deserialize_embedding_none(self, vector_service):
        """Test deserializing None."""
        result = vector_service._deserialize_embedding(None)
        assert result is None


class TestVectorSearchResult:
    """Test the VectorSearchResult dataclass."""

    def test_result_creation(self):
        """Test creating a VectorSearchResult."""
        result = VectorSearchResult(
            chunk_id=1,
            digest_id=42,
            chunk_index=0,
            text="Test chunk content",
            score=0.95,
            distance=0.05,
        )

        assert result.chunk_id == 1
        assert result.digest_id == 42
        assert result.chunk_index == 0
        assert result.text == "Test chunk content"
        assert result.score == 0.95
        assert result.distance == 0.05
        assert result.extra_data is None

    def test_result_with_extra_data(self):
        """Test VectorSearchResult with extra metadata."""
        result = VectorSearchResult(
            chunk_id=1,
            digest_id=42,
            chunk_index=0,
            text="Test chunk",
            score=0.95,
            distance=0.05,
            extra_data={"heading": "Introduction", "source": "summary"},
        )

        assert result.extra_data["heading"] == "Introduction"
        assert result.extra_data["source"] == "summary"


