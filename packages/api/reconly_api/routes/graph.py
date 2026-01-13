"""Graph API endpoints for Knowledge Graph visualization."""
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.graph import (
    GraphResponse,
    GraphNode,
    GraphEdge,
    GraphStatsResponse,
    ComputeRelationshipsRequest,
    ComputeRelationshipsResponse,
)

router = APIRouter()


@router.get("/nodes/", response_model=GraphResponse)
async def get_graph_nodes(
    center_digest_id: int | None = Query(
        None,
        description="Center the graph on this digest ID"
    ),
    depth: int = Query(
        2,
        ge=1,
        le=5,
        description="Number of relationship hops to traverse (1-5)"
    ),
    min_similarity: float = Query(
        0.6,
        ge=0.0,
        le=1.0,
        description="Minimum relationship score to include (0.0 to 1.0)"
    ),
    include_tags: bool = Query(
        True,
        description="Whether to include tag nodes in the graph"
    ),
    relationship_types: list[str] | None = Query(
        None,
        description="Filter by relationship types (semantic, tag, source)"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of nodes to return (1-500)"
    ),
    feed_id: int | None = Query(
        None,
        description="Filter digests by feed ID"
    ),
    from_date: str | None = Query(
        None,
        description="Filter digests created on or after this date (ISO format, e.g. 2025-01-01)"
    ),
    to_date: str | None = Query(
        None,
        description="Filter digests created on or before this date (ISO format, e.g. 2025-12-31)"
    ),
    tags: str | None = Query(
        None,
        description="Filter digests by tags (comma-separated, e.g. 'ai,tech')"
    ),
    db: Session = Depends(get_db),
) -> GraphResponse:
    """
    Get knowledge graph data for visualization.

    Returns nodes (digests, tags) and edges (relationships) that can be
    rendered by a graph visualization library.

    **Query Parameters:**
    - `center_digest_id`: Start from a specific digest and expand outward
    - `depth`: How many relationship hops to traverse (default: 2)
    - `min_similarity`: Filter out weak relationships below this score
    - `include_tags`: Whether to show tag nodes connected to digests
    - `relationship_types`: Only include specific relationship types
    - `limit`: Maximum nodes to return (for performance)

    **Response:**
    - `nodes`: List of graph nodes (digests, tags, sources)
    - `edges`: List of edges connecting nodes with relationship metadata

    **Node Types:**
    - `digest`: A digest document (id: "d_42")
    - `tag`: A tag (id: "t_ai")
    - `source`: A content source (id: "s_5")

    **Edge Types:**
    - `semantic`: Content similarity based on embeddings
    - `tag`: Shared tags between digests
    - `source`: Same content source

    **Example Response:**
    ```json
    {
      "nodes": [
        {"id": "d_42", "type": "digest", "label": "...", "data": {...}},
        {"id": "t_ai", "type": "tag", "label": "AI", "data": {"count": 15}}
      ],
      "edges": [
        {"source": "d_42", "target": "d_45", "type": "semantic", "score": 0.82}
      ]
    }
    ```
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.graph_service import GraphService

        # Initialize graph service
        embedding_provider = get_embedding_provider(db=db)
        graph_service = GraphService(
            db=db,
            embedding_provider=embedding_provider,
            min_similarity=min_similarity,
        )

        # Validate relationship types
        valid_types = ["semantic", "tag", "source"]
        if relationship_types:
            invalid = [t for t in relationship_types if t not in valid_types]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid relationship types: {invalid}. Valid: {valid_types}"
                )

        # Parse tags parameter
        tag_names = [t.strip() for t in tags.split(',')] if tags else None

        # Get graph data
        graph_data = graph_service.get_graph_data(
            center_digest_id=center_digest_id,
            depth=depth,
            min_similarity=min_similarity,
            include_tags=include_tags,
            relationship_types=relationship_types,
            limit=limit,
            feed_id=feed_id,
            from_date=from_date,
            to_date=to_date,
            tag_names=tag_names,
        )

        # Convert to response model
        nodes = [
            GraphNode(
                id=n.id,
                type=n.type,
                label=n.label,
                data=n.data,
            )
            for n in graph_data.nodes
        ]

        edges = [
            GraphEdge(
                source=e.source,
                target=e.target,
                type=e.type,
                score=e.score,
                extra_data=e.extra_data,
            )
            for e in graph_data.edges
        ]

        return GraphResponse(nodes=nodes, edges=edges)

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency for graph service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get graph data: {str(e)}"
        )


@router.get("/expand/{node_id}/", response_model=GraphResponse)
async def expand_node(
    node_id: str,
    depth: int = Query(
        1,
        ge=1,
        le=3,
        description="Number of relationship hops to traverse (1-3)"
    ),
    min_similarity: float = Query(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum relationship score to include (0.0 to 1.0)"
    ),
    db: Session = Depends(get_db),
) -> GraphResponse:
    """
    Expand a node to get its neighbors.

    Given a node ID (e.g., "d_42" for digest 42), returns the node and its
    connected neighbors up to the specified depth.

    **Path Parameters:**
    - `node_id`: Node identifier (format: "d_{digest_id}" for digests)

    **Query Parameters:**
    - `depth`: How many relationship hops to traverse (default: 1)
    - `min_similarity`: Filter out weak relationships below this score

    **Example:**
    ```
    GET /graph/expand/d_42/?depth=1&min_similarity=0.6
    ```
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.graph_service import GraphService

        # Parse node ID to get digest ID
        if not node_id.startswith("d_"):
            raise HTTPException(
                status_code=400,
                detail=f"Only digest nodes can be expanded. Expected 'd_{{id}}', got '{node_id}'"
            )

        try:
            digest_id = int(node_id[2:])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid node ID format: '{node_id}'"
            )

        # Initialize graph service
        embedding_provider = get_embedding_provider(db=db)
        graph_service = GraphService(
            db=db,
            embedding_provider=embedding_provider,
            min_similarity=min_similarity,
        )

        # Get graph data centered on this digest
        graph_data = graph_service.get_graph_data(
            center_digest_id=digest_id,
            depth=depth,
            min_similarity=min_similarity,
            include_tags=True,
            limit=50,  # Reasonable limit for expansion
        )

        # Convert to response model
        nodes = [
            GraphNode(
                id=n.id,
                type=n.type,
                label=n.label,
                data=n.data,
            )
            for n in graph_data.nodes
        ]

        edges = [
            GraphEdge(
                source=e.source,
                target=e.target,
                type=e.type,
                score=e.score,
                extra_data=e.extra_data,
            )
            for e in graph_data.edges
        ]

        return GraphResponse(nodes=nodes, edges=edges)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to expand node: {str(e)}"
        )


