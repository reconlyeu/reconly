"""RAG (Retrieval-Augmented Generation) Service.

This module provides the main RAG service that retrieves relevant
chunks using hybrid search and generates answers with citations.
"""
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from reconly_core.rag.search.hybrid import HybridSearchService, SearchMode
from reconly_core.rag.citations import (
    Citation,
    CitationContext,
    ParsedResponse,
    format_citations_for_prompt,
    parse_citations_from_response,
    enrich_citations_with_urls,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.embeddings.base import EmbeddingProvider
    from reconly_core.summarizers.base import BaseSummarizer

logger = logging.getLogger(__name__)


# RAG System Prompt
RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided source documents.

IMPORTANT INSTRUCTIONS:
1. ONLY use information from the provided sources to answer the question.
2. Cite your sources using [1], [2], etc. for each piece of information.
3. If the answer cannot be found in the provided sources, say "I cannot find information about this in the available sources."
4. Do NOT make up or infer information that is not explicitly stated in the sources.
5. Be concise and direct in your answers.

Your response should be well-structured and easy to read."""

RAG_USER_PROMPT_TEMPLATE = """Based on the following sources, please answer this question:

**Question:** {question}

**Sources:**
{sources}

Please provide a clear, concise answer with citations [1], [2], etc."""


@dataclass
class RAGFilters:
    """Filters for RAG queries.

    Attributes:
        feed_id: Filter by feed ID
        source_id: Filter by source ID
        days: Filter for digests created within N days
    """
    feed_id: int | None = None
    source_id: int | None = None
    days: int | None = None


@dataclass
class RAGResult:
    """Result from a RAG query.

    Attributes:
        answer: The generated answer with inline citations
        citations: List of source citations
        chunks_retrieved: Number of chunks that were retrieved
        grounded: Whether the response is grounded in sources
        model_used: Name of the LLM model used
        search_took_ms: Time taken for the search
        generation_took_ms: Time taken for answer generation
        total_took_ms: Total time for the RAG query
    """
    answer: str
    citations: list[Citation]
    chunks_retrieved: int
    grounded: bool
    model_used: str
    search_took_ms: float = 0.0
    generation_took_ms: float = 0.0
    total_took_ms: float = 0.0


class RAGService:
    """Service for Retrieval-Augmented Generation.

    Combines hybrid search with LLM generation to answer questions
    based on indexed digest content.

    Example:
        >>> from reconly_core.rag import RAGService, get_embedding_provider
        >>> from reconly_core.summarizers import get_summarizer
        >>>
        >>> provider = get_embedding_provider(db=db)
        >>> summarizer = get_summarizer(db=db, enable_fallback=False)
        >>> rag = RAGService(db, provider, summarizer)
        >>>
        >>> result = await rag.query("What are the latest trends in AI?")
        >>> print(result.answer)
        >>> for citation in result.citations:
        ...     print(f"[{citation.id}] {citation.digest_title}")
    """

    def __init__(
        self,
        db: "Session",
        embedding_provider: "EmbeddingProvider",
        summarizer: "BaseSummarizer",
        system_prompt: str | None = None,
        max_chunks: int = 10,
        search_mode: SearchMode = 'hybrid',
    ):
        """Initialize the RAG service.

        Args:
            db: Database session
            embedding_provider: Provider for generating query embeddings
            summarizer: LLM summarizer for generating answers
            system_prompt: Custom system prompt (uses default if None)
            max_chunks: Maximum number of chunks to retrieve
            search_mode: Search mode ('hybrid', 'vector', 'fts')
        """
        self.db = db
        self.embedding_provider = embedding_provider
        self.summarizer = summarizer
        self.system_prompt = system_prompt or RAG_SYSTEM_PROMPT
        self.max_chunks = max_chunks
        self.search_mode: SearchMode = search_mode

        # Initialize search service
        self.search_service = HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
        )

    async def query(
        self,
        question: str,
        filters: RAGFilters | None = None,
        max_chunks: int | None = None,
        include_answer: bool = True,
    ) -> RAGResult:
        """Query the knowledge base and generate an answer.

        Args:
            question: The question to answer
            filters: Optional filters for the search
            max_chunks: Override default max chunks
            include_answer: If False, only return chunks without generating answer

        Returns:
            RAGResult with answer, citations, and metadata
        """
        start_time = time.time()
        filters = filters or RAGFilters()
        effective_max_chunks = max_chunks or self.max_chunks

        # Step 1: Search for relevant chunks
        search_start = time.time()
        search_response = await self.search_service.search(
            query=question,
            limit=effective_max_chunks * 2,  # Get more for filtering
            feed_id=filters.feed_id,
            source_id=filters.source_id,
            days=filters.days,
            mode=self.search_mode,
        )
        search_took_ms = (time.time() - search_start) * 1000

        logger.debug(
            f"RAG search completed in {search_took_ms:.2f}ms, "
            f"found {len(search_response.results)} results"
        )

        # Step 2: Format citations for prompt
        citation_context = format_citations_for_prompt(
            results=search_response.results,
            max_total_chunks=effective_max_chunks,
        )

        # Enrich citations with URLs
        citation_context.citations = enrich_citations_with_urls(
            citation_context.citations,
            self.db,
        )

        # If no sources found, return early
        if not citation_context.citations:
            return RAGResult(
                answer="I cannot find any relevant information in the available sources to answer this question.",
                citations=[],
                chunks_retrieved=0,
                grounded=True,  # Technically grounded since it admits no sources
                model_used=self.summarizer.get_model_info().get('model', 'unknown'),
                search_took_ms=search_took_ms,
                generation_took_ms=0.0,
                total_took_ms=(time.time() - start_time) * 1000,
            )

        # If not generating answer, return just the chunks
        if not include_answer:
            return RAGResult(
                answer="",
                citations=citation_context.citations,
                chunks_retrieved=citation_context.total_chunks,
                grounded=True,
                model_used="",
                search_took_ms=search_took_ms,
                generation_took_ms=0.0,
                total_took_ms=(time.time() - start_time) * 1000,
            )

        # Step 3: Generate answer with citations
        generation_start = time.time()

        user_prompt = RAG_USER_PROMPT_TEMPLATE.format(
            question=question,
            sources=citation_context.formatted_context,
        )

        try:
            # Use the summarizer to generate the answer
            result = self.summarizer.summarize(
                content_data={
                    'content': user_prompt,
                    'title': question,
                    'source_type': 'rag_query',
                },
                language='en',
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
            )

            answer = result.get('summary', '')
            model_info = result.get('model_info', {})
            if isinstance(model_info, dict):
                model_used = model_info.get('model', 'unknown')
            else:
                summarizer_info = self.summarizer.get_model_info()
                model_used = summarizer_info.get('model', 'unknown') if isinstance(summarizer_info, dict) else 'unknown'

        except Exception as e:
            logger.error(f"Failed to generate RAG answer: {e}")
            raise

        generation_took_ms = (time.time() - generation_start) * 1000

        # Step 4: Verify grounding
        parsed = parse_citations_from_response(answer)
        grounded = self._verify_grounding(answer, parsed, citation_context)

        total_took_ms = (time.time() - start_time) * 1000

        logger.debug(
            f"RAG query completed in {total_took_ms:.2f}ms "
            f"(search: {search_took_ms:.2f}ms, generation: {generation_took_ms:.2f}ms)"
        )

        return RAGResult(
            answer=answer,
            citations=citation_context.citations,
            chunks_retrieved=citation_context.total_chunks,
            grounded=grounded,
            model_used=model_used,
            search_took_ms=search_took_ms,
            generation_took_ms=generation_took_ms,
            total_took_ms=total_took_ms,
        )

    def _verify_grounding(
        self,
        answer: str,
        parsed: ParsedResponse,
        context: CitationContext,
    ) -> bool:
        """Verify if the response is properly grounded in sources.

        A response is considered grounded if:
        1. It contains at least one citation reference
        2. All citation references are valid (exist in the sources)
        3. It doesn't have obvious uncited factual claims

        Args:
            answer: The generated answer
            parsed: Parsed response with citation info
            context: The citation context used for generation

        Returns:
            True if response is grounded, False otherwise
        """
        # Empty or "no information" responses are considered grounded
        no_info_phrases = [
            "cannot find information",
            "no relevant information",
            "not found in the sources",
            "not in the available sources",
        ]
        answer_lower = answer.lower()
        for phrase in no_info_phrases:
            if phrase in answer_lower:
                return True

        # Must have at least one citation
        if not parsed.cited_ids:
            logger.warning("RAG response has no citations")
            return False

        # All cited IDs must be valid
        valid_ids = {c.id for c in context.citations}
        invalid_refs = parsed.cited_ids - valid_ids
        if invalid_refs:
            logger.warning(f"RAG response has invalid citation references: {invalid_refs}")
            return False

        # Check for suspicious uncited claims
        # Allow a few uncited sentences (opinions, transitions, etc.)
        if len(parsed.uncited_claims) > 2:
            logger.warning(
                f"RAG response may have uncited claims: {parsed.uncited_claims[:3]}"
            )

        return True

    async def search_only(
        self,
        question: str,
        filters: RAGFilters | None = None,
        max_chunks: int | None = None,
    ) -> RAGResult:
        """Search for relevant chunks without generating an answer.

        Useful for previewing what sources would be used.

        Args:
            question: The search query
            filters: Optional filters
            max_chunks: Maximum chunks to retrieve

        Returns:
            RAGResult with citations but no generated answer
        """
        return await self.query(
            question=question,
            filters=filters,
            max_chunks=max_chunks,
            include_answer=False,
        )
