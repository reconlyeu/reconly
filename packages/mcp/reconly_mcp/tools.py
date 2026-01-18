"""MCP tool handlers for Reconly knowledge base access.

This module contains the implementation of MCP tools that expose
Reconly's RAG capabilities to AI assistants.
"""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from reconly_mcp.formatting import (
    format_search_results,
    format_rag_response,
    format_related_digests,
    format_error,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EmbeddingServiceUnavailable(Exception):
    """Raised when the embedding service is not available."""


class DatabaseConnectionError(Exception):
    """Raised when the database connection fails."""


@dataclass
class ToolContext:
    """Context for tool execution.

    Holds database session and initialized services.
    """
    db: "Session"
    _embedding_provider: object | None = None
    _search_service: object | None = None
    _rag_service: object | None = None
    _graph_service: object | None = None

    def get_embedding_provider(self):
        """Get or create embedding provider."""
        if self._embedding_provider is None:
            from reconly_core.rag import get_embedding_provider

            try:
                self._embedding_provider = get_embedding_provider(db=self.db)
            except Exception as e:
                logger.error(f"Failed to initialize embedding provider: {e}")
                raise EmbeddingServiceUnavailable(
                    f"Could not initialize embedding service: {e}"
                ) from e

        return self._embedding_provider

    def get_search_service(self):
        """Get or create hybrid search service."""
        if self._search_service is None:
            from reconly_core.rag import HybridSearchService

            provider = self.get_embedding_provider()
            self._search_service = HybridSearchService(
                db=self.db,
                embedding_provider=provider,
            )

        return self._search_service

    def get_rag_service(self):
        """Get or create RAG service."""
        if self._rag_service is None:
            from reconly_core.rag import RAGService
            from reconly_core.providers import get_summarizer

            provider = self.get_embedding_provider()

            try:
                summarizer = get_summarizer(db=self.db, enable_fallback=False)
            except Exception as e:
                logger.error(f"Failed to initialize summarizer: {e}")
                raise EmbeddingServiceUnavailable(
                    f"Could not initialize LLM for RAG queries: {e}"
                ) from e

            self._rag_service = RAGService(
                db=self.db,
                embedding_provider=provider,
                summarizer=summarizer,
            )

        return self._rag_service

    def get_graph_service(self):
        """Get or create graph service."""
        if self._graph_service is None:
            from reconly_core.rag import GraphService

            # Graph service doesn't require embedding provider for queries
            self._graph_service = GraphService(
                db=self.db,
                embedding_provider=None,
            )

        return self._graph_service


async def handle_semantic_search(
    ctx: ToolContext,
    query: str,
    limit: int = 10,
    feed_id: int | None = None,
    days: int | None = None,
) -> str:
    """Handle semantic_search tool call.

    Searches the knowledge base using hybrid vector + full-text search.

    Args:
        ctx: Tool execution context
        query: Search query text
        limit: Maximum number of results (default 10)
        feed_id: Optional filter by feed ID
        days: Optional filter for digests within N days

    Returns:
        Formatted search results as string

    Raises:
        EmbeddingServiceUnavailable: If embedding service is not configured
    """
    try:
        search_service = ctx.get_search_service()
    except EmbeddingServiceUnavailable:
        return format_error(
            error_type="Embedding Service Unavailable",
            message="The embedding service is not configured or not running.",
            suggestion="Ensure Ollama is running with an embedding model, or configure an alternative embedding provider.",
        )

    try:
        response = await search_service.search(
            query=query,
            limit=limit,
            feed_id=feed_id,
            days=days,
            mode='hybrid',
        )

        logger.info(
            f"Semantic search completed: query='{query[:50]}...', "
            f"results={len(response.results)}, took={response.took_ms:.0f}ms"
        )

        return format_search_results(
            results=response.results,
            max_chunks_per_result=2,
            max_chunk_length=300,
        )

    except Exception as e:
        logger.exception(f"Semantic search failed: {e}")
        return format_error(
            error_type="Search Error",
            message=f"Failed to execute search: {str(e)}",
            suggestion="Check that the database contains indexed digests with embeddings.",
        )


async def handle_rag_query(
    ctx: ToolContext,
    question: str,
    max_chunks: int = 10,
    feed_id: int | None = None,
    days: int | None = None,
) -> str:
    """Handle rag_query tool call.

    Answers questions using RAG with citations from the knowledge base.

    Args:
        ctx: Tool execution context
        question: The question to answer
        max_chunks: Maximum chunks to retrieve for context (default 10)
        feed_id: Optional filter by feed ID
        days: Optional filter for digests within N days

    Returns:
        Formatted answer with citations as string

    Raises:
        EmbeddingServiceUnavailable: If embedding or LLM service is not available
    """
    try:
        rag_service = ctx.get_rag_service()
    except EmbeddingServiceUnavailable as e:
        return format_error(
            error_type="Service Unavailable",
            message=str(e),
            suggestion="Ensure embedding and LLM services are configured and running.",
        )

    try:
        from reconly_core.rag import RAGFilters

        filters = RAGFilters(
            feed_id=feed_id,
            days=days,
        )

        result = await rag_service.query(
            question=question,
            filters=filters,
            max_chunks=max_chunks,
        )

        logger.info(
            f"RAG query completed: question='{question[:50]}...', "
            f"chunks={result.chunks_retrieved}, grounded={result.grounded}, "
            f"took={result.total_took_ms:.0f}ms"
        )

        return format_rag_response(
            result=result,
            include_metadata=True,
        )

    except Exception as e:
        logger.exception(f"RAG query failed: {e}")
        return format_error(
            error_type="RAG Query Error",
            message=f"Failed to generate answer: {str(e)}",
            suggestion="Check that the LLM provider is configured and accessible.",
        )


async def handle_get_related_digests(
    ctx: ToolContext,
    digest_id: int,
    depth: int = 2,
    min_similarity: float = 0.6,
) -> str:
    """Handle get_related_digests tool call.

    Finds related digests using the knowledge graph.

    Args:
        ctx: Tool execution context
        digest_id: ID of the digest to find relations for
        depth: How many relationship hops to traverse (default 2)
        min_similarity: Minimum relationship score (default 0.6)

    Returns:
        Formatted related digests as string
    """
    try:
        graph_service = ctx.get_graph_service()

        # First verify the digest exists
        from reconly_core.database.models import Digest

        digest = ctx.db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            return format_error(
                error_type="Digest Not Found",
                message=f"No digest found with ID {digest_id}.",
                suggestion="Use semantic_search to find valid digest IDs.",
            )

        graph_data = graph_service.get_graph_data(
            center_digest_id=digest_id,
            depth=depth,
            min_similarity=min_similarity,
            include_tags=True,
        )

        logger.info(
            f"Graph query completed: digest_id={digest_id}, "
            f"nodes={len(graph_data.nodes)}, edges={len(graph_data.edges)}"
        )

        return format_related_digests(
            graph_data=graph_data,
            center_digest_id=digest_id,
        )

    except Exception as e:
        logger.exception(f"Graph query failed: {e}")
        return format_error(
            error_type="Graph Query Error",
            message=f"Failed to retrieve related digests: {str(e)}",
            suggestion="Ensure the knowledge graph has been computed for this digest.",
        )


# Tool definitions for MCP server registration
TOOL_DEFINITIONS = {
    "semantic_search": {
        "description": "Search the Reconly knowledge base using semantic similarity. Returns relevant digest chunks that match the query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query text",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "feed_id": {
                    "type": "integer",
                    "description": "Optional: Filter results to a specific feed ID",
                },
                "days": {
                    "type": "integer",
                    "description": "Optional: Filter to digests created within N days",
                    "minimum": 1,
                },
            },
            "required": ["query"],
        },
        "handler": handle_semantic_search,
    },
    "rag_query": {
        "description": "Ask a question and get an answer with citations from the Reconly knowledge base. Uses RAG (Retrieval-Augmented Generation) to provide grounded responses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to answer",
                },
                "max_chunks": {
                    "type": "integer",
                    "description": "Maximum context chunks to retrieve (default: 10)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                },
                "feed_id": {
                    "type": "integer",
                    "description": "Optional: Filter sources to a specific feed ID",
                },
                "days": {
                    "type": "integer",
                    "description": "Optional: Filter to sources created within N days",
                    "minimum": 1,
                },
            },
            "required": ["question"],
        },
        "handler": handle_rag_query,
    },
    "get_related_digests": {
        "description": "Find digests related to a specific digest ID using the knowledge graph. Returns semantically similar digests, digests from the same source, and digests with shared tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "digest_id": {
                    "type": "integer",
                    "description": "The ID of the digest to find relations for",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many relationship hops to traverse (default: 2)",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 4,
                },
                "min_similarity": {
                    "type": "number",
                    "description": "Minimum relationship score to include (default: 0.6)",
                    "default": 0.6,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["digest_id"],
        },
        "handler": handle_get_related_digests,
    },
}
