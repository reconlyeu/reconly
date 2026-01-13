"""Hybrid search service combining vector and full-text search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both
search methods for improved relevance.
"""
import logging
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Literal, TYPE_CHECKING

from reconly_core.rag.search.vector import VectorSearchService, VectorSearchResult
from reconly_core.rag.search.fts import FTSService, FTSSearchResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """LRU cache for query embeddings with TTL expiration.

    Thread-safe cache that stores embeddings keyed by
    (query_text, provider_name, model_name) with configurable TTL and max size.

    Attributes:
        max_size: Maximum number of entries in the cache (default 1000)
        ttl_seconds: Time-to-live in seconds for cache entries (default 900 = 15 min)

    Example:
        >>> cache = QueryEmbeddingCache(max_size=100, ttl_seconds=600)
        >>> cache.set("hello world", "ollama", "bge-m3", [0.1, 0.2, 0.3])
        >>> embedding = cache.get("hello world", "ollama", "bge-m3")
        >>> print(embedding)  # [0.1, 0.2, 0.3]
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: float = 900.0,  # 15 minutes
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[tuple[str, str, str], tuple[list[float], float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, provider: str, model: str) -> tuple[str, str, str]:
        """Create a cache key from query parameters."""
        return (query, provider, model)

    def get(
        self,
        query: str,
        provider: str,
        model: str,
    ) -> list[float] | None:
        """
        Get a cached embedding.

        Args:
            query: Query text
            provider: Embedding provider name
            model: Model name

        Returns:
            Cached embedding or None if not found/expired
        """
        key = self._make_key(query, provider, model)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            embedding, timestamp = self._cache[key]
            current_time = time.time()

            # Check if expired
            if current_time - timestamp > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return embedding

    def set(
        self,
        query: str,
        provider: str,
        model: str,
        embedding: list[float],
    ) -> None:
        """
        Store an embedding in the cache.

        Args:
            query: Query text
            provider: Embedding provider name
            model: Model name
            embedding: Embedding vector to cache
        """
        key = self._make_key(query, provider, model)
        current_time = time.time()

        with self._lock:
            # If key exists, update it
            if key in self._cache:
                self._cache[key] = (embedding, current_time)
                self._cache.move_to_end(key)
                return

            # Evict oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (embedding, current_time)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'ttl_seconds': self.ttl_seconds,
            }

SearchMode = Literal['hybrid', 'vector', 'fts']


@dataclass
class ChunkMatch:
    """A matching chunk within a digest.

    Attributes:
        text: The chunk text content
        score: Relevance score for this chunk
        chunk_index: Position within the digest
    """
    text: str
    score: float
    chunk_index: int


@dataclass
class HybridSearchResult:
    """Result from hybrid search.

    Aggregates chunk matches by digest and provides combined scoring.

    Attributes:
        digest_id: ID of the matching Digest
        title: Digest title
        matched_chunks: List of matching chunks with scores
        score: Combined RRF score
        vector_rank: Rank from vector search (None if not found)
        fts_rank: Rank from FTS (None if not found)
        sources: Which search methods found this result
    """
    digest_id: int
    title: str | None
    matched_chunks: list[ChunkMatch]
    score: float
    vector_rank: int | None = None
    fts_rank: int | None = None
    sources: list[str] = field(default_factory=list)


@dataclass
class HybridSearchResponse:
    """Response from hybrid search including metadata.

    Attributes:
        results: List of search results
        query_embedding: The query embedding (for debugging/caching)
        took_ms: Time taken for the search in milliseconds
        mode: Search mode used ('hybrid', 'vector', 'fts')
        vector_results_count: Number of results from vector search
        fts_results_count: Number of results from FTS
    """
    results: list[HybridSearchResult]
    query_embedding: list[float] | None = None
    took_ms: float = 0.0
    mode: str = 'hybrid'
    vector_results_count: int = 0
    fts_results_count: int = 0


class HybridSearchService:
    """Service for hybrid search combining vector and full-text search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from vector
    similarity search and full-text search for improved relevance.

    RRF Formula:
        score = sum(1 / (k + rank)) for each ranking method

    Where k is a constant (default 60) that controls how much weight
    to give to lower-ranked results.

    Features:
        - Query embedding caching with configurable TTL (15 min default)
        - LRU eviction when cache reaches max size (1000 entries default)
        - Thread-safe cache operations

    Example:
        >>> from reconly_core.rag.search import HybridSearchService
        >>> service = HybridSearchService(db, embedding_provider)
        >>> response = await service.search("machine learning trends")
        >>> for r in response.results:
        ...     print(f"Digest {r.digest_id}: {r.score:.3f} - {r.title}")
        >>> # Check cache performance
        >>> print(service.get_cache_stats())
    """

    # Default RRF constant (higher = more weight to lower ranks)
    DEFAULT_K = 60

    # Default weights for combining search methods
    DEFAULT_VECTOR_WEIGHT = 0.7
    DEFAULT_FTS_WEIGHT = 0.3

    # Default cache configuration
    DEFAULT_CACHE_MAX_SIZE = 1000
    DEFAULT_CACHE_TTL_SECONDS = 900.0  # 15 minutes

    def __init__(
        self,
        db: "Session",
        embedding_provider: "EmbeddingProvider",
        k: int = DEFAULT_K,
        vector_weight: float = DEFAULT_VECTOR_WEIGHT,
        fts_weight: float = DEFAULT_FTS_WEIGHT,
        ts_config: str = 'english',
        cache_max_size: int = DEFAULT_CACHE_MAX_SIZE,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        enable_cache: bool = True,
    ):
        """
        Initialize the hybrid search service.

        Args:
            db: Database session
            embedding_provider: Provider for generating query embeddings
            k: RRF constant (default 60)
            vector_weight: Weight for vector search scores (0.0 to 1.0)
            fts_weight: Weight for FTS scores (0.0 to 1.0)
            ts_config: PostgreSQL text search configuration
            cache_max_size: Maximum entries in embedding cache (default 1000)
            cache_ttl_seconds: TTL for cache entries in seconds (default 900 = 15 min)
            enable_cache: Whether to enable query embedding caching (default True)
        """
        self.db = db
        self.embedding_provider = embedding_provider
        self.k = k
        self.vector_weight = vector_weight
        self.fts_weight = fts_weight
        self.enable_cache = enable_cache

        # Initialize component services
        self.vector_service = VectorSearchService(db, embedding_provider)
        self.fts_service = FTSService(db, ts_config)

        # Initialize query embedding cache
        self._embedding_cache = QueryEmbeddingCache(
            max_size=cache_max_size,
            ttl_seconds=cache_ttl_seconds,
        ) if enable_cache else None

    async def search(
        self,
        query: str,
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        mode: SearchMode = 'hybrid',
        include_embedding: bool = False,
    ) -> HybridSearchResponse:
        """
        Search using hybrid vector + FTS approach.

        Args:
            query: Search query text
            limit: Maximum number of results to return
            feed_id: Optional filter by feed ID
            source_id: Optional filter by source ID
            days: Optional filter for digests created within N days
            mode: Search mode ('hybrid', 'vector', 'fts')
            include_embedding: Include query embedding in response

        Returns:
            HybridSearchResponse with results and metadata
        """
        start_time = time.time()

        vector_results: list[VectorSearchResult] = []
        fts_results: list[FTSSearchResult] = []
        query_embedding: list[float] | None = None

        # Get vector search results
        if mode in ('hybrid', 'vector'):
            try:
                # Get query embedding (check cache first)
                query_embedding = await self._get_query_embedding(query)

                # Search using embedding
                vector_results = self.vector_service.search_sync(
                    query_embedding,
                    limit=limit * 2,  # Get more results for fusion
                    feed_id=feed_id,
                    source_id=source_id,
                    days=days,
                )
                logger.debug(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                if mode == 'vector':
                    # If vector-only mode, we need to raise
                    raise

        # Get FTS results
        if mode in ('hybrid', 'fts'):
            try:
                fts_results = self.fts_service.search(
                    query,
                    limit=limit * 2,  # Get more results for fusion
                    feed_id=feed_id,
                    source_id=source_id,
                    days=days,
                )
                logger.debug(f"FTS returned {len(fts_results)} results")
            except Exception as e:
                logger.error(f"FTS failed: {e}")
                if mode == 'fts':
                    # If FTS-only mode, we need to raise
                    raise

        # Merge results based on mode
        if mode == 'hybrid':
            merged_results = self._merge_with_rrf(
                vector_results, fts_results, limit
            )
        elif mode == 'vector':
            merged_results = self._convert_vector_results(vector_results[:limit])
        else:  # mode == 'fts'
            merged_results = self._convert_fts_results(fts_results[:limit])

        elapsed_ms = (time.time() - start_time) * 1000

        return HybridSearchResponse(
            results=merged_results,
            query_embedding=query_embedding if include_embedding else None,
            took_ms=elapsed_ms,
            mode=mode,
            vector_results_count=len(vector_results),
            fts_results_count=len(fts_results),
        )

    def _merge_with_rrf(
        self,
        vector_results: list[VectorSearchResult],
        fts_results: list[FTSSearchResult],
        limit: int,
    ) -> list[HybridSearchResult]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = vector_weight * (1/(k + vector_rank)) + fts_weight * (1/(k + fts_rank))
        """
        # Build digest -> results mapping
        digest_scores: dict[int, dict] = {}

        # Process vector results
        for rank, vr in enumerate(vector_results, start=1):
            if vr.digest_id not in digest_scores:
                digest_scores[vr.digest_id] = {
                    'digest_id': vr.digest_id,
                    'title': None,  # Will be filled from digest
                    'chunks': [],
                    'vector_rank': None,
                    'fts_rank': None,
                    'sources': [],
                }

            entry = digest_scores[vr.digest_id]
            entry['vector_rank'] = rank
            entry['sources'].append('vector')
            entry['chunks'].append(ChunkMatch(
                text=vr.text,
                score=vr.score,
                chunk_index=vr.chunk_index,
            ))

        # Process FTS results
        for rank, fr in enumerate(fts_results, start=1):
            if fr.digest_id not in digest_scores:
                digest_scores[fr.digest_id] = {
                    'digest_id': fr.digest_id,
                    'title': fr.title,
                    'chunks': [],
                    'vector_rank': None,
                    'fts_rank': None,
                    'sources': [],
                }

            entry = digest_scores[fr.digest_id]
            entry['fts_rank'] = rank
            if 'fts' not in entry['sources']:
                entry['sources'].append('fts')
            if entry['title'] is None:
                entry['title'] = fr.title

            # Add FTS match as a chunk if we have a snippet
            if fr.snippet:
                entry['chunks'].append(ChunkMatch(
                    text=fr.snippet,
                    score=fr.score,
                    chunk_index=-1,  # -1 indicates FTS snippet, not a real chunk
                ))

        # Calculate RRF scores
        results = []
        for digest_id, data in digest_scores.items():
            rrf_score = 0.0

            if data['vector_rank'] is not None:
                rrf_score += self.vector_weight * (1.0 / (self.k + data['vector_rank']))

            if data['fts_rank'] is not None:
                rrf_score += self.fts_weight * (1.0 / (self.k + data['fts_rank']))

            # Fetch title if not available
            title = data['title']
            if title is None:
                title = self._get_digest_title(digest_id)

            results.append(HybridSearchResult(
                digest_id=digest_id,
                title=title,
                matched_chunks=data['chunks'],
                score=rrf_score,
                vector_rank=data['vector_rank'],
                fts_rank=data['fts_rank'],
                sources=list(set(data['sources'])),  # Dedupe
            ))

        # Sort by RRF score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _convert_vector_results(
        self,
        vector_results: list[VectorSearchResult],
    ) -> list[HybridSearchResult]:
        """Convert vector-only results to hybrid format."""
        # Group by digest
        digest_chunks: dict[int, list[ChunkMatch]] = {}

        for vr in vector_results:
            if vr.digest_id not in digest_chunks:
                digest_chunks[vr.digest_id] = []

            digest_chunks[vr.digest_id].append(ChunkMatch(
                text=vr.text,
                score=vr.score,
                chunk_index=vr.chunk_index,
            ))

        results = []
        for idx, (digest_id, chunks) in enumerate(digest_chunks.items(), start=1):
            title = self._get_digest_title(digest_id)
            # Use best chunk score as overall score
            best_score = max(c.score for c in chunks) if chunks else 0.0

            results.append(HybridSearchResult(
                digest_id=digest_id,
                title=title,
                matched_chunks=chunks,
                score=best_score,
                vector_rank=idx,
                fts_rank=None,
                sources=['vector'],
            ))

        return results

    def _convert_fts_results(
        self,
        fts_results: list[FTSSearchResult],
    ) -> list[HybridSearchResult]:
        """Convert FTS-only results to hybrid format."""
        results = []

        for idx, fr in enumerate(fts_results, start=1):
            chunks = []
            if fr.snippet:
                chunks.append(ChunkMatch(
                    text=fr.snippet,
                    score=fr.score,
                    chunk_index=-1,
                ))

            results.append(HybridSearchResult(
                digest_id=fr.digest_id,
                title=fr.title,
                matched_chunks=chunks,
                score=fr.score,
                vector_rank=None,
                fts_rank=idx,
                sources=['fts'],
            ))

        return results

    def _get_digest_title(self, digest_id: int) -> str | None:
        """Fetch digest title from database."""
        from reconly_core.database.models import Digest

        digest = self.db.query(Digest.title).filter(
            Digest.id == digest_id
        ).first()

        return digest.title if digest else None

    async def _get_query_embedding(self, query: str) -> list[float]:
        """
        Get embedding for a query, using cache if available.

        Checks the embedding cache first. If not found or expired,
        generates a new embedding and stores it in the cache.

        Args:
            query: Search query text

        Returns:
            Embedding vector as list of floats
        """
        model_info = self.embedding_provider.get_model_info()
        provider_name = model_info.get('provider', 'unknown')
        model_name = model_info.get('model', 'unknown')

        # Check cache if enabled
        if self._embedding_cache is not None:
            cached = self._embedding_cache.get(query, provider_name, model_name)
            if cached is not None:
                logger.debug(f"Cache hit for query embedding: {query[:50]}...")
                return cached

        # Generate new embedding
        embedding = await self.embedding_provider.embed_single(query)

        # Store in cache if enabled
        if self._embedding_cache is not None:
            self._embedding_cache.set(query, provider_name, model_name, embedding)
            logger.debug(f"Cached embedding for query: {query[:50]}...")

        return embedding

    def get_cache_stats(self) -> dict | None:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats or None if cache is disabled
        """
        if self._embedding_cache is None:
            return None
        return self._embedding_cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the query embedding cache."""
        if self._embedding_cache is not None:
            self._embedding_cache.clear()
            logger.info("Query embedding cache cleared")

    def get_search_stats(self) -> dict:
        """Get statistics about the search configuration."""
        stats = {
            'k': self.k,
            'vector_weight': self.vector_weight,
            'fts_weight': self.fts_weight,
            'embedding_provider': self.embedding_provider.get_provider_name(),
            'embedding_dimension': self.embedding_provider.get_dimension(),
            'cache_enabled': self._embedding_cache is not None,
        }

        # Include cache stats if available
        cache_stats = self.get_cache_stats()
        if cache_stats:
            stats['cache'] = cache_stats

        return stats
