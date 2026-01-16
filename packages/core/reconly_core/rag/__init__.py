"""RAG (Retrieval-Augmented Generation) Knowledge System.

This package provides semantic search and knowledge retrieval capabilities
for the Reconly digest system.

Components:
    - embeddings: Multi-provider embedding generation (Ollama, OpenAI, HuggingFace)
    - chunking: Text chunking for embedding preparation
    - embedding_service: High-level service for chunking and embedding digests
    - search: Hybrid search combining vector and full-text search
    - rag_service: RAG service for question answering with citations
    - citations: Citation formatting and parsing
    - graph_service: Knowledge graph relationships between digests

Usage:
    >>> from reconly_core.rag import get_embedding_provider, ChunkingService
    >>>
    >>> # Get embedding provider
    >>> provider = get_embedding_provider()
    >>>
    >>> # Chunk text
    >>> chunker = ChunkingService()
    >>> chunks = chunker.chunk_text(text)
    >>>
    >>> # Generate embeddings
    >>> embeddings = await provider.embed([c.text for c in chunks])
    >>>
    >>> # Search with hybrid search
    >>> from reconly_core.rag.search import HybridSearchService
    >>> search = HybridSearchService(db, provider)
    >>> results = await search.search("machine learning")
    >>>
    >>> # RAG question answering
    >>> from reconly_core.rag import RAGService
    >>> from reconly_core.summarizers import get_summarizer
    >>> summarizer = get_summarizer(db=db)
    >>> rag = RAGService(db, provider, summarizer)
    >>> result = await rag.query("What are the latest AI trends?")
    >>> print(result.answer)
"""
from reconly_core.rag.embeddings import (
    get_embedding_provider,
    list_embedding_providers,
    list_embedding_models,
    get_embedding_dimension,
    EmbeddingProvider,
)
from reconly_core.rag.chunking import ChunkingService, TextChunk
from reconly_core.rag.embedding_service import (
    EmbeddingService,
    chunk_and_embed_sync,
    chunk_and_embed_source_content_sync,
    EMBEDDING_STATUS_PENDING,
    EMBEDDING_STATUS_COMPLETED,
    EMBEDDING_STATUS_FAILED,
)
from reconly_core.rag.search import (
    VectorSearchService,
    VectorSearchResult,
    ChunkSource,
    FTSService,
    FTSSearchResult,
    HybridSearchService,
    HybridSearchResult,
    HybridSearchResponse,
    ChunkMatch,
)
from reconly_core.rag.rag_service import RAGService, RAGResult, RAGFilters
from reconly_core.rag.citations import (
    Citation,
    CitationContext,
    ParsedResponse,
    ExportContext,
    format_citations_for_prompt,
    parse_citations_from_response,
    format_citations_for_output,
    enrich_citations_with_urls,
    format_export_as_markdown,
    format_export_as_json,
)
from reconly_core.rag.graph_service import (
    GraphService,
    GraphNode,
    GraphEdge,
    GraphData,
)

__all__ = [
    # Embedding functions
    'get_embedding_provider',
    'list_embedding_providers',
    'list_embedding_models',
    'get_embedding_dimension',
    'EmbeddingProvider',
    # Chunking
    'ChunkingService',
    'TextChunk',
    # High-level service
    'EmbeddingService',
    'chunk_and_embed_sync',
    'chunk_and_embed_source_content_sync',
    'EMBEDDING_STATUS_PENDING',
    'EMBEDDING_STATUS_COMPLETED',
    'EMBEDDING_STATUS_FAILED',
    # Search services
    'VectorSearchService',
    'VectorSearchResult',
    'ChunkSource',
    'FTSService',
    'FTSSearchResult',
    'HybridSearchService',
    'HybridSearchResult',
    'HybridSearchResponse',
    'ChunkMatch',
    # RAG service
    'RAGService',
    'RAGResult',
    'RAGFilters',
    # Citations
    'Citation',
    'CitationContext',
    'ParsedResponse',
    'ExportContext',
    'format_citations_for_prompt',
    'parse_citations_from_response',
    'format_citations_for_output',
    'enrich_citations_with_urls',
    'format_export_as_markdown',
    'format_export_as_json',
    # Graph service
    'GraphService',
    'GraphNode',
    'GraphEdge',
    'GraphData',
]
