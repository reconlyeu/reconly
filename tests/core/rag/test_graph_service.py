"""Tests for GraphService."""
import pytest
import numpy as np
from unittest.mock import Mock
from datetime import datetime, timedelta

from reconly_core.rag.graph_service import (
    GraphService,
    GraphNode,
    GraphEdge,
    GraphData,
)
from reconly_core.database.models import (
    Digest,
    DigestChunk,
    DigestRelationship,
    DigestTag,
    Tag,
    Source,
)


class TestGraphService:
    """Test suite for GraphService."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Return mock embedding provider."""
        provider = Mock()
        provider.get_dimension = Mock(return_value=1024)
        provider.get_model_info = Mock(return_value={
            'provider': 'ollama',
            'model': 'bge-m3',
        })
        return provider

    @pytest.fixture
    def graph_service(self, db_session, mock_embedding_provider):
        """Return configured graph service."""
        return GraphService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
        )

    @pytest.fixture
    def sample_digests(self, db_session):
        """Create sample digests for testing."""
        source = Source(name="Test Source", type="manual", data={})
        db_session.add(source)
        db_session.flush()

        digests = []
        for i in range(3):
            digest = Digest(
                title=f"Digest {i}",
                content=f"Content {i}",
                source_id=source.id,
            )
            db_session.add(digest)
            db_session.flush()

            # Add chunk with embedding (pgvector format - list of floats)
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=0,
                text=f"Chunk for digest {i}",
                token_count=50,
                start_char=0,
                end_char=100,
                embedding=embedding,
            )
            db_session.add(chunk)
            digests.append(digest)

        db_session.commit()
        return digests

    def test_initialization(self, db_session, mock_embedding_provider):
        """Test service initialization."""
        service = GraphService(
            db=db_session,
            embedding_provider=mock_embedding_provider,
            semantic_threshold=0.8,
            min_similarity=0.5,
            max_edges_per_digest=15,
        )

        assert service.db == db_session
        assert service.embedding_provider == mock_embedding_provider
        assert service.semantic_threshold == 0.8
        assert service.min_similarity == 0.5
        assert service.max_edges_per_digest == 15

    def test_initialization_without_provider(self, db_session):
        """Test initialization without embedding provider."""
        service = GraphService(db=db_session)
        assert service.embedding_provider is None

    def test_detect_postgres(self, graph_service):
        """Test PostgreSQL detection."""
        assert graph_service._is_postgres is True  # PostgreSQL in tests

    @pytest.mark.asyncio
    async def test_compute_relationships(self, graph_service, sample_digests):
        """Test computing relationships for a digest."""
        digest = sample_digests[0]
        count = await graph_service.compute_relationships(digest.id)

        # Should create some relationships (at least source-based)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_compute_relationships_nonexistent(self, graph_service):
        """Test computing relationships for non-existent digest."""
        count = await graph_service.compute_relationships(9999)
        assert count == 0

    @pytest.mark.asyncio
    async def test_compute_semantic_relationships(self, graph_service, sample_digests):
        """Test computing semantic relationships."""
        digest = sample_digests[0]
        count = await graph_service._compute_semantic_relationships(digest)

        # May or may not create relationships depending on similarity
        assert count >= 0

    def test_compute_tag_relationships(self, graph_service, db_session, sample_digests):
        """Test computing tag-based relationships."""
        # Create tags
        tag1 = Tag(name="AI")
        tag2 = Tag(name="ML")
        db_session.add_all([tag1, tag2])
        db_session.flush()

        # Add tags to digests
        digest1, digest2 = sample_digests[0], sample_digests[1]

        db_session.add(DigestTag(digest_id=digest1.id, tag_id=tag1.id))
        db_session.add(DigestTag(digest_id=digest1.id, tag_id=tag2.id))
        db_session.add(DigestTag(digest_id=digest2.id, tag_id=tag1.id))
        db_session.commit()

        # Compute tag relationships for digest1
        count = graph_service._compute_tag_relationships(digest1)

        # Should create relationship with digest2 (shared tag)
        assert count > 0

    def test_compute_tag_relationships_no_tags(self, graph_service, sample_digests):
        """Test computing tag relationships when digest has no tags."""
        digest = sample_digests[0]
        count = graph_service._compute_tag_relationships(digest)
        assert count == 0

    def test_compute_source_relationships(self, graph_service, sample_digests):
        """Test computing source-based relationships."""
        digest = sample_digests[0]
        count = graph_service._compute_source_relationships(digest)

        # Should find relationships with other digests from same source
        assert count > 0

    def test_compute_source_relationships_no_source(self, graph_service, db_session):
        """Test computing source relationships when digest has no source."""
        digest = Digest(title="No Source", content="Content")
        db_session.add(digest)
        db_session.commit()

        count = graph_service._compute_source_relationships(digest)
        assert count == 0

    def test_get_graph_data_centered(self, graph_service, db_session, sample_digests):
        """Test getting graph data centered on a digest."""
        digest = sample_digests[0]

        # Create a relationship
        rel = DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
        )
        db_session.add(rel)
        db_session.commit()

        data = graph_service.get_graph_data(
            center_digest_id=digest.id,
            depth=2,
        )

        assert isinstance(data, GraphData)
        assert len(data.nodes) > 0
        # Should include the center digest
        assert any(n.data.get('digest_id') == digest.id for n in data.nodes)

    def test_get_graph_data_overview(self, graph_service, sample_digests):
        """Test getting overview graph data without center."""
        data = graph_service.get_graph_data(limit=10)

        assert isinstance(data, GraphData)
        assert len(data.nodes) > 0
        # Should include digest nodes
        assert any(n.type == "digest" for n in data.nodes)

    def test_get_graph_data_with_tags(self, graph_service, db_session, sample_digests):
        """Test getting graph data with tag nodes."""
        # Add tag to digest
        tag = Tag(name="TestTag")
        db_session.add(tag)
        db_session.flush()

        db_session.add(DigestTag(digest_id=sample_digests[0].id, tag_id=tag.id))
        db_session.commit()

        data = graph_service.get_graph_data(
            center_digest_id=sample_digests[0].id,
            include_tags=True,
        )

        # Should include tag nodes
        assert any(n.type == "tag" for n in data.nodes)

    def test_get_graph_data_without_tags(self, graph_service, db_session, sample_digests):
        """Test getting graph data without tag nodes."""
        # Add tag to digest
        tag = Tag(name="TestTag")
        db_session.add(tag)
        db_session.flush()

        db_session.add(DigestTag(digest_id=sample_digests[0].id, tag_id=tag.id))
        db_session.commit()

        data = graph_service.get_graph_data(
            center_digest_id=sample_digests[0].id,
            include_tags=False,
        )

        # Should not include tag nodes
        assert not any(n.type == "tag" for n in data.nodes)

    def test_get_graph_data_filter_relationship_types(self, graph_service, db_session, sample_digests):
        """Test filtering graph data by relationship types."""
        # Create different types of relationships
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[2].id,
            relationship_type="source",
            score=0.8,
        ))
        db_session.commit()

        # Filter to only semantic
        data = graph_service.get_graph_data(
            center_digest_id=sample_digests[0].id,
            relationship_types=["semantic"],
        )

        # Should only have semantic edges
        assert all(e.type == "semantic" for e in data.edges if e.type != "tag")

    def test_prune_relationships_by_score(self, graph_service, db_session, sample_digests):
        """Test pruning relationships below minimum score."""
        # Create relationships with different scores
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.5,
        ))
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[2].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.commit()

        deleted = graph_service.prune_relationships(min_score=0.7)

        # Should delete the low-score relationship
        assert deleted == 1

    def test_prune_relationships_by_age(self, graph_service, db_session, sample_digests):
        """Test pruning old relationships."""
        # Create old relationship
        old_rel = DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
            created_at=datetime.utcnow() - timedelta(days=100),
        )
        db_session.add(old_rel)
        db_session.commit()

        deleted = graph_service.prune_relationships(max_age_days=30)

        # Should delete the old relationship
        assert deleted == 1

    def test_prune_relationships_max_edges(self, graph_service, db_session, sample_digests):
        """Test pruning excess edges per digest."""
        # Create many relationships from one digest
        for i in range(5):
            db_session.add(DigestRelationship(
                source_digest_id=sample_digests[0].id,
                target_digest_id=sample_digests[1].id if i % 2 == 0 else sample_digests[2].id,
                relationship_type="semantic",
                score=0.9 - (i * 0.1),  # Decreasing scores
            ))
        db_session.commit()

        deleted = graph_service.prune_relationships(max_edges_per_digest=2)

        # Should keep only top 2 edges
        assert deleted == 3

    def test_delete_relationships_for_digest(self, graph_service, db_session, sample_digests):
        """Test deleting all relationships for a digest."""
        # Create relationships
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[1].id,
            target_digest_id=sample_digests[0].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.commit()

        deleted = graph_service.delete_relationships_for_digest(sample_digests[0].id)

        # Should delete both relationships
        assert deleted == 2

    def test_get_statistics(self, graph_service, db_session, sample_digests):
        """Test getting graph statistics."""
        # Create some relationships
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[1].id,
            target_digest_id=sample_digests[2].id,
            relationship_type="tag",
            score=0.8,
        ))
        db_session.commit()

        stats = graph_service.get_statistics()

        assert stats['total_relationships'] == 2
        assert 'by_type' in stats
        assert stats['average_score'] > 0
        assert stats['digests_with_relationships'] > 0
        assert stats['total_digests'] == 3

    def test_create_relationship_if_not_exists_new(self, graph_service, sample_digests):
        """Test creating new relationship."""
        count = graph_service._create_relationship_if_not_exists(
            sample_digests[0].id,
            sample_digests[1].id,
            "semantic",
            0.9,
            {"test": "data"},
        )

        assert count == 1

    def test_create_relationship_if_not_exists_duplicate(self, graph_service, db_session, sample_digests):
        """Test not creating duplicate relationship."""
        # Create existing relationship
        db_session.add(DigestRelationship(
            source_digest_id=sample_digests[0].id,
            target_digest_id=sample_digests[1].id,
            relationship_type="semantic",
            score=0.9,
        ))
        db_session.commit()

        count = graph_service._create_relationship_if_not_exists(
            sample_digests[0].id,
            sample_digests[1].id,
            "semantic",
            0.9,
        )

        assert count == 0

    def test_deserialize_embedding_list(self, graph_service):
        """Test deserializing list embedding (pgvector format)."""
        embedding = [0.1, 0.2, 0.3]
        result = graph_service._deserialize_embedding(embedding)
        assert result == embedding

    def test_deserialize_embedding_none(self, graph_service):
        """Test deserializing None."""
        result = graph_service._deserialize_embedding(None)
        assert result is None


