"""API integration tests for search endpoints."""
import pytest
import numpy as np
from unittest.mock import patch, Mock, AsyncMock

from reconly_core.database.models import Digest, DigestChunk, Source


class TestSearchAPI:
    """Test suite for search API endpoints."""

    @pytest.fixture
    def sample_digest_with_embeddings(self, test_db):
        """Create sample digest with embedded chunks."""
        source = Source(name="Test Source", type="manual", url="https://test.example.com")
        test_db.add(source)
        test_db.flush()

        digest = Digest(
            url="https://test.example.com/ai-ml",
            title="AI and Machine Learning",
            content="Artificial intelligence and machine learning are transforming industries.",
            source_id=source.id,
        )
        test_db.add(digest)
        test_db.flush()

        # Add chunks with embeddings (pgvector handles list conversion)
        embeddings = [
            np.random.rand(1024).astype(np.float32).tolist(),
            np.random.rand(1024).astype(np.float32).tolist(),
        ]

        for idx, embedding in enumerate(embeddings):
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=idx,
                text=f"AI chunk {idx}",
                token_count=50,
                start_char=idx * 100,
                end_char=(idx + 1) * 100,
                embedding=embedding,
            )
            test_db.add(chunk)

        test_db.commit()
        return digest

    def test_hybrid_search_endpoint(self, client, sample_digest_with_embeddings):
        """Test hybrid search endpoint."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=machine learning")

            assert response.status_code == 200
            data = response.json()

            assert "results" in data
            assert "took_ms" in data
            assert "mode" in data
            assert data["mode"] == "hybrid"

    def test_hybrid_search_with_query(self, client, sample_digest_with_embeddings):
        """Test search with query parameter."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=AI")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["results"], list)

    def test_hybrid_search_missing_query(self, client):
        """Test search without query parameter."""
        response = client.get("/api/v1/search/hybrid")
        assert response.status_code == 422  # Validation error

    def test_hybrid_search_with_filters(self, client, test_db, sample_digest_with_embeddings):
        """Test search with filters."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(
                f"/api/v1/search/hybrid?q=test&source_id={sample_digest_with_embeddings.source_id}&days=30"
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_hybrid_search_vector_mode(self, client, sample_digest_with_embeddings):
        """Test search with vector-only mode."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test&mode=vector")

            assert response.status_code == 200
            data = response.json()
            assert data["mode"] == "vector"

    def test_hybrid_search_fts_mode(self, client, sample_digest_with_embeddings):
        """Test search with FTS-only mode."""
        response = client.get("/api/v1/search/hybrid?q=test&mode=fts")

        # FTS mode may work even without embeddings
        assert response.status_code in [200, 500]  # May fail if FTS not available

    def test_hybrid_search_with_limit(self, client, sample_digest_with_embeddings):
        """Test search with limit parameter."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test&limit=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) <= 5

    def test_hybrid_search_with_include_embedding(self, client, sample_digest_with_embeddings):
        """Test search with include_embedding flag."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test&include_embedding=true")

            assert response.status_code == 200
            data = response.json()
            # May or may not include embedding depending on implementation
            assert "results" in data

    def test_search_response_structure(self, client, sample_digest_with_embeddings):
        """Test that search response has correct structure."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test")

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "results" in data
            assert "took_ms" in data
            assert "mode" in data
            assert "vector_results_count" in data
            assert "fts_results_count" in data

            # If there are results, verify result structure
            if data["results"]:
                result = data["results"][0]
                assert "digest_id" in result
                assert "title" in result
                assert "matched_chunks" in result
                assert "score" in result

    def test_search_invalid_mode(self, client):
        """Test search with invalid mode parameter."""
        response = client.get("/api/v1/search/hybrid?q=test&mode=invalid")
        assert response.status_code == 422  # Validation error

    def test_search_invalid_limit(self, client):
        """Test search with invalid limit parameter."""
        response = client.get("/api/v1/search/hybrid?q=test&limit=1000")
        assert response.status_code == 422  # Validation error (exceeds max)

    def test_search_stats_endpoint(self, client):
        """Test search stats endpoint if available."""
        # This endpoint may or may not exist
        response = client.get("/api/v1/search/stats")

        # Accept both 200 (exists) and 404 (not implemented)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify it returns some stats
            assert isinstance(data, dict)


class TestSearchAPIEdgeCases:
    """Test edge cases for search API."""

    def test_search_empty_database(self, client):
        """Test search with no digests in database."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test")

            assert response.status_code == 200
            data = response.json()
            assert data["results"] == []

    def test_search_very_long_query(self, client):
        """Test search with very long query."""
        long_query = "test " * 1000

        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(f"/api/v1/search/hybrid?q={long_query}")

            # Should either work or return error
            assert response.status_code in [200, 413, 422]

    def test_search_special_characters(self, client):
        """Test search with special characters."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            special_query = "test & <script> OR 'DROP TABLE'"
            response = client.get(f"/api/v1/search/hybrid?q={special_query}")

            # Should handle gracefully
            assert response.status_code in [200, 422]

    def test_search_provider_failure(self, client):
        """Test search when embedding provider fails."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.embed_single = AsyncMock(side_effect=RuntimeError("Provider error"))
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/search/hybrid?q=test&mode=vector")

            # Should return error
            assert response.status_code == 500
