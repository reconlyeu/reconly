"""Shared fixtures for RAG tests.

These fixtures provide common mock objects used across RAG test modules.
Individual test classes can still define their own fixtures if they need
specific behavior different from these defaults.
"""
import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock

from reconly_core.database.models import Digest, DigestChunk, Source


# =============================================================================
# Mock Provider Fixtures
# =============================================================================

@pytest.fixture
def mock_embedding_provider():
    """Return a mock embedding provider with standard 1024-dim output.

    The provider mocks:
    - embed_single: Returns a 1024-dimension embedding
    - embed_batch: Returns embeddings for multiple texts
    - get_dimension: Returns 1024
    - get_model_info: Returns ollama/bge-m3 config
    """
    provider = Mock()
    provider.embed_single = AsyncMock(return_value=[0.1] * 1024)
    provider.embed_batch = AsyncMock(
        side_effect=lambda texts: [[0.1] * 1024 for _ in texts]
    )
    provider.get_dimension = Mock(return_value=1024)
    provider.get_model_info = Mock(return_value={
        "provider": "ollama",
        "model": "bge-m3",
        "dimension": 1024,
    })
    return provider


@pytest.fixture
def mock_summarizer():
    """Return a mock summarizer for testing RAG responses.

    The summarizer mocks:
    - summarize: Returns a test summary with citations
    - get_model_info: Returns test model config
    """
    summarizer = Mock()
    summarizer.summarize = Mock(return_value={
        "summary": "This is a test answer with citations [1] and [2].",
        "model_info": {"model": "test-model"},
    })
    summarizer.get_model_info = Mock(return_value={"model": "test-model"})
    return summarizer


# =============================================================================
# RAG Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_digest_with_chunks(db_session):
    """Create a sample digest with embedded chunks for RAG testing.

    Creates:
    - A source
    - A digest linked to the source
    - 2 chunks with random 1024-dim embeddings
    """
    # Create source
    source = Source(
        name="RAG Test Source",
        type="manual",
        data={"url": "https://example.com/rag"},
    )
    db_session.add(source)
    db_session.flush()

    # Create digest
    digest = Digest(
        title="RAG Test Digest",
        content="This is a sample digest for RAG testing about AI and ML.",
        source_id=source.id,
        source_type="manual",
        summary="A digest about AI and machine learning.",
    )
    db_session.add(digest)
    db_session.flush()

    # Create chunks with random embeddings
    chunk_texts = [
        "First chunk about artificial intelligence concepts.",
        "Second chunk about machine learning techniques.",
    ]

    for idx, text in enumerate(chunk_texts):
        embedding = np.random.rand(1024).astype(np.float32).tolist()
        chunk = DigestChunk(
            digest_id=digest.id,
            chunk_index=idx,
            text=text,
            embedding=embedding,
            token_count=len(text.split()),
            start_char=idx * 100,
            end_char=(idx + 1) * 100,
        )
        db_session.add(chunk)

    db_session.commit()
    db_session.refresh(digest)
    return digest


@pytest.fixture
def sample_digests_with_chunks(db_session):
    """Create multiple digests with chunks for batch RAG testing.

    Creates 3 digests, each with 2 chunks.
    """
    digests = []

    # Create source
    source = Source(
        name="Batch RAG Test Source",
        type="manual",
        data={"url": "https://example.com/batch"},
    )
    db_session.add(source)
    db_session.flush()

    topics = ["artificial intelligence", "data science", "cloud computing"]

    for i, topic in enumerate(topics):
        digest = Digest(
            title=f"Digest about {topic}",
            content=f"Full content about {topic} and related concepts.",
            source_id=source.id,
            source_type="manual",
            summary=f"Summary of {topic}.",
        )
        db_session.add(digest)
        db_session.flush()

        # Add 2 chunks per digest
        for j in range(2):
            embedding = np.random.rand(1024).astype(np.float32).tolist()
            chunk = DigestChunk(
                digest_id=digest.id,
                chunk_index=j,
                text=f"Chunk {j} about {topic}",
                embedding=embedding,
                token_count=20,
                start_char=j * 100,
                end_char=(j + 1) * 100,
            )
            db_session.add(chunk)

        digests.append(digest)

    db_session.commit()
    for digest in digests:
        db_session.refresh(digest)

    return digests
