"""Search API endpoints for RAG hybrid search."""
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.search import (
    SearchResponse,
    SearchResult,
    ChunkMatch,
    SearchStatsResponse,
)

router = APIRouter()


@router.get("/hybrid/", response_model=SearchResponse)
async def hybrid_search(
    q: str = Query(..., min_length=1, description="Search query text"),
    feed_id: int | None = Query(None, description="Filter by feed ID"),
    source_id: int | None = Query(None, description="Filter by source ID"),
    days: int | None = Query(None, ge=1, description="Filter for digests created within N days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results (1-100)"),
    mode: Literal['hybrid', 'vector', 'fts'] = Query(
        'hybrid',
        description="Search mode: 'hybrid' (default), 'vector', or 'fts'"
    ),
    include_embedding: bool = Query(
        False,
        description="Include query embedding in response (for debugging)"
    ),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search digests using hybrid vector + full-text search.

    Combines semantic vector search (using pgvector) with PostgreSQL
    full-text search, merging results using Reciprocal Rank Fusion (RRF).

    **Search Modes:**
    - `hybrid` (default): Combines vector and FTS for best results
    - `vector`: Semantic search only using embeddings
    - `fts`: Full-text search only using PostgreSQL tsvector

    **Filters:**
    - `feed_id`: Only search digests from a specific feed
    - `source_id`: Only search digests from a specific source
    - `days`: Only search digests created within the last N days

    **Response:**
    Results are sorted by combined relevance score. Each result includes:
    - `matched_chunks`: Text chunks that matched the query
    - `score`: Combined RRF score (higher = more relevant)
    - `vector_rank` and `fts_rank`: Original ranks from each search method
    - `sources`: Which methods found this result ('vector', 'fts', or both)
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.search import HybridSearchService

        embedding_provider = get_embedding_provider(db=db)
        search_service = HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
        )

        response = await search_service.search(
            query=q,
            limit=limit,
            feed_id=feed_id,
            source_id=source_id,
            days=days,
            mode=mode,
            include_embedding=include_embedding,
        )

        results = [
            SearchResult(
                digest_id=r.digest_id,
                title=r.title,
                matched_chunks=[
                    ChunkMatch(text=c.text, score=c.score, chunk_index=c.chunk_index)
                    for c in r.matched_chunks
                ],
                score=r.score,
                vector_rank=r.vector_rank,
                fts_rank=r.fts_rank,
                sources=r.sources,
            )
            for r in response.results
        ]

        return SearchResponse(
            results=results,
            query_embedding=response.query_embedding,
            took_ms=response.took_ms,
            mode=response.mode,
            vector_results_count=response.vector_results_count,
            fts_results_count=response.fts_results_count,
            total=len(results),
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency for search: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/stats/", response_model=SearchStatsResponse)
async def get_search_stats(
    db: Session = Depends(get_db),
) -> SearchStatsResponse:
    """
    Get search configuration and indexing statistics.

    Returns information about:
    - RRF fusion parameters (k, weights)
    - Embedding provider and dimension
    - Number of indexed chunks and digests
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.search import HybridSearchService
        from reconly_core.database.models import DigestChunk

        embedding_provider = get_embedding_provider(db=db)
        search_service = HybridSearchService(
            db=db,
            embedding_provider=embedding_provider,
        )

        stats = search_service.get_search_stats()

        total_chunks = db.query(func.count(DigestChunk.id)).scalar() or 0
        total_digests_with_chunks = db.query(
            func.count(func.distinct(DigestChunk.digest_id))
        ).scalar() or 0

        return SearchStatsResponse(
            k=stats['k'],
            vector_weight=stats['vector_weight'],
            fts_weight=stats['fts_weight'],
            embedding_provider=stats['embedding_provider'],
            embedding_dimension=stats['embedding_dimension'],
            total_chunks=total_chunks,
            total_digests_with_chunks=total_digests_with_chunks,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get search stats: {str(e)}"
        )


@router.get("/vector/", response_model=SearchResponse)
async def vector_search(
    q: str = Query(..., min_length=1, description="Search query text"),
    feed_id: int | None = Query(None, description="Filter by feed ID"),
    source_id: int | None = Query(None, description="Filter by source ID"),
    days: int | None = Query(None, ge=1, description="Filter for digests created within N days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results (1-100)"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity score (0.0 to 1.0)"),
    include_embedding: bool = Query(False, description="Include query embedding in response"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search digests using vector similarity only.

    Uses pgvector's cosine distance for semantic search based on embeddings.

    **Parameters:**
    - `min_score`: Filter results below this similarity threshold (0.0 to 1.0)
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.search import VectorSearchService
        from reconly_core.database.models import Digest

        embedding_provider = get_embedding_provider(db=db)
        vector_service = VectorSearchService(
            db=db,
            embedding_provider=embedding_provider,
        )

        start_time = time.time()

        results = await vector_service.search(
            query=q,
            limit=limit,
            feed_id=feed_id,
            source_id=source_id,
            days=days,
            min_score=min_score,
        )

        took_ms = (time.time() - start_time) * 1000

        query_embedding = None
        if include_embedding:
            query_embedding = await embedding_provider.embed_single(q)

        # Group results by digest
        digest_results: dict[int, SearchResult] = {}
        for r in results:
            if r.digest_id not in digest_results:
                digest = db.query(Digest.title).filter(Digest.id == r.digest_id).first()
                title = digest.title if digest else None

                digest_results[r.digest_id] = SearchResult(
                    digest_id=r.digest_id,
                    title=title,
                    matched_chunks=[],
                    score=r.score,
                    vector_rank=None,
                    fts_rank=None,
                    sources=['vector'],
                )

            digest_results[r.digest_id].matched_chunks.append(
                ChunkMatch(
                    text=r.text,
                    score=r.score,
                    chunk_index=r.chunk_index,
                )
            )

        # Assign ranks
        sorted_results = sorted(digest_results.values(), key=lambda x: x.score, reverse=True)
        for idx, result in enumerate(sorted_results, start=1):
            result.vector_rank = idx

        return SearchResponse(
            results=sorted_results,
            query_embedding=query_embedding,
            took_ms=took_ms,
            mode='vector',
            vector_results_count=len(results),
            fts_results_count=0,
            total=len(sorted_results),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {str(e)}"
        )


@router.get("/fts/", response_model=SearchResponse)
async def fts_search(
    q: str = Query(..., min_length=1, description="Search query text"),
    feed_id: int | None = Query(None, description="Filter by feed ID"),
    source_id: int | None = Query(None, description="Filter by source ID"),
    days: int | None = Query(None, ge=1, description="Filter for digests created within N days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results (1-100)"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search digests using full-text search only.

    Uses PostgreSQL's to_tsvector and plainto_tsquery for text search.
    Results include relevance ranking using ts_rank and highlighted snippets.
    """
    try:
        from reconly_core.rag.search import FTSService

        start_time = time.time()

        fts_service = FTSService(db=db)

        results = fts_service.search(
            query=q,
            limit=limit,
            feed_id=feed_id,
            source_id=source_id,
            days=days,
        )

        took_ms = (time.time() - start_time) * 1000

        search_results = [
            SearchResult(
                digest_id=r.digest_id,
                title=r.title,
                matched_chunks=[
                    ChunkMatch(text=r.snippet, score=r.score, chunk_index=-1)
                ] if r.snippet else [],
                score=r.score,
                vector_rank=None,
                fts_rank=idx,
                sources=['fts'],
            )
            for idx, r in enumerate(results, start=1)
        ]

        return SearchResponse(
            results=search_results,
            query_embedding=None,
            took_ms=took_ms,
            mode='fts',
            vector_results_count=0,
            fts_results_count=len(results),
            total=len(search_results),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"FTS search failed: {str(e)}"
        )
