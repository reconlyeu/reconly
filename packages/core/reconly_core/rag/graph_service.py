"""Graph Service for Knowledge Graph relationships.

Computes and manages relationships between digests for knowledge graph
visualization and navigation using PostgreSQL with pgvector.

Relationship types:
- semantic: Digests with similar embeddings (cosine similarity > threshold)
- tag: Digests sharing one or more tags
- source: Digests from the same source/feed

Chunk Sources:
- source_content: Use SourceContentChunk embeddings (cleaner, recommended)
- digest: Use DigestChunk embeddings (fallback for legacy data)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

from reconly_core.rag.search.vector import ChunkSource

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Relationship types
RelationshipType = Literal["semantic", "tag", "source"]


@dataclass
class GraphNode:
    """A node in the knowledge graph.

    Attributes:
        id: Unique node identifier (e.g., "d_42" for digest, "t_ai" for tag)
        type: Node type ("digest", "tag", "source")
        label: Display label for the node
        data: Additional node data (varies by type)
    """
    id: str
    type: Literal["digest", "tag", "source"]
    label: str
    data: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph.

    Attributes:
        source: Source node ID
        target: Target node ID
        type: Edge type ("semantic", "tag", "source")
        score: Relationship strength (0.0 to 1.0)
        extra_data: Additional edge metadata
    """
    source: str
    target: str
    type: RelationshipType
    score: float
    extra_data: dict = field(default_factory=dict)


@dataclass
class GraphData:
    """Complete graph data structure.

    Attributes:
        nodes: List of graph nodes
        edges: List of graph edges
    """
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


