"""Tests for HybridSearchService."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import time

from reconly_core.rag.search.hybrid import (
    HybridSearchService,
    HybridSearchResult,
    HybridSearchResponse,
    ChunkMatch,
    QueryEmbeddingCache,
)
from reconly_core.rag.search.vector import VectorSearchResult
from reconly_core.rag.search.fts import FTSSearchResult


class TestQueryEmbeddingCache:
    """Test suite for QueryEmbeddingCache."""

    @pytest.fixture
    def cache(self):
        """Return a cache instance."""
        return QueryEmbeddingCache(max_size=10, ttl_seconds=1.0)

    def test_initialization(self):
        """Test cache initialization."""
        cache = QueryEmbeddingCache(max_size=100, ttl_seconds=600)
        assert cache.max_size == 100
        assert cache.ttl_seconds == 600
        assert cache._hits == 0
        assert cache._misses == 0

    def test_set_and_get(self, cache):
        """Test setting and getting cache entries."""
        embedding = [0.1, 0.2, 0.3]
        cache.set("test query", "ollama", "bge-m3", embedding)

        result = cache.get("test query", "ollama", "bge-m3")
        assert result == embedding

    def test_cache_miss(self, cache):
        """Test cache miss."""
        result = cache.get("unknown query", "ollama", "bge-m3")
        assert result is None

    def test_cache_hit_tracking(self, cache):
        """Test hit/miss tracking."""
        embedding = [0.1, 0.2, 0.3]
        cache.set("query", "ollama", "bge-m3", embedding)

        # Miss
        cache.get("unknown", "ollama", "bge-m3")
        assert cache._misses == 1

        # Hit
        cache.get("query", "ollama", "bge-m3")
        assert cache._hits == 1

    def test_ttl_expiration(self, cache):
        """Test TTL expiration."""
        embedding = [0.1, 0.2, 0.3]
        cache.set("query", "ollama", "bge-m3", embedding)

        # Should be cached
        result = cache.get("query", "ollama", "bge-m3")
        assert result is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        result = cache.get("query", "ollama", "bge-m3")
        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = QueryEmbeddingCache(max_size=2, ttl_seconds=10.0)

        cache.set("query1", "ollama", "model1", [0.1])
        cache.set("query2", "ollama", "model2", [0.2])
        cache.set("query3", "ollama", "model3", [0.3])  # Should evict query1

        # query1 should be evicted
        assert cache.get("query1", "ollama", "model1") is None
        # query2 and query3 should still be there
        assert cache.get("query2", "ollama", "model2") is not None
        assert cache.get("query3", "ollama", "model3") is not None

    def test_clear(self, cache):
        """Test clearing the cache."""
        cache.set("query", "ollama", "bge-m3", [0.1])
        cache.clear()

        # After clear, stats should be reset (before any get calls)
        stats = cache.get_stats()
        assert stats['size'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0

        # Verify the entry is gone (this will increment misses)
        assert cache.get("query", "ollama", "bge-m3") is None

    def test_get_stats(self, cache):
        """Test getting cache statistics."""
        cache.set("query1", "ollama", "bge-m3", [0.1])
        cache.get("query1", "ollama", "bge-m3")  # Hit
        cache.get("query2", "ollama", "bge-m3")  # Miss

        stats = cache.get_stats()
        assert stats['size'] == 1
        assert stats['max_size'] == 10
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5


class TestHybridSearchService:
    """Test suite for HybridSearchService."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
        provider.get_dimension = Mock(return_value=1024)
        provider.get_provider_name = Mock(return_value='ollama')
        provider.get_model_info = Mock(return_value={
            'provider': 'ollama',
            'model': 'bge-m3',
            'dimension': 1024,
        })
        return provider

    @pytest.fixture
    def hybrid_service(self, db_session, mock_embedding_provider):
        """Return configured hybrid search service."""
        return HybridSearchService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            enable_cache=True,
        )

    def test_initialization(self, db_session, mock_embedding_provider):
        """Test service initialization."""
        service = HybridSearchService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            k=50,
            vector_weight=0.6,
            fts_weight=0.4,
        )

        assert service.db == db_session
        assert service.embedding_provider == mock_embedding_provider
        assert service.k == 50
        assert service.vector_weight == 0.6
        assert service.fts_weight == 0.4
        assert service._embedding_cache is not None

    def test_initialization_without_cache(self, db_session, mock_embedding_provider):
        """Test initialization with cache disabled."""
        service = HybridSearchService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            enable_cache=False,
        )

        assert service._embedding_cache is None

    @pytest.mark.asyncio
    async def test_search_hybrid_mode(self, hybrid_service):
        """Test hybrid search mode."""
        with patch.object(hybrid_service.vector_service, 'search_sync') as mock_vector, \
             patch.object(hybrid_service.fts_service, 'search') as mock_fts:

            # Mock vector search results
            mock_vector.return_value = [
                VectorSearchResult(
                    chunk_id=1,
                    digest_id=1,
                    chunk_index=0,
                    text="Machine learning chunk",
                    score=0.9,
                    distance=0.1,
                )
            ]

            # Mock FTS results
            mock_fts.return_value = [
                FTSSearchResult(
                    digest_id=1,
                    title="ML Article",
                    summary=None,
                    score=0.8,
                    matched_field="title",
                    snippet="Machine learning is...",
                )
            ]

            response = await hybrid_service.search(
                query="machine learning",
                limit=10,
                mode='hybrid',
            )

            assert isinstance(response, HybridSearchResponse)
            assert response.mode == 'hybrid'
            assert len(response.results) > 0
            assert response.vector_results_count == 1
            assert response.fts_results_count == 1
            assert response.took_ms > 0

    @pytest.mark.asyncio
    async def test_search_vector_only_mode(self, hybrid_service):
        """Test vector-only search mode."""
        with patch.object(hybrid_service.vector_service, 'search_sync') as mock_vector:
            mock_vector.return_value = [
                VectorSearchResult(
                    chunk_id=1,
                    digest_id=1,
                    chunk_index=0,
                    text="Test chunk",
                    score=0.9,
                    distance=0.1,
                )
            ]

            response = await hybrid_service.search(
                query="test",
                mode='vector',
            )

            assert response.mode == 'vector'
            assert response.vector_results_count == 1
            assert response.fts_results_count == 0

    @pytest.mark.asyncio
    async def test_search_fts_only_mode(self, hybrid_service):
        """Test FTS-only search mode."""
        with patch.object(hybrid_service.fts_service, 'search') as mock_fts:
            mock_fts.return_value = [
                FTSSearchResult(
                    digest_id=1,
                    title="Test Article",
                    summary=None,
                    score=0.8,
                    matched_field="title",
                    snippet="Test content",
                )
            ]

            response = await hybrid_service.search(
                query="test",
                mode='fts',
            )

            assert response.mode == 'fts'
            assert response.vector_results_count == 0
            assert response.fts_results_count == 1

    @pytest.mark.asyncio
    async def test_search_with_filters(self, hybrid_service):
        """Test search with various filters."""
        with patch.object(hybrid_service.vector_service, 'search_sync') as mock_vector, \
             patch.object(hybrid_service.fts_service, 'search') as mock_fts:

            mock_vector.return_value = []
            mock_fts.return_value = []

            await hybrid_service.search(
                query="test",
                feed_id=1,
                source_id=2,
                days=30,
            )

            # Verify filters were passed
            mock_vector.assert_called_once()
            call_kwargs = mock_vector.call_args[1]
            assert call_kwargs['feed_id'] == 1
            assert call_kwargs['source_id'] == 2
            assert call_kwargs['days'] == 30

    @pytest.mark.asyncio
    async def test_search_with_embedding_cache(self, hybrid_service, mock_embedding_provider):
        """Test that embedding cache is used."""
        with patch.object(hybrid_service.vector_service, 'search_sync') as mock_vector, \
             patch.object(hybrid_service.fts_service, 'search') as mock_fts:

            mock_vector.return_value = []
            mock_fts.return_value = []

            # First search - should generate embedding
            await hybrid_service.search("test query", mode='vector')
            assert mock_embedding_provider.embed_single.call_count == 1

            # Second search with same query - should use cache
            await hybrid_service.search("test query", mode='vector')
            # Still only 1 call because of cache
            assert mock_embedding_provider.embed_single.call_count == 1

    @pytest.mark.asyncio
    async def test_search_include_embedding(self, hybrid_service):
        """Test search with include_embedding flag."""
        with patch.object(hybrid_service.vector_service, 'search_sync') as mock_vector, \
             patch.object(hybrid_service.fts_service, 'search') as mock_fts:

            mock_vector.return_value = []
            mock_fts.return_value = []

            response = await hybrid_service.search(
                query="test",
                mode='vector',
                include_embedding=True,
            )

            assert response.query_embedding is not None
            assert len(response.query_embedding) == 1024

    def test_merge_with_rrf(self, hybrid_service):
        """Test RRF merging algorithm."""
        vector_results = [
            VectorSearchResult(1, 1, 0, "chunk1", 0.9, 0.1),
            VectorSearchResult(2, 2, 0, "chunk2", 0.8, 0.2),
        ]

        fts_results = [
            FTSSearchResult(digest_id=1, title="Title 1", summary=None, score=0.95, matched_field="title", snippet="snippet1"),
            FTSSearchResult(digest_id=3, title="Title 3", summary=None, score=0.7, matched_field="title", snippet="snippet3"),
        ]

        merged = hybrid_service._merge_with_rrf(vector_results, fts_results, limit=10)

        assert isinstance(merged, list)
        assert all(isinstance(r, HybridSearchResult) for r in merged)

        # Results should be sorted by RRF score
        scores = [r.score for r in merged]
        assert scores == sorted(scores, reverse=True)

        # Digest 1 should have both sources
        digest1_result = next(r for r in merged if r.digest_id == 1)
        assert 'vector' in digest1_result.sources
        assert 'fts' in digest1_result.sources

    def test_convert_vector_results(self, hybrid_service, db_session):
        """Test converting vector results to hybrid format."""
        from reconly_core.database.models import Digest, Source

        # Create test digest
        source = Source(name="Test", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="Test Digest", url="https://test.example.com/test-digest", content="Content", source_id=source.id)
        db_session.add(digest)
        db_session.commit()

        vector_results = [
            VectorSearchResult(1, digest.id, 0, "chunk1", 0.9, 0.1),
        ]

        converted = hybrid_service._convert_vector_results(vector_results)

        assert len(converted) == 1
        assert converted[0].digest_id == digest.id
        assert converted[0].title == "Test Digest"
        assert converted[0].sources == ['vector']

    def test_convert_fts_results(self, hybrid_service):
        """Test converting FTS results to hybrid format."""
        fts_results = [
            FTSSearchResult(digest_id=1, title="Title 1", summary=None, score=0.95, matched_field="title", snippet="snippet1"),
            FTSSearchResult(digest_id=2, title="Title 2", summary=None, score=0.85, matched_field="title", snippet="snippet2"),
        ]

        converted = hybrid_service._convert_fts_results(fts_results)

        assert len(converted) == 2
        assert all(r.sources == ['fts'] for r in converted)
        assert converted[0].title == "Title 1"
        assert converted[1].title == "Title 2"

    def test_get_cache_stats(self, hybrid_service):
        """Test getting cache statistics."""
        stats = hybrid_service.get_cache_stats()

        assert stats is not None
        assert 'size' in stats
        assert 'hits' in stats
        assert 'misses' in stats

    def test_clear_cache(self, hybrid_service):
        """Test clearing the cache."""
        hybrid_service.clear_cache()

        stats = hybrid_service.get_cache_stats()
        assert stats['size'] == 0

    def test_get_search_stats(self, hybrid_service):
        """Test getting search statistics."""
        stats = hybrid_service.get_search_stats()

        assert stats['k'] == hybrid_service.k
        assert stats['vector_weight'] == hybrid_service.vector_weight
        assert stats['fts_weight'] == hybrid_service.fts_weight
        assert stats['embedding_provider'] == 'ollama'
        assert stats['embedding_dimension'] == 1024
        assert stats['cache_enabled'] is True


