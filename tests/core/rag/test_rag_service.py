"""Tests for RAGService."""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from reconly_core.rag.rag_service import (
    RAGService,
    RAGResult,
    RAGFilters,
    RAG_SYSTEM_PROMPT,
)
from reconly_core.rag.search.hybrid import HybridSearchResponse, HybridSearchResult, ChunkMatch
from reconly_core.rag.citations import Citation


class TestRAGService:
    """Test suite for RAGService."""

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
    def mock_summarizer(self):
        """Return mock summarizer."""
        summarizer = Mock()
        summarizer.summarize = Mock(return_value={
            'summary': 'This is a test answer with citations [1] and [2].',
            'model_info': {'model': 'test-model'},
        })
        summarizer.get_model_info = Mock(return_value={'model': 'test-model'})
        return summarizer

    @pytest.fixture
    def rag_service(self, db_session, mock_embedding_provider, mock_summarizer):
        """Return configured RAG service."""
        return RAGService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            summarizer=mock_summarizer,
        )

    def test_initialization(self, db_session, mock_embedding_provider, mock_summarizer):
        """Test service initialization."""
        service = RAGService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            summarizer=mock_summarizer,
            max_chunks=15,
            search_mode='vector',
        )

        assert service.db == db_session
        assert service.embedding_provider == mock_embedding_provider
        assert service.summarizer == mock_summarizer
        assert service.max_chunks == 15
        assert service.search_mode == 'vector'
        assert service.system_prompt == RAG_SYSTEM_PROMPT

    def test_initialization_custom_prompt(self, db_session, mock_embedding_provider, mock_summarizer):
        """Test initialization with custom system prompt."""
        custom_prompt = "Custom system prompt"
        service = RAGService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            summarizer=mock_summarizer,
            system_prompt=custom_prompt,
        )

        assert service.system_prompt == custom_prompt

    @pytest.mark.asyncio
    async def test_query_with_results(self, rag_service, db_session):
        """Test RAG query with search results."""
        from reconly_core.database.models import Digest, Source

        # Create test digest
        source = Source(name="Test", type="manual", url="https://example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="AI Article", url="https://example.com/ai-article", content="Content about AI", source_id=source.id)
        db_session.add(digest)
        db_session.commit()

        # Mock search response
        mock_search_response = HybridSearchResponse(
            results=[
                HybridSearchResult(
                    digest_id=digest.id,
                    title="AI Article",
                    matched_chunks=[
                        ChunkMatch("AI is transforming industries", 0.9, 0)
                    ],
                    score=0.9,
                    sources=['vector'],
                )
            ],
            took_ms=50.0,
            mode='hybrid',
            vector_results_count=1,
            fts_results_count=0,
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response):
            result = await rag_service.query("What is AI doing?")

            assert isinstance(result, RAGResult)
            assert result.answer != ""
            assert result.chunks_retrieved > 0
            assert result.model_used == 'test-model'
            assert result.search_took_ms > 0
            assert result.generation_took_ms >= 0
            assert result.total_took_ms > 0

    @pytest.mark.asyncio
    async def test_query_no_results(self, rag_service):
        """Test RAG query with no search results."""
        mock_search_response = HybridSearchResponse(
            results=[],
            took_ms=10.0,
            mode='hybrid',
            vector_results_count=0,
            fts_results_count=0,
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response):
            result = await rag_service.query("Unknown topic")

            assert "cannot find" in result.answer.lower()
            assert len(result.citations) == 0
            assert result.chunks_retrieved == 0
            assert result.grounded is True  # Admits no sources

    @pytest.mark.asyncio
    async def test_query_with_filters(self, rag_service):
        """Test RAG query with filters."""
        filters = RAGFilters(feed_id=1, source_id=2, days=30)

        mock_search_response = HybridSearchResponse(
            results=[],
            took_ms=10.0,
            mode='hybrid',
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response) as mock_search:
            await rag_service.query("test question", filters=filters)

            # Verify filters were passed to search
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs['feed_id'] == 1
            assert call_kwargs['source_id'] == 2
            assert call_kwargs['days'] == 30

    @pytest.mark.asyncio
    async def test_query_custom_max_chunks(self, rag_service):
        """Test RAG query with custom max_chunks."""
        mock_search_response = HybridSearchResponse(
            results=[],
            took_ms=10.0,
            mode='hybrid',
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response) as mock_search:
            await rag_service.query("test", max_chunks=5)

            # Verify limit was adjusted (max_chunks * 2)
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs['limit'] == 10

    @pytest.mark.asyncio
    async def test_query_without_answer(self, rag_service, db_session):
        """Test RAG query without generating answer."""
        from reconly_core.database.models import Digest, Source

        # Create test data
        source = Source(name="Test", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="Test", url="https://test.example.com/test", content="Content", source_id=source.id)
        db_session.add(digest)
        db_session.commit()

        mock_search_response = HybridSearchResponse(
            results=[
                HybridSearchResult(
                    digest_id=digest.id,
                    title="Test",
                    matched_chunks=[ChunkMatch("text", 0.9, 0)],
                    score=0.9,
                    sources=['vector'],
                )
            ],
            took_ms=10.0,
            mode='hybrid',
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response):
            result = await rag_service.query("test", include_answer=False)

            assert result.answer == ""
            assert len(result.citations) > 0
            assert result.generation_took_ms == 0

    @pytest.mark.asyncio
    async def test_search_only(self, rag_service, db_session):
        """Test search_only convenience method."""
        from reconly_core.database.models import Digest, Source

        source = Source(name="Test", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(title="Test", url="https://test.example.com/test-search", content="Content", source_id=source.id)
        db_session.add(digest)
        db_session.commit()

        mock_search_response = HybridSearchResponse(
            results=[
                HybridSearchResult(
                    digest_id=digest.id,
                    title="Test",
                    matched_chunks=[ChunkMatch("text", 0.9, 0)],
                    score=0.9,
                    sources=['vector'],
                )
            ],
            took_ms=10.0,
            mode='hybrid',
        )

        with patch.object(rag_service.search_service, 'search', return_value=mock_search_response):
            result = await rag_service.search_only("test question")

            assert result.answer == ""
            assert len(result.citations) > 0

    def test_verify_grounding_with_citations(self, rag_service):
        """Test grounding verification with valid citations."""
        from reconly_core.rag.citations import ParsedResponse, CitationContext

        answer = "This is an answer with citations [1] and [2]."
        parsed = ParsedResponse(
            answer=answer,
            cited_ids={1, 2},
            uncited_claims=[],
        )
        context = CitationContext(
            citations=[
                Citation(id=1, digest_id=1, digest_title="Title 1", chunk_text="text1", chunk_index=0, relevance_score=0.9),
                Citation(id=2, digest_id=2, digest_title="Title 2", chunk_text="text2", chunk_index=0, relevance_score=0.8),
            ],
            formatted_context="",
            total_chunks=2,
        )

        grounded = rag_service._verify_grounding(answer, parsed, context)
        assert grounded is True

    def test_verify_grounding_no_citations(self, rag_service):
        """Test grounding verification with no citations."""
        from reconly_core.rag.citations import ParsedResponse, CitationContext

        answer = "This is an answer without citations."
        parsed = ParsedResponse(
            answer=answer,
            cited_ids=set(),
            uncited_claims=["This is an answer without citations"],
        )
        context = CitationContext(citations=[], formatted_context="", total_chunks=0)

        grounded = rag_service._verify_grounding(answer, parsed, context)
        assert grounded is False

    def test_verify_grounding_invalid_citations(self, rag_service):
        """Test grounding verification with invalid citation references."""
        from reconly_core.rag.citations import ParsedResponse, CitationContext

        answer = "Answer with invalid citation [99]."
        parsed = ParsedResponse(
            answer=answer,
            cited_ids={99},
            uncited_claims=[],
        )
        context = CitationContext(
            citations=[
                Citation(id=1, digest_id=1, digest_title="Title", chunk_text="text", chunk_index=0, relevance_score=0.9),
            ],
            formatted_context="",
            total_chunks=1,
        )

        grounded = rag_service._verify_grounding(answer, parsed, context)
        assert grounded is False

    def test_verify_grounding_no_info_response(self, rag_service):
        """Test grounding verification for 'no information' responses."""
        from reconly_core.rag.citations import ParsedResponse, CitationContext

        answer = "I cannot find information about this in the available sources."
        parsed = ParsedResponse(
            answer=answer,
            cited_ids=set(),
            uncited_claims=[],
        )
        context = CitationContext(citations=[], formatted_context="", total_chunks=0)

        grounded = rag_service._verify_grounding(answer, parsed, context)
        assert grounded is True  # "No info" responses are considered grounded


class TestRAGFilters:
    """Test RAGFilters dataclass."""

    def test_filters_creation(self):
        """Test creating RAGFilters."""
        filters = RAGFilters(
            feed_id=1,
            source_id=2,
            days=30,
        )

        assert filters.feed_id == 1
        assert filters.source_id == 2
        assert filters.days == 30

    def test_filters_defaults(self):
        """Test RAGFilters default values."""
        filters = RAGFilters()

        assert filters.feed_id is None
        assert filters.source_id is None
        assert filters.days is None


class TestRAGResult:
    """Test RAGResult dataclass."""

    def test_result_creation(self):
        """Test creating a RAGResult."""
        citations = [
            Citation(id=1, digest_id=1, digest_title="Title", chunk_text="text", chunk_index=0, relevance_score=0.9)
        ]

        result = RAGResult(
            answer="Test answer [1]",
            citations=citations,
            chunks_retrieved=5,
            grounded=True,
            model_used="test-model",
            search_took_ms=100.0,
            generation_took_ms=200.0,
            total_took_ms=300.0,
        )

        assert result.answer == "Test answer [1]"
        assert len(result.citations) == 1
        assert result.chunks_retrieved == 5
        assert result.grounded is True
        assert result.model_used == "test-model"
        assert result.search_took_ms == 100.0
        assert result.generation_took_ms == 200.0
        assert result.total_took_ms == 300.0


class TestRAGServiceIntegration:
    """Integration tests for RAGService."""

    @pytest.mark.asyncio
    async def test_full_rag_flow(self, db_session):
        """Test complete RAG flow from query to answer."""
        from reconly_core.database.models import Digest, Source

        # Setup mocks
        mock_provider = Mock()
        mock_provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
        mock_provider.get_dimension = Mock(return_value=1024)
        mock_provider.get_model_info = Mock(return_value={
            'provider': 'test',
            'model': 'test-model',
        })

        mock_summarizer = Mock()
        mock_summarizer.summarize = Mock(return_value={
            'summary': 'AI is revolutionizing technology [1].',
            'model_info': {'model': 'gpt-test'},
        })
        mock_summarizer.get_model_info = Mock(return_value={'model': 'gpt-test'})

        # Create test data
        source = Source(name="Tech News", type="manual", url="https://tech.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            title="AI Revolution",
            url="https://tech.com/ai-revolution",
            content="Artificial intelligence is transforming the world.",
            source_id=source.id,
        )
        db_session.add(digest)
        db_session.commit()

        # Create service
        service = RAGService(db_session, mock_provider, mock_summarizer)

        # Mock search response
        mock_search_response = HybridSearchResponse(
            results=[
                HybridSearchResult(
                    digest_id=digest.id,
                    title=digest.title,
                    matched_chunks=[
                        ChunkMatch("AI is transforming technology", 0.95, 0)
                    ],
                    score=0.95,
                    sources=['vector'],
                )
            ],
            took_ms=25.0,
            mode='hybrid',
            vector_results_count=1,
            fts_results_count=0,
        )

        with patch.object(service.search_service, 'search', return_value=mock_search_response):
            result = await service.query("What is happening with AI?")

            # Verify result structure
            assert isinstance(result, RAGResult)
            assert "AI" in result.answer or "[1]" in result.answer
            assert len(result.citations) > 0
            assert result.chunks_retrieved > 0
            assert result.grounded is True
            assert result.model_used == 'gpt-test'
            assert result.total_took_ms > 0
