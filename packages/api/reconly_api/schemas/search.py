"""Search-related schemas for RAG hybrid search API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChunkMatch(BaseModel):
    """A matching chunk within a digest."""
    text: str = Field(..., description="The chunk text content")
    score: float = Field(..., description="Relevance score for this chunk (0.0 to 1.0)")
    chunk_index: int = Field(..., description="Position within the digest (-1 for FTS snippets)")

    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    """A search result with matched chunks."""
    digest_id: int = Field(..., description="ID of the matching digest")
    title: str | None = Field(None, description="Digest title")
    matched_chunks: list[ChunkMatch] = Field(
        default_factory=list,
        description="List of matching chunks with scores"
    )
    score: float = Field(..., description="Combined relevance score")
    vector_rank: int | None = Field(
        None,
        description="Rank from vector search (None if not found by vector search)"
    )
    fts_rank: int | None = Field(
        None,
        description="Rank from FTS (None if not found by FTS)"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Which search methods found this result ('vector', 'fts')"
    )

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """Response from hybrid search endpoint."""
    results: list[SearchResult] = Field(
        default_factory=list,
        description="List of search results sorted by relevance"
    )
    query_embedding: list[float] | None = Field(
        None,
        description="Query embedding vector (for debugging, only if requested)"
    )
    took_ms: float = Field(
        default=0.0,
        description="Time taken for the search in milliseconds"
    )
    mode: str = Field(
        default="hybrid",
        description="Search mode used ('hybrid', 'vector', 'fts')"
    )
    vector_results_count: int = Field(
        default=0,
        description="Number of results from vector search"
    )
    fts_results_count: int = Field(
        default=0,
        description="Number of results from FTS"
    )
    total: int = Field(
        default=0,
        description="Total number of results returned"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "digest_id": 42,
                        "title": "Understanding Machine Learning Trends",
                        "matched_chunks": [
                            {
                                "text": "Machine learning continues to evolve...",
                                "score": 0.92,
                                "chunk_index": 0
                            }
                        ],
                        "score": 0.85,
                        "vector_rank": 1,
                        "fts_rank": 2,
                        "sources": ["vector", "fts"]
                    }
                ],
                "took_ms": 45.2,
                "mode": "hybrid",
                "vector_results_count": 15,
                "fts_results_count": 10,
                "total": 1
            }
        }
    )


class SearchQuery(BaseModel):
    """Query parameters for search requests."""
    q: str = Field(..., min_length=1, description="Search query text")
    feed_id: int | None = Field(None, description="Filter by feed ID")
    source_id: int | None = Field(None, description="Filter by source ID")
    days: int | None = Field(
        None,
        ge=1,
        description="Filter for digests created within N days"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results (1-100)"
    )
    mode: Literal['hybrid', 'vector', 'fts'] = Field(
        default='hybrid',
        description="Search mode: 'hybrid' (default), 'vector', or 'fts'"
    )
    include_embedding: bool = Field(
        default=False,
        description="Include query embedding in response (for debugging)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "q": "machine learning trends",
                "limit": 10,
                "mode": "hybrid",
                "days": 30
            }
        }
    )


class SearchStatsResponse(BaseModel):
    """Statistics about the search configuration."""
    k: int = Field(..., description="RRF constant (higher = more weight to lower ranks)")
    vector_weight: float = Field(..., description="Weight for vector search scores (0.0 to 1.0)")
    fts_weight: float = Field(..., description="Weight for FTS scores (0.0 to 1.0)")
    embedding_provider: str = Field(..., description="Name of the embedding provider")
    embedding_dimension: int = Field(..., description="Dimension of embedding vectors")
    total_chunks: int | None = Field(None, description="Total number of indexed chunks")
    total_digests_with_chunks: int | None = Field(
        None,
        description="Number of digests with embeddings"
    )

    model_config = ConfigDict(from_attributes=True)
