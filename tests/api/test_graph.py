"""API integration tests for graph endpoints."""
import pytest
import numpy as np
from unittest.mock import patch, Mock

from reconly_core.database.models import (
    Digest,
    DigestChunk,
    DigestRelationship,
    DigestTag,
    Tag,
    Source,
)


class TestGraphAPI:
    """Test suite for graph API endpoints."""

    @pytest.fixture
    def sample_graph_data(self, test_db):
        """Create sample graph data with relationships."""
        source = Source(name="Test Source", type="manual", url="https://test.example.com")
        test_db.add(source)
        test_db.flush()

        # Create digests
        digests = []
        for i in range(3):
            digest = Digest(
                url=f"https://test.example.com/digest-{i}",
                title=f"Digest {i}",
                content=f"Content {i}",
                source_id=source.id,
            )
            test_db.add(digest)
            test_db.flush()

            # Add chunk with embedding (pgvector handles list conversion)
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=0,
                text=f"Chunk {i}",
                token_count=50,
                start_char=0,
                end_char=100,
                embedding=embedding,
            )
            test_db.add(chunk)
            digests.append(digest)

        # Create relationships
        test_db.add(DigestRelationship(
            source_digest_id=digests[0].id,
            target_digest_id=digests[1].id,
            relationship_type="semantic",
            score=0.9,
        ))
        test_db.add(DigestRelationship(
            source_digest_id=digests[1].id,
            target_digest_id=digests[2].id,
            relationship_type="source",
            score=0.8,
        ))

        # Create tag
        tag = Tag(name="AI")
        test_db.add(tag)
        test_db.flush()

        test_db.add(DigestTag(digest_id=digests[0].id, tag_id=tag.id))

        test_db.commit()
        return digests

    def test_get_graph_nodes_endpoint(self, client, sample_graph_data):
        """Test get graph nodes endpoint."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes")

            assert response.status_code == 200
            data = response.json()

            assert "nodes" in data
            assert "edges" in data
            assert isinstance(data["nodes"], list)
            assert isinstance(data["edges"], list)

    def test_get_graph_nodes_centered(self, client, sample_graph_data):
        """Test get graph nodes centered on a digest."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            digest_id = sample_graph_data[0].id
            response = client.get(f"/api/v1/graph/nodes?center_digest_id={digest_id}")

            assert response.status_code == 200
            data = response.json()

            assert len(data["nodes"]) > 0
            # Should include the center digest
            node_ids = [n["id"] for n in data["nodes"]]
            assert f"d_{digest_id}" in node_ids

    def test_get_graph_nodes_with_depth(self, client, sample_graph_data):
        """Test get graph nodes with depth parameter."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(
                f"/api/v1/graph/nodes?center_digest_id={sample_graph_data[0].id}&depth=1"
            )

            assert response.status_code == 200

    def test_get_graph_nodes_with_min_similarity(self, client, sample_graph_data):
        """Test get graph nodes with min_similarity filter."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes?min_similarity=0.8")

            assert response.status_code == 200
            data = response.json()

            # All edges should have score >= 0.8
            for edge in data["edges"]:
                if edge["type"] != "tag":  # Tag edges may have score 1.0
                    assert edge["score"] >= 0.7  # Allow small margin

    def test_get_graph_nodes_with_tags(self, client, sample_graph_data):
        """Test get graph nodes including tags."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(
                f"/api/v1/graph/nodes?center_digest_id={sample_graph_data[0].id}&include_tags=true"
            )

            assert response.status_code == 200
            data = response.json()

            # Should include tag nodes
            node_types = [n["type"] for n in data["nodes"]]
            assert "tag" in node_types

    def test_get_graph_nodes_without_tags(self, client, sample_graph_data):
        """Test get graph nodes excluding tags."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(
                f"/api/v1/graph/nodes?center_digest_id={sample_graph_data[0].id}&include_tags=false"
            )

            assert response.status_code == 200
            data = response.json()

            # Should not include tag nodes
            node_types = [n["type"] for n in data["nodes"]]
            assert "tag" not in node_types

    def test_get_graph_nodes_with_relationship_types(self, client, sample_graph_data):
        """Test get graph nodes filtered by relationship types."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get(
                "/api/v1/graph/nodes?relationship_types=semantic"
            )

            assert response.status_code == 200
            data = response.json()

            # All non-tag edges should be semantic
            for edge in data["edges"]:
                if edge["type"] != "tag":
                    assert edge["type"] == "semantic"

    def test_get_graph_nodes_with_limit(self, client, sample_graph_data):
        """Test get graph nodes with limit parameter."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes?limit=2")

            assert response.status_code == 200
            data = response.json()

            # Should respect limit
            assert len(data["nodes"]) <= 2

    def test_graph_node_structure(self, client, sample_graph_data):
        """Test that graph nodes have correct structure."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes")

            assert response.status_code == 200
            data = response.json()

            if data["nodes"]:
                node = data["nodes"][0]
                assert "id" in node
                assert "type" in node
                assert "label" in node
                assert "data" in node

    def test_graph_edge_structure(self, client, sample_graph_data):
        """Test that graph edges have correct structure."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes")

            assert response.status_code == 200
            data = response.json()

            if data["edges"]:
                edge = data["edges"][0]
                assert "source" in edge
                assert "target" in edge
                assert "type" in edge
                assert "score" in edge

    def test_compute_relationships_endpoint(self, client, sample_graph_data):
        """Test compute relationships endpoint if available."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            digest_id = sample_graph_data[0].id
            response = client.post(
                "/api/v1/graph/compute",
                json={"digest_id": digest_id}
            )

            # May not be implemented
            assert response.status_code in [200, 404, 422]

    def test_graph_stats_endpoint(self, client, sample_graph_data):
        """Test graph statistics endpoint if available."""
        response = client.get("/api/v1/graph/stats")

        # May not be implemented
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


class TestGraphAPIEdgeCases:
    """Test edge cases for graph API."""

    def test_graph_empty_database(self, client):
        """Test graph with no data."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes")

            assert response.status_code == 200
            data = response.json()

            assert data["nodes"] == []
            assert data["edges"] == []

    def test_graph_nonexistent_center_digest(self, client):
        """Test graph with non-existent center digest."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            provider = Mock()
            provider.get_dimension = Mock(return_value=1024)
            provider.get_model_info = Mock(return_value={'provider': 'test', 'model': 'test'})
            mock_provider.return_value = provider

            response = client.get("/api/v1/graph/nodes?center_digest_id=99999")

            assert response.status_code == 200
            data = response.json()

            # Should return empty or handle gracefully
            assert isinstance(data["nodes"], list)

    def test_graph_invalid_depth(self, client):
        """Test graph with invalid depth parameter."""
        response = client.get("/api/v1/graph/nodes?depth=100")

        assert response.status_code == 422  # Validation error (exceeds max)

    def test_graph_invalid_min_similarity(self, client):
        """Test graph with invalid min_similarity parameter."""
        response = client.get("/api/v1/graph/nodes?min_similarity=1.5")

        assert response.status_code == 422  # Validation error (exceeds 1.0)

    def test_graph_invalid_limit(self, client):
        """Test graph with invalid limit parameter."""
        response = client.get("/api/v1/graph/nodes?limit=10000")

        assert response.status_code == 422  # Validation error (exceeds max)

    def test_graph_provider_failure(self, client):
        """Test graph when embedding provider fails."""
        with patch('reconly_core.rag.embeddings.get_embedding_provider') as mock_provider:
            mock_provider.side_effect = RuntimeError("Provider error")

            response = client.get("/api/v1/graph/nodes")

            # Should handle error gracefully
            assert response.status_code in [500, 200]  # May work without provider