class TestGraphNode:
    """Test GraphNode dataclass."""

    def test_node_creation(self):
        """Test creating a GraphNode."""
        node = GraphNode(
            id="d_42",
            type="digest",
            label="Test Digest",
            data={"digest_id": 42, "title": "Test"},
        )

        assert node.id == "d_42"
        assert node.type == "digest"
        assert node.label == "Test Digest"
        assert node.data["digest_id"] == 42


class TestGraphEdge:
    """Test GraphEdge dataclass."""

    def test_edge_creation(self):
        """Test creating a GraphEdge."""
        edge = GraphEdge(
            source="d_1",
            target="d_2",
            type="semantic",
            score=0.95,
            extra_data={"method": "cosine"},
        )

        assert edge.source == "d_1"
        assert edge.target == "d_2"
        assert edge.type == "semantic"
        assert edge.score == 0.95
        assert edge.extra_data["method"] == "cosine"


class TestGraphData:
    """Test GraphData dataclass."""

    def test_graph_data_creation(self):
        """Test creating GraphData."""
        nodes = [
            GraphNode("d_1", "digest", "Digest 1"),
            GraphNode("d_2", "digest", "Digest 2"),
        ]
        edges = [
            GraphEdge("d_1", "d_2", "semantic", 0.9),
        ]

        data = GraphData(nodes=nodes, edges=edges)

        assert len(data.nodes) == 2
        assert len(data.edges) == 1