class GraphService:
    """Service for computing and managing digest relationships.

    Provides functionality to:
    - Compute semantic relationships using embedding similarity
    - Detect tag-based relationships (shared tags)
    - Detect source-based relationships (same source)
    - Query the knowledge graph for visualization

    Supports two chunk sources for semantic relationships:
    - source_content: Uses SourceContentChunk embeddings (cleaner, recommended)
    - digest: Uses DigestChunk embeddings (fallback for legacy data)

    Example:
        >>> from reconly_core.rag import GraphService, get_embedding_provider
        >>>
        >>> provider = get_embedding_provider(db=db)
        >>> graph = GraphService(db, provider)
        >>>
        >>> # Compute relationships for a new digest (uses source content by default)
        >>> await graph.compute_relationships(digest_id=42)
        >>>
        >>> # Fallback to digest chunks for legacy data
        >>> await graph.compute_relationships(digest_id=42, chunk_source='digest')
        >>>
        >>> # Query graph centered on a digest
        >>> data = graph.get_graph_data(center_digest_id=42, depth=2)
        >>> print(f"Found {len(data.nodes)} nodes, {len(data.edges)} edges")
    """

    # Default thresholds
    DEFAULT_SEMANTIC_THRESHOLD = 0.55
    DEFAULT_MIN_SIMILARITY = 0.4
    DEFAULT_MAX_EDGES_PER_DIGEST = 10
    DEFAULT_TAG_THRESHOLD = 0.15

    def __init__(
        self,
        db: "Session",
        embedding_provider: "EmbeddingProvider | None" = None,
        semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        max_edges_per_digest: int = DEFAULT_MAX_EDGES_PER_DIGEST,
        default_chunk_source: ChunkSource = 'source_content',
        tag_threshold: float = DEFAULT_TAG_THRESHOLD,
    ):
        """Initialize the graph service.

        Args:
            db: Database session
            embedding_provider: Provider for embeddings (optional, for semantic)
            semantic_threshold: Minimum similarity for semantic relationships
            min_similarity: Minimum similarity for graph queries
            max_edges_per_digest: Maximum edges per digest for pruning
            default_chunk_source: Default chunk source for semantic relationships
                                  ('source_content' or 'digest')
            tag_threshold: Minimum Jaccard similarity for tag relationships
        """
        self.db = db
        self.embedding_provider = embedding_provider
        self.semantic_threshold = semantic_threshold
        self.min_similarity = min_similarity
        self.max_edges_per_digest = max_edges_per_digest
        self.default_chunk_source: ChunkSource = default_chunk_source
        self.tag_threshold = tag_threshold

    # ═══════════════════════════════════════════════════════════════════════════════
    # RELATIONSHIP COMPUTATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def compute_relationships(
        self,
        digest_id: int,
        include_semantic: bool = True,
        include_tags: bool = True,
        include_source: bool = True,
        chunk_source: ChunkSource | None = None,
    ) -> int:
        """Compute all relationships for a digest.

        Creates DigestRelationship records for semantic, tag, and source
        relationships with other digests.

        Args:
            digest_id: ID of the digest to compute relationships for
            include_semantic: Whether to compute semantic relationships
            include_tags: Whether to compute tag relationships
            include_source: Whether to compute source relationships
            chunk_source: Which chunks to use for semantic similarity
                          ('source_content' or 'digest'). If None, uses default.

        Returns:
            Number of relationships created
        """
        from reconly_core.database.models import Digest

        digest = self.db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            logger.warning(f"Digest {digest_id} not found")
            return 0

        total_created = 0

        # Determine which chunk source to use
        effective_chunk_source = chunk_source if chunk_source is not None else self.default_chunk_source

        if include_semantic:
            count = await self._compute_semantic_relationships(digest, effective_chunk_source)
            total_created += count
            logger.debug(f"Created {count} semantic relationships for digest {digest_id} (chunk_source={effective_chunk_source})")

        if include_tags:
            count = self._compute_tag_relationships(digest)
            total_created += count
            logger.debug(f"Created {count} tag relationships for digest {digest_id}")

        if include_source:
            count = self._compute_source_relationships(digest)
            total_created += count
            logger.debug(f"Created {count} source relationships for digest {digest_id}")

        self.db.flush()
        logger.info(f"Created {total_created} relationships for digest {digest_id}")

        return total_created

    async def _compute_semantic_relationships(
        self,
        digest,
        chunk_source: ChunkSource,
    ) -> int:
        """Compute semantic relationships based on embedding similarity.

        Finds digests with similar embeddings and creates bidirectional
        relationships above the threshold.

        Args:
            digest: The digest to compute relationships for
            chunk_source: Which chunks to use ('source_content' or 'digest')

        Returns:
            Number of relationships created
        """
        if not self.embedding_provider:
            logger.debug("No embedding provider, skipping semantic relationships")
            return 0

        # Get representative embedding based on chunk source
        if chunk_source == 'source_content':
            digest_embedding = self._get_source_content_embedding(digest)
        else:
            digest_embedding = self._get_digest_chunk_embedding(digest)

        if digest_embedding is None:
            logger.debug(f"Digest {digest.id} has no embedded chunks (chunk_source={chunk_source})")
            return 0

        # Find similar digests
        similar_digests = self._find_similar_digests(
            digest.id,
            digest_embedding,
            chunk_source=chunk_source,
            limit=self.max_edges_per_digest * 2,  # Get more to filter
        )

        # Create relationships
        created = 0
        for other_digest_id, similarity in similar_digests:
            if similarity < self.semantic_threshold:
                continue

            # Create bidirectional relationships
            extra_data = {"method": "cosine_similarity", "chunk_source": chunk_source}
            created += self._create_relationship_if_not_exists(
                digest.id, other_digest_id, "semantic", similarity, extra_data
            )
            created += self._create_relationship_if_not_exists(
                other_digest_id, digest.id, "semantic", similarity, extra_data
            )

            if created >= self.max_edges_per_digest * 2:
                break

        return created

    def _get_digest_chunk_embedding(self, digest) -> list[float] | None:
        """Get a representative embedding from DigestChunk.

        Uses the first chunk's embedding as representative.
        """
        from reconly_core.database.models import DigestChunk

        chunk = self.db.query(DigestChunk).filter(
            DigestChunk.digest_id == digest.id,
            DigestChunk.embedding.isnot(None)
        ).first()

        if not chunk:
            return None

        return self._embedding_to_list(chunk.embedding)

    def _get_source_content_embedding(self, digest) -> list[float] | None:
        """Get a representative embedding from SourceContentChunk.

        Uses the first chunk's embedding from the digest's source content.
        The relationship chain is:
        Digest -> DigestSourceItem -> SourceContent -> SourceContentChunk
        """
        from reconly_core.database.models import (
            DigestSourceItem, SourceContent, SourceContentChunk
        )

        # Get the first source content chunk with an embedding for this digest
        chunk = self.db.query(SourceContentChunk).join(
            SourceContent, SourceContentChunk.source_content_id == SourceContent.id
        ).join(
            DigestSourceItem, SourceContent.digest_source_item_id == DigestSourceItem.id
        ).filter(
            DigestSourceItem.digest_id == digest.id,
            SourceContentChunk.embedding.isnot(None)
        ).order_by(
            SourceContentChunk.chunk_index
        ).first()

        if not chunk:
            return None

        return self._embedding_to_list(chunk.embedding)

    def _find_similar_digests(
        self,
        exclude_digest_id: int,
        query_embedding: list[float],
        chunk_source: ChunkSource = 'source_content',
        limit: int = 20,
    ) -> list[tuple[int, float]]:
        """Find digests with similar embeddings using pgvector.

        Uses cosine distance to find similar chunks, grouped by digest,
        taking the minimum distance (maximum similarity) per digest.

        Args:
            exclude_digest_id: Digest to exclude from results
            query_embedding: Embedding to compare against
            chunk_source: Which chunks to search ('source_content' or 'digest')
            limit: Maximum results to return

        Returns:
            List of (digest_id, similarity_score) tuples
        """
        if chunk_source == 'source_content':
            return self._find_similar_digests_from_source_content(
                exclude_digest_id, query_embedding, limit
            )
        else:
            return self._find_similar_digests_from_digest_chunks(
                exclude_digest_id, query_embedding, limit
            )

    def _find_similar_digests_from_digest_chunks(
        self,
        exclude_digest_id: int,
        query_embedding: list[float],
        limit: int = 20,
    ) -> list[tuple[int, float]]:
        """Find similar digests using DigestChunk embeddings.

        Uses cosine distance to find similar digest chunks, grouped by digest,
        taking the minimum distance (maximum similarity) per digest.

        Args:
            exclude_digest_id: Digest to exclude from results
            query_embedding: Embedding to compare against
            limit: Maximum results to return

        Returns:
            List of (digest_id, similarity_score) tuples
        """
        from sqlalchemy import func
        from reconly_core.database.models import DigestChunk

        query = self.db.query(
            DigestChunk.digest_id,
            func.min(DigestChunk.embedding.cosine_distance(query_embedding)).label('min_distance')
        ).filter(
            DigestChunk.digest_id != exclude_digest_id,
            DigestChunk.embedding.isnot(None)
        ).group_by(
            DigestChunk.digest_id
        ).order_by(
            'min_distance'
        ).limit(limit)

        results = []
        for digest_id, distance in query.all():
            similarity = max(0.0, 1.0 - distance)
            results.append((digest_id, similarity))

        return results

    def _find_similar_digests_from_source_content(
        self,
        exclude_digest_id: int,
        query_embedding: list[float],
        limit: int = 20,
    ) -> list[tuple[int, float]]:
        """Find similar digests using SourceContentChunk embeddings.

        Uses cosine distance to find similar source content chunks from other
        digests. Results are grouped by the parent digest, taking the minimum
        distance (maximum similarity) per digest.

        The relationship chain is:
        SourceContentChunk -> SourceContent -> DigestSourceItem -> Digest

        This provides cleaner semantic relationships by using original source
        content instead of processed digest summaries with template noise.

        Args:
            exclude_digest_id: Digest to exclude from results
            query_embedding: Embedding to compare against
            limit: Maximum results to return

        Returns:
            List of (digest_id, similarity_score) tuples
        """
        from sqlalchemy import func
        from reconly_core.database.models import (
            SourceContentChunk, SourceContent, DigestSourceItem
        )

        # Query SourceContentChunk with joins to get digest_id
        # Group by digest_id and take minimum distance
        query = self.db.query(
            DigestSourceItem.digest_id,
            func.min(
                SourceContentChunk.embedding.cosine_distance(query_embedding)
            ).label('min_distance')
        ).join(
            SourceContent, SourceContentChunk.source_content_id == SourceContent.id
        ).join(
            DigestSourceItem, SourceContent.digest_source_item_id == DigestSourceItem.id
        ).filter(
            DigestSourceItem.digest_id != exclude_digest_id,
            SourceContentChunk.embedding.isnot(None)
        ).group_by(
            DigestSourceItem.digest_id
        ).order_by(
            'min_distance'
        ).limit(limit)

        results = []
        for digest_id, distance in query.all():
            similarity = max(0.0, 1.0 - distance)
            results.append((digest_id, similarity))

        return results

    def _compute_tag_relationships(self, digest) -> int:
        """Compute tag-based relationships.

        Creates relationships between digests that share tags.
        Score is based on Jaccard similarity of tag sets.
        """
        from reconly_core.database.models import DigestTag, Tag

        # Get tags for this digest
        digest_tag_ids = {dt.tag_id for dt in digest.tags}
        if not digest_tag_ids:
            return 0

        # Find other digests with overlapping tags
        overlapping = self.db.query(
            DigestTag.digest_id
        ).filter(
            DigestTag.tag_id.in_(digest_tag_ids),
            DigestTag.digest_id != digest.id
        ).distinct().all()

        created = 0
        for (other_digest_id,) in overlapping:
            # Get tags for the other digest
            other_tags = self.db.query(DigestTag).filter(
                DigestTag.digest_id == other_digest_id
            ).all()
            other_tag_ids = {dt.tag_id for dt in other_tags}

            # Calculate Jaccard similarity
            intersection = len(digest_tag_ids & other_tag_ids)
            union = len(digest_tag_ids | other_tag_ids)
            jaccard = intersection / union if union > 0 else 0.0

            if jaccard < self.tag_threshold:
                continue

            # Get shared tag names for extra_data
            shared_tag_ids = digest_tag_ids & other_tag_ids
            shared_tags = self.db.query(Tag.name).filter(
                Tag.id.in_(shared_tag_ids)
            ).all()
            shared_tag_names = [t.name for t in shared_tags]

            created += self._create_relationship_if_not_exists(
                digest.id, other_digest_id, "tag", jaccard, {"shared_tags": shared_tag_names}
            )

            if created >= self.max_edges_per_digest:
                break

        return created

    def _compute_source_relationships(self, digest) -> int:
        """Compute source-based relationships.

        Creates relationships between digests from the same source.
        Score is based on temporal proximity (closer = higher score).
        """
        from reconly_core.database.models import Digest

        if not digest.source_id:
            return 0

        # Find other digests from the same source
        other_digests = self.db.query(Digest).filter(
            Digest.source_id == digest.source_id,
            Digest.id != digest.id
        ).order_by(
            Digest.created_at.desc()
        ).limit(self.max_edges_per_digest * 2).all()

        created = 0
        digest_time = digest.created_at or datetime.utcnow()

        for other in other_digests:
            other_time = other.created_at or datetime.utcnow()

            # Calculate temporal score (exponential decay over ~25 days)
            time_diff = abs((digest_time - other_time).total_seconds())
            days_diff = time_diff / 86400  # Convert to days
            # Score decays from 1.0 to ~0.55 over 30 days
            score = max(0.1, min(1.0, 1.0 * (0.98 ** days_diff)))

            if score < self.min_similarity:
                continue

            created += self._create_relationship_if_not_exists(
                digest.id, other.id, "source", score, {"source_id": digest.source_id}
            )

            if created >= self.max_edges_per_digest:
                break

        return created

    # ═══════════════════════════════════════════════════════════════════════════════
    # GRAPH QUERYING
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_graph_data(
        self,
        center_digest_id: int | None = None,
        depth: int = 2,
        min_similarity: float | None = None,
        include_tags: bool = True,
        relationship_types: list[str] | None = None,
        limit: int = 100,
        feed_id: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        tag_names: list[str] | None = None,
    ) -> GraphData:
        """Get graph data for visualization.

        Args:
            center_digest_id: Optional digest to center the graph on
            depth: How many relationship hops to traverse
            min_similarity: Minimum relationship score to include
            include_tags: Whether to include tag nodes
            relationship_types: Filter by relationship types
            limit: Maximum number of nodes to return
            feed_id: Filter digests by feed ID
            from_date: Filter digests created on or after this date (ISO format)
            to_date: Filter digests created on or before this date (ISO format)
            tag_names: Filter digests that have any of these tags

        Returns:
            GraphData with nodes and edges for visualization
        """
        from reconly_core.database.models import (
            Digest, DigestRelationship, Tag, DigestTag, FeedRun, Feed
        )
        from datetime import datetime

        # Build a cache of feed names for cluster labels
        feed_cache: dict[int, str] = {}
        def get_feed_name(feed_run_id: int | None) -> tuple[int | None, str | None]:
            """Get feed ID and name from feed run ID."""
            if not feed_run_id:
                return None, None
            feed_run = self.db.query(FeedRun).filter(FeedRun.id == feed_run_id).first()
            if not feed_run:
                return None, None
            if feed_run.feed_id not in feed_cache:
                feed = self.db.query(Feed).filter(Feed.id == feed_run.feed_id).first()
                feed_cache[feed_run.feed_id] = feed.name if feed else f"Feed {feed_run.feed_id}"
            return feed_run.feed_id, feed_cache[feed_run.feed_id]

        min_sim = min_similarity or self.min_similarity
        # Build default relationship types based on include_tags if not explicitly provided
        if relationship_types:
            rel_types = relationship_types
        elif include_tags:
            rel_types = ["semantic", "tag", "source"]
        else:
            rel_types = ["semantic", "source"]

        # Build base digest query with filters
        def build_filtered_digest_ids() -> set[int]:
            """Build set of digest IDs that match all filters."""
            query = self.db.query(Digest.id)

            # Filter by feed
            if feed_id:
                query = query.join(FeedRun, Digest.feed_run_id == FeedRun.id).filter(
                    FeedRun.feed_id == feed_id
                )

            # Filter by date range
            if from_date:
                try:
                    from_dt = datetime.fromisoformat(from_date)
                    query = query.filter(Digest.created_at >= from_dt)
                except ValueError:
                    pass

            if to_date:
                try:
                    to_dt = datetime.fromisoformat(to_date)
                    query = query.filter(Digest.created_at <= to_dt)
                except ValueError:
                    pass

            # Filter by tags
            if tag_names:
                # Get digests that have any of the specified tags
                tag_subquery = self.db.query(DigestTag.digest_id).join(
                    Tag, DigestTag.tag_id == Tag.id
                ).filter(Tag.name.in_(tag_names)).subquery()
                query = query.filter(Digest.id.in_(tag_subquery))

            return set(row[0] for row in query.all())

        # Get filtered digest IDs if any filters are active
        filtered_ids = None
        if feed_id or from_date or to_date or tag_names:
            filtered_ids = build_filtered_digest_ids()

        def is_digest_allowed(digest_id: int) -> bool:
            """Check if a digest passes the filters."""
            return filtered_ids is None or digest_id in filtered_ids

        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        if center_digest_id:
            # Start from a specific digest and traverse
            visited_digests = set()
            to_visit = [(center_digest_id, 0)]

            while to_visit and len(nodes) < limit:
                digest_id, current_depth = to_visit.pop(0)

                if digest_id in visited_digests:
                    continue
                visited_digests.add(digest_id)

                # Skip if digest doesn't pass filters (except center node)
                if digest_id != center_digest_id and not is_digest_allowed(digest_id):
                    continue

                # Get the digest
                digest = self.db.query(Digest).filter(Digest.id == digest_id).first()
                if not digest:
                    continue

                # Get feed info for clustering
                digest_feed_id, digest_feed_name = get_feed_name(digest.feed_run_id)

                # Add digest node
                node_id = f"d_{digest_id}"
                nodes[node_id] = GraphNode(
                    id=node_id,
                    type="digest",
                    label=digest.title[:50] if digest.title else f"Digest {digest_id}",
                    data={
                        "digest_id": digest.id,
                        "title": digest.title,
                        "created_at": digest.created_at.isoformat() if digest.created_at else None,
                        "source_id": digest.source_id,
                        "feed_id": digest_feed_id,
                        "feed_name": digest_feed_name,
                    }
                )

                # Add feed node as cluster anchor (only if source relationships requested)
                if digest_feed_id and "source" in rel_types:
                    feed_node_id = f"f_{digest_feed_id}"
                    if feed_node_id not in nodes:
                        nodes[feed_node_id] = GraphNode(
                            id=feed_node_id,
                            type="feed",
                            label=digest_feed_name or f"Feed {digest_feed_id}",
                            data={"feed_id": digest_feed_id, "name": digest_feed_name}
                        )
                    # Add edge from digest to feed
                    edges.append(GraphEdge(
                        source=node_id,
                        target=feed_node_id,
                        type="source",
                        score=0.5,  # Lower score so it doesn't dominate
                    ))

                # Add tag nodes (only if tag relationships requested)
                if "tag" in rel_types:
                    for dt in digest.tags:
                        tag_node_id = f"t_{dt.tag.name}"
                        if tag_node_id not in nodes:
                            # Count digests with this tag
                            tag_count = self.db.query(DigestTag).filter(
                                DigestTag.tag_id == dt.tag_id
                            ).count()
                            nodes[tag_node_id] = GraphNode(
                                id=tag_node_id,
                                type="tag",
                                label=dt.tag.name,
                                data={"tag_id": dt.tag_id, "count": tag_count}
                            )
                        # Add edge to tag
                        edges.append(GraphEdge(
                            source=node_id,
                            target=tag_node_id,
                            type="tag",
                            score=1.0,
                        ))

                # Stop traversing at max depth
                if current_depth >= depth:
                    continue

                # Get relationships from this digest
                relationships = self.db.query(DigestRelationship).filter(
                    DigestRelationship.source_digest_id == digest_id,
                    DigestRelationship.relationship_type.in_(rel_types),
                    DigestRelationship.score >= min_sim
                ).order_by(
                    DigestRelationship.score.desc()
                ).limit(self.max_edges_per_digest).all()

                for rel in relationships:
                    target_node_id = f"d_{rel.target_digest_id}"

                    # Add edge
                    edges.append(GraphEdge(
                        source=node_id,
                        target=target_node_id,
                        type=rel.relationship_type,
                        score=rel.score,
                        extra_data=rel.extra_data or {},
                    ))

                    # Queue for traversal
                    if rel.target_digest_id not in visited_digests:
                        to_visit.append((rel.target_digest_id, current_depth + 1))

        else:
            # Return all nodes up to limit (for overview)
            query = self.db.query(Digest)

            # Apply filters
            if filtered_ids is not None:
                query = query.filter(Digest.id.in_(filtered_ids))

            digests = query.order_by(
                Digest.created_at.desc()
            ).limit(limit).all()

            for digest in digests:
                # Get feed info for clustering
                digest_feed_id, digest_feed_name = get_feed_name(digest.feed_run_id)

                node_id = f"d_{digest.id}"
                nodes[node_id] = GraphNode(
                    id=node_id,
                    type="digest",
                    label=digest.title[:50] if digest.title else f"Digest {digest.id}",
                    data={
                        "digest_id": digest.id,
                        "title": digest.title,
                        "created_at": digest.created_at.isoformat() if digest.created_at else None,
                        "source_id": digest.source_id,
                        "feed_id": digest_feed_id,
                        "feed_name": digest_feed_name,
                    }
                )

                # Add feed node as cluster anchor (only if source relationships requested)
                if digest_feed_id and "source" in rel_types:
                    feed_node_id = f"f_{digest_feed_id}"
                    if feed_node_id not in nodes:
                        nodes[feed_node_id] = GraphNode(
                            id=feed_node_id,
                            type="feed",
                            label=digest_feed_name or f"Feed {digest_feed_id}",
                            data={"feed_id": digest_feed_id, "name": digest_feed_name}
                        )
                    # Add edge from digest to feed
                    edges.append(GraphEdge(
                        source=node_id,
                        target=feed_node_id,
                        type="source",
                        score=0.5,
                    ))

                # Add tag nodes (only if tag relationships requested)
                if "tag" in rel_types:
                    for dt in digest.tags:
                        tag_node_id = f"t_{dt.tag.name}"
                        if tag_node_id not in nodes:
                            tag_count = self.db.query(DigestTag).filter(
                                DigestTag.tag_id == dt.tag_id
                            ).count()
                            nodes[tag_node_id] = GraphNode(
                                id=tag_node_id,
                                type="tag",
                                label=dt.tag.name,
                                data={"tag_id": dt.tag_id, "count": tag_count}
                            )
                        edges.append(GraphEdge(
                            source=node_id,
                            target=tag_node_id,
                            type="tag",
                            score=1.0,
                        ))

            # Get relationships between these digests
            digest_ids = [d.id for d in digests]
            relationships = self.db.query(DigestRelationship).filter(
                DigestRelationship.source_digest_id.in_(digest_ids),
                DigestRelationship.target_digest_id.in_(digest_ids),
                DigestRelationship.relationship_type.in_(rel_types),
                DigestRelationship.score >= min_sim
            ).all()

            for rel in relationships:
                edges.append(GraphEdge(
                    source=f"d_{rel.source_digest_id}",
                    target=f"d_{rel.target_digest_id}",
                    type=rel.relationship_type,
                    score=rel.score,
                    extra_data=rel.extra_data or {},
                ))

        return GraphData(
            nodes=list(nodes.values()),
            edges=edges,
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # RELATIONSHIP PRUNING
    # ═══════════════════════════════════════════════════════════════════════════════

    def prune_relationships(
        self,
        min_score: float | None = None,
        max_age_days: int | None = None,
        max_edges_per_digest: int | None = None,
    ) -> int:
        """Prune relationships below threshold or exceeding limits.

        Args:
            min_score: Remove relationships below this score
            max_age_days: Remove relationships older than this
            max_edges_per_digest: Keep only top N edges per digest

        Returns:
            Number of relationships deleted
        """
        from reconly_core.database.models import DigestRelationship

        deleted = 0

        # Delete by score
        if min_score:
            count = self.db.query(DigestRelationship).filter(
                DigestRelationship.score < min_score
            ).delete(synchronize_session=False)
            deleted += count

        # Delete by age
        if max_age_days:
            cutoff = datetime.utcnow() - timedelta(days=max_age_days)
            count = self.db.query(DigestRelationship).filter(
                DigestRelationship.created_at < cutoff
            ).delete(synchronize_session=False)
            deleted += count

        # Enforce max edges per digest (keep top scoring)
        if max_edges_per_digest:
            # Get all source digest IDs
            source_ids = self.db.query(
                DigestRelationship.source_digest_id
            ).distinct().all()

            for (source_id,) in source_ids:
                # Get relationships for this digest ordered by score
                rels = self.db.query(DigestRelationship).filter(
                    DigestRelationship.source_digest_id == source_id
                ).order_by(
                    DigestRelationship.score.desc()
                ).all()

                # Delete excess relationships
                for rel in rels[max_edges_per_digest:]:
                    self.db.delete(rel)
                    deleted += 1

        self.db.flush()
        logger.info(f"Pruned {deleted} relationships")
        return deleted

    def delete_relationships_for_digest(self, digest_id: int) -> int:
        """Delete all relationships for a specific digest.

        Args:
            digest_id: ID of the digest

        Returns:
            Number of relationships deleted
        """
        from reconly_core.database.models import DigestRelationship

        count = self.db.query(DigestRelationship).filter(
            (DigestRelationship.source_digest_id == digest_id) |
            (DigestRelationship.target_digest_id == digest_id)
        ).delete(synchronize_session=False)

        self.db.flush()
        return count

    # ═══════════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_statistics(self) -> dict:
        """Get statistics about the knowledge graph.

        Returns:
            Dictionary with graph statistics
        """
        from sqlalchemy import func
        from reconly_core.database.models import DigestRelationship, Digest

        total_relationships = self.db.query(
            func.count(DigestRelationship.id)
        ).scalar() or 0

        # Count by type
        by_type = self.db.query(
            DigestRelationship.relationship_type,
            func.count(DigestRelationship.id)
        ).group_by(DigestRelationship.relationship_type).all()

        type_counts = {rel_type: count for rel_type, count in by_type}

        # Average score
        avg_score = self.db.query(
            func.avg(DigestRelationship.score)
        ).scalar() or 0.0

        # Digests with relationships
        digests_with_rels = self.db.query(
            func.count(func.distinct(DigestRelationship.source_digest_id))
        ).scalar() or 0

        total_digests = self.db.query(func.count(Digest.id)).scalar() or 0

        return {
            "total_relationships": total_relationships,
            "by_type": type_counts,
            "average_score": round(float(avg_score), 3),
            "digests_with_relationships": digests_with_rels,
            "total_digests": total_digests,
            "coverage": round(digests_with_rels / max(total_digests, 1), 3),
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _embedding_to_list(self, embedding) -> list[float] | None:
        """Convert a pgvector embedding to a Python list.

        pgvector may return embeddings as numpy arrays or other array types.
        This normalizes to a Python list for consistent handling.

        Args:
            embedding: Embedding value from database (may be None, list, or ndarray)

        Returns:
            List of floats, or None if embedding is None
        """
        if embedding is None:
            return None
        if hasattr(embedding, 'tolist'):
            return embedding.tolist()
        return embedding

    def _create_relationship_if_not_exists(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
        score: float,
        extra_data: dict | None = None,
    ) -> int:
        """Create a relationship if it doesn't already exist.

        Args:
            source_id: Source digest ID
            target_id: Target digest ID
            rel_type: Relationship type
            score: Relationship score
            extra_data: Additional metadata

        Returns:
            1 if created, 0 if already exists
        """
        from reconly_core.database.models import DigestRelationship

        existing = self.db.query(DigestRelationship).filter(
            DigestRelationship.source_digest_id == source_id,
            DigestRelationship.target_digest_id == target_id,
            DigestRelationship.relationship_type == rel_type
        ).first()

        if existing:
            return 0

        rel = DigestRelationship(
            source_digest_id=source_id,
            target_digest_id=target_id,
            relationship_type=rel_type,
            score=score,
            extra_data=extra_data or {},
        )
        self.db.add(rel)
        return 1
