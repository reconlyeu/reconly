"""Full-text search service using PostgreSQL tsvector/tsquery.

Provides keyword-based search with relevance ranking using PostgreSQL's
native full-text search capabilities.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class FTSSearchResult:
    """Result from full-text search.

    Attributes:
        digest_id: ID of the matching Digest
        title: Digest title
        summary: Digest summary (if any)
        score: Relevance score from ts_rank (higher = more relevant)
        matched_field: Which field(s) matched ('title', 'summary', 'content')
        snippet: Text snippet with match context (if available)
    """
    digest_id: int
    title: str | None
    summary: str | None
    score: float
    matched_field: str
    snippet: str | None = None


class FTSService:
    """Service for full-text search over digests.

    Uses PostgreSQL's to_tsvector and plainto_tsquery for powerful
    text search with ranking.

    Example:
        >>> from reconly_core.rag.search import FTSService
        >>> service = FTSService(db)
        >>> results = service.search("machine learning", limit=10)
        >>> for r in results:
        ...     print(f"Digest {r.digest_id}: {r.score:.3f} - {r.title}")
    """

    # Default text search configuration (language)
    DEFAULT_TS_CONFIG = 'english'

    def __init__(
        self,
        db: "Session",
        ts_config: str = DEFAULT_TS_CONFIG,
    ):
        """
        Initialize the full-text search service.

        Args:
            db: Database session
            ts_config: PostgreSQL text search configuration (e.g., 'english', 'german')
        """
        self.db = db
        self.ts_config = ts_config

    def search(
        self,
        query: str,
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
        search_fields: list[str] | None = None,
    ) -> list[FTSSearchResult]:
        """
        Search digests using full-text search.

        Args:
            query: Search query text
            limit: Maximum number of results to return
            feed_id: Optional filter by feed ID
            source_id: Optional filter by source ID
            days: Optional filter for digests created within N days
            search_fields: Fields to search in ['title', 'summary', 'content']
                          Defaults to all fields.

        Returns:
            List of FTSSearchResult objects sorted by relevance
        """
        if not query or not query.strip():
            return []

        if search_fields is None:
            search_fields = ['title', 'summary', 'content']
        # Build tsvector expression for combined fields
        # Weight: A = title (highest), B = summary, C = content
        tsvector_parts = []
        if 'title' in search_fields:
            tsvector_parts.append(
                f"setweight(to_tsvector('{self.ts_config}', COALESCE(title, '')), 'A')"
            )
        if 'summary' in search_fields:
            tsvector_parts.append(
                f"setweight(to_tsvector('{self.ts_config}', COALESCE(summary, '')), 'B')"
            )
        if 'content' in search_fields:
            tsvector_parts.append(
                f"setweight(to_tsvector('{self.ts_config}', COALESCE(content, '')), 'C')"
            )

        if not tsvector_parts:
            return []

        tsvector_expr = " || ".join(tsvector_parts)

        # Build the query using raw SQL for PostgreSQL-specific functions
        sql = f"""
            SELECT
                id,
                title,
                summary,
                ts_rank({tsvector_expr}, plainto_tsquery('{self.ts_config}', :query)) as rank,
                CASE
                    WHEN title ILIKE '%' || :query_like || '%' THEN 'title'
                    WHEN summary ILIKE '%' || :query_like || '%' THEN 'summary'
                    ELSE 'content'
                END as matched_field,
                ts_headline(
                    '{self.ts_config}',
                    COALESCE(summary, content, ''),
                    plainto_tsquery('{self.ts_config}', :query),
                    'MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>'
                ) as snippet
            FROM digests
            WHERE ({tsvector_expr}) @@ plainto_tsquery('{self.ts_config}', :query)
        """

        params = {
            'query': query,
            'query_like': query,
        }

        # Add filters
        filter_clauses = []

        if feed_id is not None:
            filter_clauses.append("feed_run_id IN (SELECT id FROM feed_runs WHERE feed_id = :feed_id)")
            params['feed_id'] = feed_id

        if source_id is not None:
            filter_clauses.append("source_id = :source_id")
            params['source_id'] = source_id

        if days is not None:
            filter_clauses.append("created_at >= :cutoff")
            params['cutoff'] = datetime.now(timezone.utc) - timedelta(days=days)

        if filter_clauses:
            sql += " AND " + " AND ".join(filter_clauses)

        sql += " ORDER BY rank DESC LIMIT :limit"
        params['limit'] = limit

        # Execute query
        result = self.db.execute(text(sql), params)
        rows = result.fetchall()

        # Convert to result objects
        results = []
        for row in rows:
            results.append(FTSSearchResult(
                digest_id=row.id,
                title=row.title,
                summary=row.summary,
                score=float(row.rank) if row.rank else 0.0,
                matched_field=row.matched_field,
                snippet=row.snippet,
            ))

        return results

    def search_chunks(
        self,
        query: str,
        limit: int = 20,
        feed_id: int | None = None,
        source_id: int | None = None,
        days: int | None = None,
    ) -> list[dict]:
        """
        Search digest chunks using full-text search.

        Returns chunk-level results for more granular matching.

        Args:
            query: Search query text
            limit: Maximum number of results
            feed_id: Optional filter by feed ID
            source_id: Optional filter by source ID
            days: Optional filter for digests created within N days

        Returns:
            List of dicts with chunk match information
        """
        from reconly_core.database.models import DigestChunk, Digest, FeedRun

        if not query or not query.strip():
            return []

        # Build base query
        db_query = self.db.query(DigestChunk).join(
            Digest, DigestChunk.digest_id == Digest.id
        )

        # Apply text filter using PostgreSQL FTS on chunk text
        fts_condition = text(
            f"to_tsvector('{self.ts_config}', text) @@ plainto_tsquery('{self.ts_config}', :query)"
        )
        db_query = db_query.filter(fts_condition).params(query=query)

        # Apply filters
        if feed_id is not None:
            db_query = db_query.join(
                FeedRun, Digest.feed_run_id == FeedRun.id
            ).filter(FeedRun.feed_id == feed_id)

        if source_id is not None:
            db_query = db_query.filter(Digest.source_id == source_id)

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            db_query = db_query.filter(Digest.created_at >= cutoff)

        # Limit results
        db_query = db_query.limit(limit)

        chunks = db_query.all()

        # Convert to result dicts
        results = []
        query_lower = query.lower()

        for chunk in chunks:
            # Calculate simple score based on match frequency
            text_lower = chunk.text.lower()
            match_count = text_lower.count(query_lower)
            score = min(1.0, match_count * 0.2)  # Cap at 1.0

            results.append({
                'chunk_id': chunk.id,
                'digest_id': chunk.digest_id,
                'chunk_index': chunk.chunk_index,
                'text': chunk.text,
                'score': score,
                'extra_data': chunk.extra_data,
            })

        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)

        return results