@router.get("/stats/", response_model=GraphStatsResponse)
async def get_graph_stats(
    db: Session = Depends(get_db),
) -> GraphStatsResponse:
    """
    Get statistics about the knowledge graph.

    Returns metrics about the graph including:
    - Total number of relationships
    - Breakdown by relationship type
    - Average relationship score
    - Coverage (fraction of digests with relationships)
    """
    try:
        from reconly_core.rag.graph_service import GraphService

        graph_service = GraphService(db=db)
        stats = graph_service.get_statistics()

        return GraphStatsResponse(
            total_relationships=stats["total_relationships"],
            by_type=stats["by_type"],
            average_score=stats["average_score"],
            digests_with_relationships=stats["digests_with_relationships"],
            total_digests=stats["total_digests"],
            coverage=stats["coverage"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get graph stats: {str(e)}"
        )


@router.post("/compute/", response_model=ComputeRelationshipsResponse)
async def compute_relationships(
    request: ComputeRelationshipsRequest,
    db: Session = Depends(get_db),
) -> ComputeRelationshipsResponse:
    """
    Compute relationships for a specific digest.

    Triggers relationship computation for semantic, tag, and source
    relationships. The computation runs synchronously for immediate feedback.

    **Request Body:**
    - `digest_id`: ID of the digest to compute relationships for
    - `include_semantic`: Whether to compute semantic (embedding) relationships
    - `include_tags`: Whether to compute tag-based relationships
    - `include_source`: Whether to compute source-based relationships

    **Note:** For bulk computation, use the background job endpoint instead.
    """
    try:
        from reconly_core.rag import get_embedding_provider
        from reconly_core.rag.graph_service import GraphService
        from reconly_core.database.models import Digest

        # Verify digest exists
        digest = db.query(Digest).filter(Digest.id == request.digest_id).first()
        if not digest:
            raise HTTPException(
                status_code=404,
                detail=f"Digest {request.digest_id} not found"
            )

        # Initialize graph service
        embedding_provider = get_embedding_provider(db=db)
        graph_service = GraphService(
            db=db,
            embedding_provider=embedding_provider,
        )

        # Compute relationships
        count = await graph_service.compute_relationships(
            digest_id=request.digest_id,
            include_semantic=request.include_semantic,
            include_tags=request.include_tags,
            include_source=request.include_source,
        )

        db.commit()

        return ComputeRelationshipsResponse(
            digest_id=request.digest_id,
            relationships_created=count,
            message=f"Successfully computed relationships for digest {request.digest_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute relationships: {str(e)}"
        )


@router.post("/compute-all/")
async def compute_all_relationships(
    background_tasks: BackgroundTasks,
    include_semantic: bool = Query(True, description="Compute semantic relationships"),
    include_tags: bool = Query(True, description="Compute tag relationships"),
    include_source: bool = Query(True, description="Compute source relationships"),
    force: bool = Query(False, description="Recompute even if relationships exist"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Compute relationships for all digests (background job).

    This endpoint triggers a background job to compute relationships
    for all digests that don't have relationships yet (or all if force=true).

    Returns immediately with job status. Use /stats/ to monitor progress.

    **Query Parameters:**
    - `include_semantic`: Whether to compute embedding-based relationships
    - `include_tags`: Whether to compute tag-based relationships
    - `include_source`: Whether to compute source-based relationships
    - `force`: If true, recompute relationships even if they exist
    """
    from reconly_core.database.models import Digest, DigestRelationship
    from sqlalchemy import func

    # Count digests to process
    if force:
        digests_to_process = db.query(func.count(Digest.id)).scalar() or 0
    else:
        # Count digests without relationships
        digests_with_rels = db.query(
            func.distinct(DigestRelationship.source_digest_id)
        ).subquery()
        digests_to_process = db.query(func.count(Digest.id)).filter(
            ~Digest.id.in_(db.query(digests_with_rels))
        ).scalar() or 0

    if digests_to_process == 0:
        return {
            "status": "no_work",
            "message": "No digests need relationship computation",
            "digests_to_process": 0,
        }

    # Add background task
    background_tasks.add_task(
        _compute_relationships_background,
        include_semantic=include_semantic,
        include_tags=include_tags,
        include_source=include_source,
        force=force,
    )

    return {
        "status": "started",
        "message": f"Background job started for {digests_to_process} digests",
        "digests_to_process": digests_to_process,
    }


async def _compute_relationships_background(
    include_semantic: bool,
    include_tags: bool,
    include_source: bool,
    force: bool,
):
    """Background task to compute relationships for all digests."""
    import logging
    from reconly_api.dependencies import SessionLocal
    from reconly_core.database.models import Digest, DigestRelationship
    from reconly_core.rag import get_embedding_provider
    from reconly_core.rag.graph_service import GraphService

    logger = logging.getLogger(__name__)
    logger.info("Starting background relationship computation")

    db = SessionLocal()
    try:
        embedding_provider = get_embedding_provider(db=db)
        graph_service = GraphService(db=db, embedding_provider=embedding_provider)

        # Get digests to process
        if force:
            digests = db.query(Digest).all()
        else:
            # Get digests without relationships
            digests_with_rels = db.query(
                DigestRelationship.source_digest_id
            ).distinct().subquery()
            digests = db.query(Digest).filter(
                ~Digest.id.in_(db.query(digests_with_rels))
            ).all()

        total = len(digests)
        processed = 0
        total_relationships = 0

        for digest in digests:
            try:
                count = await graph_service.compute_relationships(
                    digest_id=digest.id,
                    include_semantic=include_semantic,
                    include_tags=include_tags,
                    include_source=include_source,
                )
                total_relationships += count
                processed += 1

                # Commit periodically
                if processed % 10 == 0:
                    db.commit()
                    logger.info(f"Processed {processed}/{total} digests")

            except Exception as e:
                logger.error(f"Error processing digest {digest.id}: {e}")
                continue

        db.commit()
        logger.info(
            f"Completed relationship computation: {processed}/{total} digests, "
            f"{total_relationships} relationships created"
        )

    except Exception as e:
        logger.error(f"Background relationship computation failed: {e}")
        db.rollback()
    finally:
        db.close()


@router.delete("/relationships/{digest_id}/")
async def delete_digest_relationships(
    digest_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete all relationships for a specific digest.

    Removes both incoming and outgoing relationships.
    Useful for recomputing relationships from scratch.
    """
    try:
        from reconly_core.rag.graph_service import GraphService
        from reconly_core.database.models import Digest

        # Verify digest exists
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            raise HTTPException(
                status_code=404,
                detail=f"Digest {digest_id} not found"
            )

        graph_service = GraphService(db=db)
        count = graph_service.delete_relationships_for_digest(digest_id)
        db.commit()

        return {
            "digest_id": digest_id,
            "relationships_deleted": count,
            "message": f"Deleted {count} relationships for digest {digest_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete relationships: {str(e)}"
        )


@router.post("/prune/")
async def prune_relationships(
    min_score: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Remove relationships below this score"
    ),
    max_age_days: int | None = Query(
        None,
        ge=1,
        description="Remove relationships older than this many days"
    ),
    max_edges_per_digest: int | None = Query(
        None,
        ge=1,
        description="Keep only top N relationships per digest"
    ),
    db: Session = Depends(get_db),
) -> dict:
    """
    Prune relationships based on score, age, or edge count.

    Useful for cleaning up weak or stale relationships to improve
    graph visualization clarity.

    **Query Parameters:**
    - `min_score`: Remove relationships with score below this threshold
    - `max_age_days`: Remove relationships created more than N days ago
    - `max_edges_per_digest`: Keep only the top N scoring edges per digest
    """
    try:
        from reconly_core.rag.graph_service import GraphService

        if min_score is None and max_age_days is None and max_edges_per_digest is None:
            raise HTTPException(
                status_code=400,
                detail="At least one pruning parameter must be specified"
            )

        graph_service = GraphService(db=db)
        count = graph_service.prune_relationships(
            min_score=min_score,
            max_age_days=max_age_days,
            max_edges_per_digest=max_edges_per_digest,
        )
        db.commit()

        return {
            "relationships_pruned": count,
            "message": f"Pruned {count} relationships",
            "criteria": {
                "min_score": min_score,
                "max_age_days": max_age_days,
                "max_edges_per_digest": max_edges_per_digest,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prune relationships: {str(e)}"
        )
