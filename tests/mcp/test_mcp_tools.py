"""Unit tests for MCP tool handlers."""
import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from reconly_mcp.tools import (
    ToolContext,
    EmbeddingServiceUnavailable,
    handle_semantic_search,
    handle_rag_query,
    handle_get_related_digests,
)
from reconly_core.database.models import Digest, DigestChunk, DigestRelationship, Source


class TestToolContext:
    """Test suite for ToolContext."""

    @pytest.fixture
    def context(self, db_session):
        """Return a ToolContext instance."""
        return ToolContext(db=db_session)

    def test_initialization(self, db_session):
        """Test ToolContext initialization."""
        ctx = ToolContext(db=db_session)

        assert ctx.db == db_session
        assert ctx._embedding_provider is None
        assert ctx._search_service is None
        assert ctx._rag_service is None
        assert ctx._graph_service is None

    def test_get_embedding_provider(self, context):
        """Test getting embedding provider."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_get:
            mock_provider = Mock()
            mock_get.return_value = mock_provider

            provider = context.get_embedding_provider()

            assert provider == mock_provider
            # Should cache the provider
            assert context._embedding_provider == mock_provider

    def test_get_embedding_provider_failure(self, context):
        """Test getting embedding provider when it fails."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_get:
            mock_get.side_effect = RuntimeError("Provider error")

            with pytest.raises(EmbeddingServiceUnavailable):
                context.get_embedding_provider()

    def test_get_search_service(self, context):
        """Test getting search service."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_get:
            mock_provider = Mock()
            mock_get.return_value = mock_provider

            service = context.get_search_service()

            assert service is not None
            # Should cache the service
            assert context._search_service == service

    def test_get_rag_service(self, context):
        """Test getting RAG service."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.summarizers.get_summarizer') as mock_sum:

            mock_provider = Mock()
            mock_emb.return_value = mock_provider

            mock_summarizer = Mock()
            mock_sum.return_value = mock_summarizer

            service = context.get_rag_service()

            assert service is not None
            # Should cache the service
            assert context._rag_service == service

    def test_get_rag_service_summarizer_failure(self, context):
        """Test getting RAG service when summarizer fails."""
        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.summarizers.get_summarizer') as mock_sum:

            mock_provider = Mock()
            mock_emb.return_value = mock_provider

            mock_sum.side_effect = RuntimeError("Summarizer error")

            with pytest.raises(EmbeddingServiceUnavailable):
                context.get_rag_service()

    def test_get_graph_service(self, context):
        """Test getting graph service."""
        service = context.get_graph_service()

        assert service is not None
        # Should cache the service
        assert context._graph_service == service


