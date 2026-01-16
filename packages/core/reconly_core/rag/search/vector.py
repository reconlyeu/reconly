"""Vector similarity search service using pgvector.

Provides semantic search over digest chunks and source content chunks
using pgvector's cosine distance operator for efficient similarity search.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Type alias for chunk source selection
ChunkSource = Literal['source_content', 'digest']


@dataclass
class VectorSearchResult:
    """Result from vector similarity search.

    Attributes:
        chunk_id: Database ID of the chunk (DigestChunk or SourceContentChunk)
        digest_id: ID of the parent Digest
        chunk_index: Position within the parent (0-indexed)
        text: The chunk text content
        score: Similarity score (0.0 to 1.0, higher = more similar)
        distance: Raw distance from pgvector (lower = more similar)
        extra_data: Additional metadata from the chunk
        source_type: Type of chunk ('source_content' or 'digest')
        source_item_title: Title of the source item (for source content chunks)
        source_item_url: URL of the source item (for source content chunks)
    """
    chunk_id: int
    digest_id: int
    chunk_index: int
    text: str
    score: float
    distance: float
    extra_data: dict | None = None
    source_type: ChunkSource = 'digest'
    source_item_title: str | None = None
    source_item_url: str | None = None


class VectorSearchService:
    """Service for vector similarity search over chunks.

    Uses pgvector's cosine distance operator (<=>) for efficient
    similarity search in PostgreSQL.

    Supports searching both DigestChunk (processed summaries) and
    SourceContentChunk (original source content) for different use cases:
    - source_content: Cleaner semantic search without template noise
    - digest: Search over processed/summarized content

    Example:
        >>> from reconly_core.rag.search import VectorSearchService
        >>> service = VectorSearchService(db, embedding_provider)
        >>> # Search source content (default, recommended for RAG)
        >>> results = await service.search("machine learning trends", limit=10)
        >>> # Search digest chunks (fallback)
        >>> results = await service.search("...", chunk_source='digest')
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
        chunk_source: ChunkSource = 'source_content',
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
            chunk_source: Which chunks to search ('source_content' or 'digest')

        Returns:
            List of VectorSearchResult objects sorted by similarity
        """
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_single(query)

        return self.search_sync(
            query_embedding, limit, feed_id, source_id, days, min_score, chunk_source
        )

    def search_sync(
        self,
        query_embedding: list[float],
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        min_score: float = 0.0,
        chunk_source: ChunkSource = 'source_content',
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
            chunk_source: Which chunks to search ('source_content' or 'digest')

        Returns:
            List of VectorSearchResult objects
        """
        if chunk_source == 'source_content':
            return self._search_source_content_chunks(
                query_embedding, limit, feed_id, source_id, days, min_score
            )
        else:
            return self._search_digest_chunks(
                query_embedding, limit, feed_id, source_id, days, min_score
            )

    def _search_digest_chunks(
        self,
        query_embedding: list[float],
        limit: int,
        feed_id: int | None,
        source_id: int | None,
        days: int | None,
        min_score: float,
    ) -> list[VectorSearchResult]:
        """
        Search DigestChunk using pgvector's cosine distance operator.

        Uses the <=> operator for cosine distance (1 - cosine_similarity).
        This searches processed/summarized digest content.
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
                source_type='digest',
            ))

        return results

    def _search_source_content_chunks(
        self,
        query_embedding: list[float],
        limit: int,
        feed_id: int | None,
        source_id: int | None,
        days: int | None,
        min_score: float,
    ) -> list[VectorSearchResult]:
        """
        Search SourceContentChunk using pgvector's cosine distance operator.

        Uses the <=> operator for cosine distance (1 - cosine_similarity).
        This searches original source content without template noise.

        The relationship chain is:
        SourceContentChunk -> SourceContent -> DigestSourceItem -> Digest
        """
        from reconly_core.database.models import (
            SourceContentChunk, SourceContent, DigestSourceItem, Digest, FeedRun
        )

        # Build the query with pgvector cosine distance
        # Join through the relationship chain to get digest context
        query = self.db.query(
            SourceContentChunk,
            SourceContentChunk.embedding.cosine_distance(query_embedding).label('distance'),
            Digest.id.label('digest_id'),
            DigestSourceItem.item_title,
            DigestSourceItem.item_url,
        ).join(
            SourceContent, SourceContentChunk.source_content_id == SourceContent.id
        ).join(
            DigestSourceItem, SourceContent.digest_source_item_id == DigestSourceItem.id
        ).join(
            Digest, DigestSourceItem.digest_id == Digest.id
        )

        # Apply filters
        if feed_id is not None:
            query = query.join(
                FeedRun, Digest.feed_run_id == FeedRun.id
            ).filter(FeedRun.feed_id == feed_id)

        if source_id is not None:
            query = query.filter(DigestSourceItem.source_id == source_id)

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(Digest.created_at >= cutoff)

        # Filter by minimum score (convert to max distance)
        if min_score > 0:
            max_distance = 1.0 - min_score
            query = query.filter(
                SourceContentChunk.embedding.cosine_distance(query_embedding) <= max_distance
            )

        # Only include chunks that have embeddings
        query = query.filter(SourceContentChunk.embedding.isnot(None))

        # Order by distance and limit
        query = query.order_by('distance').limit(limit)

        # Execute and convert to results
        results = []
        for chunk, distance, digest_id, item_title, item_url in query.all():
            score = max(0.0, 1.0 - distance)  # Convert distance to similarity
            results.append(VectorSearchResult(
                chunk_id=chunk.id,
                digest_id=digest_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=score,
                distance=distance,
                extra_data=chunk.extra_data,
                source_type='source_content',
                source_item_title=item_title,
                source_item_url=item_url,
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
