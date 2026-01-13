"""Vector similarity search service using pgvector.

Provides semantic search over digest chunks using pgvector's
cosine distance operator for efficient similarity search.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    """Result from vector similarity search.

    Attributes:
        chunk_id: Database ID of the DigestChunk
        digest_id: ID of the parent Digest
        chunk_index: Position within the digest (0-indexed)
        text: The chunk text content
        score: Similarity score (0.0 to 1.0, higher = more similar)
        distance: Raw distance from pgvector (lower = more similar)
        extra_data: Additional metadata from the chunk
    """
    chunk_id: int
    digest_id: int
    chunk_index: int
    text: str
    score: float
    distance: float
    extra_data: dict | None = None


class VectorSearchService:
    """Service for vector similarity search over digest chunks.

    Uses pgvector's cosine distance operator (<=>) for efficient
    similarity search in PostgreSQL.

    Example:
        >>> from reconly_core.rag.search import VectorSearchService
        >>> service = VectorSearchService(db, embedding_provider)
        >>> results = await service.search("machine learning trends", limit=10)
        >>> for r in results:
        ...     print(f"Digest {r.digest_id}: {r.score:.3f} - {r.text[:50]}...")
    """

    def __init__(
        self,
        db: "Session",
        embedding_provider: "EmbeddingProvider",
    ):
        """
        Initialize the vector search service.

        Args:
            db: Database session
            embedding_provider: Provider for generating query embeddings
        """
        self.db = db
        self.embedding_provider = embedding_provider

    async def search(
        self,
        query: str,
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        min_score: float = 0.0,
    ) -> list[VectorSearchResult]:
        """
        Search for chunks similar to the query.

        Args:
            query: Search query text
            limit: Maximum number of results to return
            feed_id: Optional filter by feed ID (via FeedRun)
            source_id: Optional filter by source ID
            days: Optional filter for digests created within N days
            min_score: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of VectorSearchResult objects sorted by similarity
        """
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_single(query)

        return self._search_pgvector(
            query_embedding, limit, feed_id, source_id, days, min_score
        )

    def search_sync(
        self,
        query_embedding: list[float],
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        min_score: float = 0.0,
    ) -> list[VectorSearchResult]:
        """
        Synchronous search using a pre-computed query embedding.

        Args:
            query_embedding: Pre-computed embedding vector
            limit: Maximum number of results to return
            feed_id: Optional filter by feed ID
            source_id: Optional filter by source ID
            days: Optional filter for digests created within N days
            min_score: Minimum similarity score

        Returns:
            List of VectorSearchResult objects
        """
        return self._search_pgvector(
            query_embedding, limit, feed_id, source_id, days, min_score
        )

    def _search_pgvector(
        self,
        query_embedding: list[float],
        limit: int,
        feed_id: int | None,
        source_id: int | None,
        days: int | None,
        min_score: float,
    ) -> list[VectorSearchResult]:
        """
        Search using pgvector's cosine distance operator.

        Uses the <=> operator for cosine distance (1 - cosine_similarity).
        """
        from reconly_core.database.models import DigestChunk, Digest, FeedRun

        # Build the query with pgvector cosine distance
        # Note: <=> returns cosine distance (1 - similarity), so lower is better
        # We convert to similarity score: score = 1 - distance

        # Base query with distance calculation
        query = self.db.query(
            DigestChunk,
            DigestChunk.embedding.cosine_distance(query_embedding).label('distance')
        ).join(
            Digest, DigestChunk.digest_id == Digest.id
        )

        # Apply filters
        if feed_id is not None:
            query = query.join(
                FeedRun, Digest.feed_run_id == FeedRun.id
            ).filter(FeedRun.feed_id == feed_id)

        if source_id is not None:
            query = query.filter(Digest.source_id == source_id)

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(Digest.created_at >= cutoff)

        # Filter by minimum score (convert to max distance)
        # distance = 1 - score, so max_distance = 1 - min_score
        if min_score > 0:
            max_distance = 1.0 - min_score
            query = query.filter(
                DigestChunk.embedding.cosine_distance(query_embedding) <= max_distance
            )

        # Order by distance and limit
        query = query.order_by('distance').limit(limit)

        # Execute and convert to results
        results = []
        for chunk, distance in query.all():
            score = max(0.0, 1.0 - distance)  # Convert distance to similarity
            results.append(VectorSearchResult(
                chunk_id=chunk.id,
                digest_id=chunk.digest_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=score,
                distance=distance,
                extra_data=chunk.extra_data,
            ))

        return results

    async def get_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding for a query string.

        Useful when you need the embedding for debugging or hybrid search.

        Args:
            query: Query text to embed

        Returns:
            Embedding vector as list of floats
        """
        return await self.embedding_provider.embed_single(query)

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from the provider."""
        return self.embedding_provider.get_dimension()