class TestChunkMatch:
    """Test ChunkMatch dataclass."""

    def test_chunk_match_creation(self):
        """Test creating a ChunkMatch."""
        match = ChunkMatch(
            text="Test chunk",
            score=0.95,
            chunk_index=0,
        )

        assert match.text == "Test chunk"
        assert match.score == 0.95
        assert match.chunk_index == 0


class TestHybridSearchResult:
    """Test HybridSearchResult dataclass."""

    def test_result_creation(self):
        """Test creating a HybridSearchResult."""
        chunks = [
            ChunkMatch("chunk1", 0.9, 0),
            ChunkMatch("chunk2", 0.8, 1),
        ]

        result = HybridSearchResult(
            digest_id=42,
            title="Test Digest",
            matched_chunks=chunks,
            score=0.85,
            vector_rank=1,
            fts_rank=2,
            sources=['vector', 'fts'],
        )

        assert result.digest_id == 42
        assert result.title == "Test Digest"
        assert len(result.matched_chunks) == 2
        assert result.score == 0.85
        assert result.vector_rank == 1
        assert result.fts_rank == 2
        assert 'vector' in result.sources
        assert 'fts' in result.sources


class TestHybridSearchResponse:
    """Test HybridSearchResponse dataclass."""

    def test_response_creation(self):
        """Test creating a HybridSearchResponse."""
        results = [
            HybridSearchResult(
                digest_id=1,
                title="Test",
                matched_chunks=[],
                score=0.9,
            )
        ]

        response = HybridSearchResponse(
            results=results,
            query_embedding=[0.1] * 1024,
            took_ms=123.45,
            mode='hybrid',
            vector_results_count=5,
            fts_results_count=3,
        )

        assert len(response.results) == 1
        assert len(response.query_embedding) == 1024
        assert response.took_ms == 123.45
        assert response.mode == 'hybrid'
        assert response.vector_results_count == 5
        assert response.fts_results_count == 3