class TestSemanticSearchHandler:
    """Test suite for semantic_search handler."""

    @pytest.fixture
    def context_with_data(self, db_session):
        """Create context with test data."""
        source = Source(name="Test", type="manual", data={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="Test Digest", content="Test content", source_id=source.id)
        db_session.add(digest)
        db_session.flush()

        # Use list format for embeddings (pgvector format)
        embedding = np.random.rand(1024).astype(np.float32).tolist()
        chunk = DigestChunk(
            digest_id=digest.id,
            chunk_index=0,
            text="Test chunk",
            token_count=50,
            start_char=0,
            end_char=100,
            embedding=embedding,
        )
        db_session.add(chunk)
        db_session.commit()

        return ToolContext(db=db_session)

    @pytest.mark.asyncio
    async def test_semantic_search_success(self, context_with_data):
        """Test successful semantic search."""
        with patch.object(context_with_data, 'get_search_service') as mock_get:
            # Mock search service
            search_service = Mock()
            search_service.search = AsyncMock(return_value=Mock(
                results=[],
                took_ms=10.0,
                mode='hybrid',
            ))
            mock_get.return_value = search_service

            result = await handle_semantic_search(
                ctx=context_with_data,
                query="test query",
                limit=10,
            )

            # Should return formatted string
            assert isinstance(result, str)
            search_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search_with_filters(self, context_with_data):
        """Test semantic search with filters."""
        with patch.object(context_with_data, 'get_search_service') as mock_get:
            search_service = Mock()
            search_service.search = AsyncMock(return_value=Mock(
                results=[],
                took_ms=10.0,
                mode='hybrid',
            ))
            mock_get.return_value = search_service

            result = await handle_semantic_search(
                ctx=context_with_data,
                query="test",
                limit=5,
                feed_id=1,
                days=30,
            )

            assert isinstance(result, str)

            # Verify filters were passed
            call_kwargs = search_service.search.call_args[1]
            assert call_kwargs['feed_id'] == 1
            assert call_kwargs['days'] == 30

    @pytest.mark.asyncio
    async def test_semantic_search_provider_unavailable(self, db_session):
        """Test semantic search when provider is unavailable."""
        ctx = ToolContext(db=db_session)

        with patch.object(ctx, 'get_search_service') as mock_get:
            mock_get.side_effect = EmbeddingServiceUnavailable("Provider unavailable")

            result = await handle_semantic_search(ctx, "test")

            # Should return error message
            assert isinstance(result, str)
            assert "Embedding Service Unavailable" in result

    @pytest.mark.asyncio
    async def test_semantic_search_error_handling(self, context_with_data):
        """Test semantic search error handling."""
        with patch.object(context_with_data, 'get_search_service') as mock_get:
            search_service = Mock()
            search_service.search = AsyncMock(side_effect=RuntimeError("Search failed"))
            mock_get.return_value = search_service

            result = await handle_semantic_search(context_with_data, "test")

            # Should return error message
            assert isinstance(result, str)
            assert "error" in result.lower() or "failed" in result.lower()


class TestRAGQueryHandler:
    """Test suite for rag_query handler."""

    @pytest.fixture
    def context_with_data(self, db_session):
        """Create context with test data."""
        source = Source(name="Test", type="manual", data={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="Test Digest", content="Test content", source_id=source.id)
        db_session.add(digest)
        db_session.flush()

        # Use list format for embeddings (pgvector format)
        embedding = np.random.rand(1024).astype(np.float32).tolist()
        chunk = DigestChunk(
            digest_id=digest.id,
            chunk_index=0,
            text="Test chunk",
            token_count=50,
            start_char=0,
            end_char=100,
            embedding=embedding,
        )
        db_session.add(chunk)
        db_session.commit()

        return ToolContext(db=db_session)

    @pytest.mark.asyncio
    async def test_rag_query_success(self, context_with_data):
        """Test successful RAG query."""
        from reconly_core.rag.rag_service import RAGResult
        from reconly_core.rag.citations import Citation

        with patch.object(context_with_data, 'get_rag_service') as mock_get:
            # Mock RAG service
            rag_service = Mock()
            rag_service.query = AsyncMock(return_value=RAGResult(
                answer="Test answer [1]",
                citations=[
                    Citation(
                        id=1,
                        digest_id=1,
                        digest_title="Title",
                        text="text",
                        url=None,
                    )
                ],
                chunks_retrieved=1,
                grounded=True,
                model_used="test-model",
            ))
            mock_get.return_value = rag_service

            result = await handle_rag_query(
                ctx=context_with_data,
                question="What is AI?",
            )

            # Should return formatted string
            assert isinstance(result, str)
            rag_service.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_query_with_filters(self, context_with_data):
        """Test RAG query with filters."""
        from reconly_core.rag.rag_service import RAGResult

        with patch.object(context_with_data, 'get_rag_service') as mock_get:
            rag_service = Mock()
            rag_service.query = AsyncMock(return_value=RAGResult(
                answer="Test",
                citations=[],
                chunks_retrieved=0,
                grounded=True,
                model_used="test",
            ))
            mock_get.return_value = rag_service

            result = await handle_rag_query(
                ctx=context_with_data,
                question="test",
                feed_id=1,
                days=30,
            )

            assert isinstance(result, str)

            # Verify query was called with filters
            rag_service.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_query_provider_unavailable(self, db_session):
        """Test RAG query when provider is unavailable."""
        ctx = ToolContext(db=db_session)

        with patch.object(ctx, 'get_rag_service') as mock_get:
            mock_get.side_effect = EmbeddingServiceUnavailable("Provider unavailable")

            result = await handle_rag_query(ctx, "test question")

            # Should return error message
            assert isinstance(result, str)
            assert "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_rag_query_error_handling(self, context_with_data):
        """Test RAG query error handling."""
        with patch.object(context_with_data, 'get_rag_service') as mock_get:
            rag_service = Mock()
            rag_service.query = AsyncMock(side_effect=RuntimeError("Query failed"))
            mock_get.return_value = rag_service

            result = await handle_rag_query(context_with_data, "test")

            # Should return error message
            assert isinstance(result, str)
            assert "error" in result.lower() or "failed" in result.lower()


class TestGetRelatedDigestsHandler:
    """Test suite for get_related_digests handler."""

    @pytest.fixture
    def context_with_graph(self, db_session):
        """Create context with graph data."""
        source = Source(name="Test", type="manual", data={})
        db_session.add(source)
        db_session.flush()

        # Create digests
        digest1 = Digest(title="Digest 1", content="Content 1", source_id=source.id)
        digest2 = Digest(title="Digest 2", content="Content 2", source_id=source.id)
        db_session.add_all([digest1, digest2])
        db_session.flush()

        # Create relationship
        rel = DigestRelationship(
            source_digest_id=digest1.id,
            target_digest_id=digest2.id,
            relationship_type="semantic",
            score=0.9,
        )
        db_session.add(rel)
        db_session.commit()

        return ToolContext(db=db_session), digest1

    @pytest.mark.asyncio
    async def test_get_related_digests_success(self, context_with_graph):
        """Test successful get related digests."""
        ctx, digest = context_with_graph

        result = await handle_get_related_digests(
            ctx=ctx,
            digest_id=digest.id,
            limit=10,
        )

        # Should return formatted string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_related_digests_with_filters(self, context_with_graph):
        """Test get related digests with filters."""
        ctx, digest = context_with_graph

        result = await handle_get_related_digests(
            ctx=ctx,
            digest_id=digest.id,
            limit=5,
            min_score=0.8,
        )

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_related_digests_nonexistent(self, db_session):
        """Test get related digests for non-existent digest."""
        ctx = ToolContext(db=db_session)

        result = await handle_get_related_digests(
            ctx=ctx,
            digest_id=99999,
        )

        # Should return error or empty result
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_related_digests_error_handling(self, db_session):
        """Test get related digests error handling."""
        ctx = ToolContext(db=db_session)

        with patch.object(ctx, 'get_graph_service') as mock_get:
            graph_service = Mock()
            graph_service.get_graph_data = Mock(side_effect=RuntimeError("Graph error"))
            mock_get.return_value = graph_service

            result = await handle_get_related_digests(ctx, 1)

            # Should return error message
            assert isinstance(result, str)
            assert "error" in result.lower() or "failed" in result.lower()


class TestMCPToolIntegration:
    """Integration tests for MCP tools."""

    @pytest.fixture
    def full_context(self, db_session):
        """Create fully populated test context."""
        # Create source
        source = Source(name="Tech News", type="manual", data={"url": "https://tech.com"})
        db_session.add(source)
        db_session.flush()

        # Create digests
        digest1 = Digest(
            title="AI Advances",
            content="AI is making progress",
            source_id=source.id,
        )
        digest2 = Digest(
            title="ML Techniques",
            content="Machine learning techniques",
            source_id=source.id,
        )
        db_session.add_all([digest1, digest2])
        db_session.flush()

        # Add chunks with embeddings (pgvector format - list of floats)
        for digest in [digest1, digest2]:
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=0,
                text=f"Chunk for {digest.title}",
                token_count=50,
                start_char=0,
                end_char=100,
                embedding=embedding,
            )
            db_session.add(chunk)

        # Add relationship
        rel = DigestRelationship(
            source_digest_id=digest1.id,
            target_digest_id=digest2.id,
            relationship_type="semantic",
            score=0.85,
        )
        db_session.add(rel)
        db_session.commit()

        return ToolContext(db=db_session), digest1

    @pytest.mark.asyncio
    async def test_full_workflow(self, full_context):
        """Test full MCP tool workflow."""
        ctx, digest = full_context

        with patch('reconly_core.rag.get_embedding_provider') as mock_emb, \
             patch('reconly_core.summarizers.get_summarizer') as mock_sum:

            # Setup mocks
            provider = Mock()
            provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_emb.return_value = provider

            summarizer = Mock()
            summarizer.summarize = Mock(return_value={
                'summary': 'Test answer [1]',
                'model_info': {'model': 'test'},
            })
            summarizer.get_model_info = Mock(return_value={'model': 'test'})
            mock_sum.return_value = summarizer

            # 1. Search
            search_result = await handle_semantic_search(ctx, "AI progress")
            assert isinstance(search_result, str)

            # 2. RAG query
            rag_result = await handle_rag_query(ctx, "What is AI doing?")
            assert isinstance(rag_result, str)

            # 3. Get related digests
            related_result = await handle_get_related_digests(ctx, digest.id)
            assert isinstance(related_result, str)
