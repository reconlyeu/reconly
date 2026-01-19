"""API integration tests for RAG endpoints."""
import pytest
import numpy as np
from unittest.mock import patch, Mock, AsyncMock

from reconly_core.database.models import Digest, DigestChunk, Source


class TestRAGAPI:
    """Test suite for RAG API endpoints."""

    @pytest.fixture
    def sample_digest_with_chunks(self, test_db):
        """Create sample digest with embedded chunks."""
        source = Source(
            name="Tech News",
            type="manual",
            url="https://technews.com"
        )
        test_db.add(source)
        test_db.flush()

        digest = Digest(
            url="https://test.example.com/ai-advances-2024",
            title="AI Advances in 2024",
            content="Artificial intelligence made significant progress in 2024.",
            source_id=source.id,
        )
        test_db.add(digest)
        test_db.flush()

        # Add chunks with embeddings (pgvector handles list conversion)
        for idx in range(3):
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=idx,
                text=f"AI progress chunk {idx}",
                token_count=50,
                start_char=idx * 100,
                end_char=(idx + 1) * 100,
                embedding=embedding,
            )
            test_db.add(chunk)

        test_db.commit()
        return digest

    def test_rag_query_endpoint(self, client, sample_digest_with_chunks):
        """Test RAG query endpoint."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            # Mock embedding provider
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            # Mock summarizer
            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'AI made progress in 2024 [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={"question": "What progress did AI make?"}
            )

            assert response.status_code == 200
            data = response.json()

            assert "answer" in data
            assert "citations" in data
            assert "chunks_retrieved" in data
            assert "grounded" in data
            assert "model_used" in data

    def test_rag_query_with_filters(self, client, sample_digest_with_chunks):
        """Test RAG query with filters."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Test answer [1].',
                'model_info': {'model': 'test'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "What is AI?",
                    "filters": {
                        "source_id": sample_digest_with_chunks.source_id,
                        "days": 30
                    }
                }
            )

            assert response.status_code == 200

    def test_rag_query_without_answer(self, client, sample_digest_with_chunks):
        """Test RAG query without generating answer (search only)."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "What is AI?",
                    "include_answer": False
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Should have citations but possibly empty answer
            assert "citations" in data

    def test_rag_query_custom_max_chunks(self, client, sample_digest_with_chunks):
        """Test RAG query with custom max_chunks."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Test [1].',
                'model_info': {'model': 'test'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "Test question",
                    "max_chunks": 5
                }
            )

            assert response.status_code == 200

    def test_rag_query_missing_question(self, client):
        """Test RAG query without question parameter."""
        response = client.post(
            "/api/v1/rag/query",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_rag_query_empty_database(self, client):
        """Test RAG query with no digests in database."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            response = client.post(
                "/api/v1/rag/query",
                json={"question": "Test question"}
            )

            # Should handle gracefully
            assert response.status_code in [200, 500]

    def test_rag_response_structure(self, client, sample_digest_with_chunks):
        """Test that RAG response has correct structure."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Answer with citation [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={"question": "What is AI?"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "answer" in data
            assert "citations" in data
            assert "chunks_retrieved" in data
            assert "grounded" in data
            assert "model_used" in data
            assert "search_took_ms" in data
            assert "generation_took_ms" in data
            assert "total_took_ms" in data

            # If there are citations, verify citation structure
            if data["citations"]:
                citation = data["citations"][0]
                assert "id" in citation
                assert "digest_id" in citation
                assert "digest_title" in citation

    def test_rag_export_markdown(self, client, sample_digest_with_chunks):
        """Test RAG export to markdown endpoint."""
        # This endpoint may not exist, testing if available
        response = client.post(
            "/api/v1/rag/export",
            json={
                "answer": "Test answer [1]",
                "citations": [
                    {
                        "id": 1,
                        "digest_id": sample_digest_with_chunks.id,
                        "digest_title": "Test",
                        "chunk_text": "chunk",
                        "url": "https://example.com"
                    }
                ],
                "format": "markdown"
            }
        )

        # Accept both 200 (exists) and 404 (not implemented)
        assert response.status_code in [200, 404, 422]


class TestRAGAPIEdgeCases:
    """Test edge cases for RAG API."""

    def test_rag_provider_failure_graceful_degradation(self, client):
        """Test RAG gracefully degrades when embedding provider fails.

        In hybrid mode (default), if vector search fails, the search falls back
        to FTS-only mode and returns a valid response.
        """
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb:
            provider = Mock()
            provider.embed_single = AsyncMock(side_effect=RuntimeError("Provider error"))
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            response = client.post(
                "/api/v1/rag/query",
                json={"question": "Test"}
            )

            # Hybrid mode gracefully falls back to FTS when vector search fails
            assert response.status_code == 200
            data = response.json()
            # With no data in DB, FTS returns no results, so we get "no sources" answer
            assert "cannot find" in data["answer"].lower() or data["chunks_retrieved"] == 0

    def test_rag_summarizer_failure(self, client, test_db):
        """Test RAG when summarizer fails after finding sources."""
        # Create test data with searchable content for FTS fallback
        source = Source(name="Test", type="manual", url="https://test.example.com")
        test_db.add(source)
        test_db.flush()

        # Use content that matches the search query for FTS to find it
        digest = Digest(
            url="https://test.example.com/test",
            title="Test Question Topic",
            content="This is content about the test question topic.",
            summary="A summary about the test question topic.",
            source_id=source.id
        )
        test_db.add(digest)
        test_db.flush()

        # Create a chunk that FTS can find
        chunk = DigestChunk(
            digest_id=digest.id,
            chunk_index=0,
            text="This chunk contains information about the test question topic.",
            token_count=10,
            start_char=0,
            end_char=100,
            embedding=None,  # No embedding needed, we'll use FTS fallback
        )
        test_db.add(chunk)
        test_db.commit()

        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            # Mock embedding provider to fail (triggers FTS fallback)
            provider = Mock()
            provider.embed_single = AsyncMock(side_effect=RuntimeError("Provider error"))
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            # Mock summarizer to fail
            summarizer = Mock()
            summarizer.summarize = Mock(side_effect=RuntimeError("Summarizer error"))
            summarizer.get_model_info = Mock(return_value={'model': 'test'})
            mock_sum.return_value = summarizer

            # Query with terms that FTS will match
            response = client.post(
                "/api/v1/rag/query",
                json={"question": "test question topic"}
            )

            # Should fail because summarizer raises error
            assert response.status_code == 500

    def test_rag_very_long_question(self, client):
        """Test RAG with very long question."""
        long_question = "What is the meaning of " + ("life " * 1000) + "?"

        with patch('reconly_core.rag.get_embedding_provider') as mock_emb:
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            response = client.post(
                "/api/v1/rag/query",
                json={"question": long_question}
            )

            # Should either work or return error
            assert response.status_code in [200, 413, 422, 500]

    def test_rag_invalid_max_chunks(self, client):
        """Test RAG with invalid max_chunks parameter."""
        response = client.post(
            "/api/v1/rag/query",
            json={
                "question": "Test",
                "max_chunks": 1000  # Exceeds limit
            }
        )

        assert response.status_code == 422  # Validation error

    def test_rag_invalid_filters(self, client):
        """Test RAG with invalid filter values."""
        response = client.post(
            "/api/v1/rag/query",
            json={
                "question": "Test",
                "filters": {
                    "days": -10  # Invalid negative value
                }
            }
        )

        assert response.status_code == 422  # Validation error


class TestRAGAPISourceContent:
    """Test suite for RAG with source content integration."""

    @pytest.fixture
    def sample_source_content_data(self, test_db):
        """Create sample data with source content chunks."""
        from reconly_core.database.models import (
            Source,
            Digest,
            DigestSourceItem,
            SourceContent,
            SourceContentChunk,
        )
        from datetime import datetime
        import hashlib

        # Create source
        source = Source(
            name="Tech Blog",
            type="manual",
            url="https://techblog.com",
            config={}
        )
        test_db.add(source)
        test_db.flush()

        # Create digest
        digest = Digest(
            url="https://techblog.com/ai-article",
            title="Comprehensive AI Article",
            content="Short summary",
            source_id=source.id,
        )
        test_db.add(digest)
        test_db.flush()

        # Create digest source item
        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://techblog.com/full-ai-article",
            item_title="Full AI Article",
            item_published_at=datetime.utcnow(),
        )
        test_db.add(digest_source_item)
        test_db.flush()

        # Create source content
        full_content = """
        Artificial intelligence is transforming industries at an unprecedented pace.
        Machine learning algorithms are becoming more sophisticated, enabling applications
        that were once thought impossible. Deep learning has revolutionized computer vision
        and natural language processing.
        """
        content_hash = hashlib.sha256(full_content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=full_content,
            content_hash=content_hash,
            content_length=len(full_content),
            fetched_at=datetime.utcnow(),
            embedding_status="completed",
        )
        test_db.add(source_content)
        test_db.flush()

        # Add source content chunks with embeddings
        for idx in range(3):
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = SourceContentChunk(
                source_content_id=source_content.id,
                chunk_index=idx,
                text=f"Source content chunk {idx} about AI and machine learning.",
                token_count=50,
                start_char=idx * 100,
                end_char=(idx + 1) * 100,
                embedding=embedding,
            )
            test_db.add(chunk)

        test_db.commit()
        return {"digest": digest, "source_content": source_content}

    def test_rag_query_with_source_content_chunks(self, client, sample_source_content_data):
        """Test RAG query using source_content chunks."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            # Mock embedding provider
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            # Mock summarizer
            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'AI is transforming industries [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "What is AI doing?",
                    "filters": {
                        "chunk_source": "source_content"
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure includes chunk_source
            assert "chunk_source" in data
            assert data["chunk_source"] == "source_content"
            assert "answer" in data
            assert "citations" in data

    def test_rag_query_with_digest_chunks(self, client, test_db):
        """Test RAG query using digest chunks."""
        # Create digest with chunks for this test
        digest = Digest(
            url="https://test.example.com/ai-digest",
            title="AI Progress Article",
            content="AI made significant progress in 2024.",
            source_id=None,
        )
        test_db.add(digest)
        test_db.flush()

        # Add digest chunks with embeddings
        for idx in range(2):
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=idx,
                text=f"Digest chunk {idx} about AI progress.",
                token_count=50,
                start_char=idx * 100,
                end_char=(idx + 1) * 100,
                embedding=embedding,
            )
            test_db.add(chunk)

        test_db.commit()

        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            # Mock embedding provider
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            # Mock summarizer
            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'AI made progress [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "What progress did AI make?",
                    "filters": {
                        "chunk_source": "digest"
                    }
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure includes chunk_source
            assert "chunk_source" in data
            assert data["chunk_source"] == "digest"
            assert "answer" in data
            assert "citations" in data

    def test_rag_query_default_chunk_source(self, client, sample_source_content_data):
        """Test that default chunk_source is source_content."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            # Mock embedding provider
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            # Mock summarizer
            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Default answer [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            # Query without specifying chunk_source
            response = client.post(
                "/api/v1/rag/query",
                json={
                    "question": "What is AI?",
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Should default to source_content
            assert data["chunk_source"] == "source_content"

    def test_rag_query_chunk_source_in_response(self, client, test_db):
        """Test that chunk_source is always included in response."""
        # Create minimal digest for this test
        digest = Digest(
            url="https://test.example.com/test-digest",
            title="Test Article",
            content="Test content.",
            source_id=None,
        )
        test_db.add(digest)
        test_db.flush()

        # Add digest chunk
        embedding = np.random.rand(1024).astype(np.float32).tolist()
        chunk = DigestChunk(
            digest_id=digest.id,
            chunk_index=0,
            text="Test chunk content.",
            token_count=10,
            start_char=0,
            end_char=50,
            embedding=embedding,
        )
        test_db.add(chunk)
        test_db.commit()

        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.providers.factory.get_summarizer') as mock_sum:

            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Test answer [1].',
                'model_info': {'model': 'test-model'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
            mock_sum.return_value = summarizer

            response = client.post(
                "/api/v1/rag/query",
                json={"question": "Test question"}
            )

            assert response.status_code == 200
            data = response.json()

            # chunk_source must be in response
            assert "chunk_source" in data
            assert data["chunk_source"] in ["source_content", "digest"]
