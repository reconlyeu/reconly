"""Graph-related schemas for Knowledge Graph API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    """A node in the knowledge graph.

    Nodes can represent:
    - digest: A digest document (id: "d_42")
    - tag: A tag (id: "t_ai")
    - source: A content source (id: "s_5")
    - feed: A feed cluster label (id: "f_3")
    """
    id: str = Field(..., description="Unique node identifier (e.g., 'd_42', 't_ai', 'f_3')")
    type: Literal["digest", "tag", "source", "feed"] = Field(
        ...,
        description="Node type"
    )
    label: str = Field(..., description="Display label for the node")
    data: dict = Field(
        default_factory=dict,
        description="Additional node metadata (varies by type)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "d_42",
                "type": "digest",
                "label": "Understanding Machine Learning Trends",
                "data": {
                    "digest_id": 42,
                    "title": "Understanding Machine Learning Trends",
                    "created_at": "2025-01-10T14:30:00",
                    "source_id": 5
                }
            }
        }
    )


class GraphEdge(BaseModel):
    """An edge connecting two nodes in the knowledge graph.

    Edge types:
    - semantic: Digests with similar content (cosine similarity > threshold)
    - tag: Digest is associated with a tag, or digests share tags
    - source: Digests from the same content source
    """
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: Literal["semantic", "tag", "source"] = Field(
        ...,
        description="Relationship type"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0.0 to 1.0)"
    )
    extra_data: dict = Field(
        default_factory=dict,
        description="Additional edge metadata"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "source": "d_42",
                "target": "d_45",
                "type": "semantic",
                "score": 0.82,
                "extra_data": {"method": "cosine_similarity"}
            }
        }
    )


class GraphResponse(BaseModel):
    """Response containing graph data for visualization.

    Contains nodes and edges that can be rendered by a graph
    visualization library (e.g., D3.js, vis.js, Cytoscape).
    """
    nodes: list[GraphNode] = Field(
        default_factory=list,
        description="List of graph nodes"
    )
    edges: list[GraphEdge] = Field(
        default_factory=list,
        description="List of graph edges"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "nodes": [
                    {
                        "id": "d_42",
                        "type": "digest",
                        "label": "Understanding Machine Learning Trends",
                        "data": {"digest_id": 42, "title": "Understanding Machine Learning Trends"}
                    },
                    {
                        "id": "d_45",
                        "type": "digest",
                        "label": "AI in Healthcare Applications",
                        "data": {"digest_id": 45, "title": "AI in Healthcare Applications"}
                    },
                    {
                        "id": "t_ai",
                        "type": "tag",
                        "label": "AI",
                        "data": {"tag_id": 3, "count": 15}
                    }
                ],
                "edges": [
                    {
                        "source": "d_42",
                        "target": "d_45",
                        "type": "semantic",
                        "score": 0.82,
                        "extra_data": {}
                    },
                    {
                        "source": "d_42",
                        "target": "t_ai",
                        "type": "tag",
                        "score": 1.0,
                        "extra_data": {}
                    }
                ]
            }
        }
    )


class GraphStatsResponse(BaseModel):
    """Statistics about the knowledge graph."""
    total_relationships: int = Field(
        ...,
        description="Total number of relationships in the graph"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of relationships by type"
    )
    average_score: float = Field(
        ...,
        description="Average relationship score"
    )
    digests_with_relationships: int = Field(
        ...,
        description="Number of digests that have at least one relationship"
    )
    total_digests: int = Field(
        ...,
        description="Total number of digests in the database"
    )
    coverage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of digests with relationships"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_relationships": 1250,
                "by_type": {
                    "semantic": 800,
                    "tag": 350,
                    "source": 100
                },
                "average_score": 0.72,
                "digests_with_relationships": 450,
                "total_digests": 500,
                "coverage": 0.9
            }
        }
    )


class ComputeRelationshipsRequest(BaseModel):
    """Request to compute relationships for a digest."""
    digest_id: int = Field(..., description="ID of the digest to compute relationships for")
    include_semantic: bool = Field(
        default=True,
        description="Whether to compute semantic relationships"
    )
    include_tags: bool = Field(
        default=True,
        description="Whether to compute tag relationships"
    )
    include_source: bool = Field(
        default=True,
        description="Whether to compute source relationships"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "digest_id": 42,
                "include_semantic": True,
                "include_tags": True,
                "include_source": True
            }
        }
    )


class ComputeRelationshipsResponse(BaseModel):
    """Response after computing relationships."""
    digest_id: int = Field(..., description="ID of the digest")
    relationships_created: int = Field(
        ...,
        description="Number of new relationships created"
    )
    message: str = Field(..., description="Status message")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "digest_id": 42,
                "relationships_created": 15,
                "message": "Successfully computed relationships for digest 42"
            }
        }
    )
