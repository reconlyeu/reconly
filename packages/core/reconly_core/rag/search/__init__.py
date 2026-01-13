"""Search services for RAG knowledge system.

This package provides semantic and full-text search over digest chunks,
with hybrid search combining both approaches using Reciprocal Rank Fusion.

Components:
    - VectorSearchService: Semantic search using pgvector cosine distance
    - FTSService: Full-text search using PostgreSQL tsvector/tsquery
    - HybridSearchService: Combined search with RRF score fusion

Usage:
    >>> from reconly_core.rag.search import HybridSearchService
    >>> from reconly_core.rag import get_embedding_provider
    >>>
    >>> provider = get_embedding_provider()
    >>> search = HybridSearchService(db, provider)
    >>> results = await search.search("machine learning", limit=10)
"""
from reconly_core.rag.search.vector import (
    VectorSearchService,
    VectorSearchResult,
)
from reconly_core.rag.search.fts import (
    FTSService,
    FTSSearchResult,
)
from reconly_core.rag.search.hybrid import (
    HybridSearchService,
    HybridSearchResult,
    HybridSearchResponse,
    ChunkMatch,
    SearchMode,
)

__all__ = [
    # Vector search
    'VectorSearchService',
    'VectorSearchResult',
    # Full-text search
    'FTSService',
    'FTSSearchResult',
    # Hybrid search
    'HybridSearchService',
    'HybridSearchResult',
    'HybridSearchResponse',
    'ChunkMatch',
    'SearchMode',
]