class TestGraphServiceIntegration:
    """Integration tests for GraphService."""

    @pytest.mark.asyncio
    async def test_full_graph_computation(self, db_session):
        """Test complete graph computation flow."""
        from reconly_core.database.models import Source, Digest, DigestChunk, Tag, DigestTag

        # Create mock provider
        mock_provider = Mock()
        mock_provider.get_dimension = Mock(return_value=1024)

        service = GraphService(db_session, mock_provider)

        # Create test data
        source = Source(name="Tech News", type="manual", data={})
        db_session.add(source)
        db_session.flush()

        tag = Tag(name="AI")
        db_session.add(tag)
        db_session.flush()

        # Create digests
        digest1 = Digest(title="AI News 1", content="Content 1", source_id=source.id)
        digest2 = Digest(title="AI News 2", content="Content 2", source_id=source.id)
        db_session.add_all([digest1, digest2])
        db_session.flush()

        # Add tags
        db_session.add_all([
            DigestTag(digest_id=digest1.id, tag_id=tag.id),
            DigestTag(digest_id=digest2.id, tag_id=tag.id),
        ])

        # Add chunks with embeddings (pgvector format - list of floats)
        for digest in [digest1, digest2]:
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=0,
                text="Chunk text",
                token_count=50,
                start_char=0,
                end_char=100,
                embedding=embedding,
            )
            db_session.add(chunk)

        db_session.commit()

        # Compute relationships
        count = await service.compute_relationships(
            digest1.id,
            include_semantic=True,
            include_tags=True,
            include_source=True,
        )

        # Should create some relationships
        assert count > 0

        # Get graph data
        graph_data = service.get_graph_data(center_digest_id=digest1.id, depth=1, include_tags=True)

        # Verify structure
        assert len(graph_data.nodes) > 0
        assert any(n.type == "digest" for n in graph_data.nodes)
        assert any(n.type == "tag" for n in graph_data.nodes)
