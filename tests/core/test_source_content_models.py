"""
Unit tests for SourceContent and SourceContentChunk models.

Tests the new RAG knowledge system models that store original source content
and their embeddings for semantic search.
"""
import hashlib
from datetime import datetime, timedelta

import pytest

from reconly_core.database.models import (
    Digest,
    DigestSourceItem,
    Source,
    SourceContent,
    SourceContentChunk,
)


# =============================================================================
# SourceContent Model Tests
# =============================================================================

@pytest.mark.database
@pytest.mark.unit
def test_create_source_content(db_session, sample_digest, sample_source):
    """Test creating a SourceContent record with all fields."""
    # Create a DigestSourceItem first (required relationship)
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
        item_title="Test Article",
        item_published_at=datetime.utcnow() - timedelta(hours=1),
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent
    content = "This is the original article content for RAG embedding."
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    fetched_at = datetime.utcnow()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content=content,
        content_hash=content_hash,
        content_length=len(content),
        fetched_at=fetched_at,
        embedding_status="pending",
        embedding_error=None,
    )
    db_session.add(source_content)
    db_session.commit()
    db_session.refresh(source_content)

    # Verify
    assert source_content.id is not None
    assert source_content.digest_source_item_id == digest_source_item.id
    assert source_content.content == content
    assert source_content.content_hash == content_hash
    assert source_content.content_length == len(content)
    assert source_content.fetched_at == fetched_at
    assert source_content.embedding_status == "pending"
    assert source_content.embedding_error is None
    assert source_content.created_at is not None


@pytest.mark.database
@pytest.mark.unit
def test_source_content_embedding_status_transitions(db_session, sample_digest, sample_source):
    """Test SourceContent embedding status lifecycle (pending -> completed/failed)."""
    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
        item_title="Test Article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent with pending status
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Test content",
        content_hash=hashlib.sha256(b"Test content").hexdigest(),
        content_length=12,
        fetched_at=datetime.utcnow(),
        embedding_status="pending",
    )
    db_session.add(source_content)
    db_session.commit()

    assert source_content.embedding_status == "pending"

    # Update to completed
    source_content.embedding_status = "completed"
    db_session.commit()
    db_session.refresh(source_content)

    assert source_content.embedding_status == "completed"

    # Update to failed with error
    source_content.embedding_status = "failed"
    source_content.embedding_error = "Embedding service timeout"
    db_session.commit()
    db_session.refresh(source_content)

    assert source_content.embedding_status == "failed"
    assert source_content.embedding_error == "Embedding service timeout"


@pytest.mark.database
@pytest.mark.unit
def test_source_content_to_dict(db_session, sample_digest, sample_source):
    """Test SourceContent.to_dict() method."""
    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent
    content = "Test content for to_dict"
    fetched_at = datetime.utcnow()
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        content_length=len(content),
        fetched_at=fetched_at,
        embedding_status="completed",
        embedding_error=None,
    )
    db_session.add(source_content)
    db_session.commit()
    db_session.refresh(source_content)

    # Test to_dict
    result = source_content.to_dict()

    assert result['id'] == source_content.id
    assert result['digest_source_item_id'] == digest_source_item.id
    assert result['content_hash'] == source_content.content_hash
    assert result['content_length'] == len(content)
    assert result['fetched_at'] == fetched_at.isoformat()
    assert result['embedding_status'] == "completed"
    assert result['embedding_error'] is None
    assert result['chunk_count'] == 0  # No chunks yet
    assert result['created_at'] == source_content.created_at.isoformat()


@pytest.mark.database
@pytest.mark.unit
def test_source_content_unique_constraint(db_session, sample_digest, sample_source):
    """Test that digest_source_item_id has unique constraint (one-to-one relationship)."""
    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create first SourceContent
    source_content1 = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content 1",
        content_hash=hashlib.sha256(b"Content 1").hexdigest(),
        content_length=9,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content1)
    db_session.commit()

    # Try to create duplicate SourceContent for same DigestSourceItem
    source_content2 = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content 2",
        content_hash=hashlib.sha256(b"Content 2").hexdigest(),
        content_length=9,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content2)

    # Should raise IntegrityError due to unique constraint
    with pytest.raises(Exception):  # SQLAlchemy IntegrityError
        db_session.commit()


# =============================================================================
# SourceContentChunk Model Tests
# =============================================================================

@pytest.mark.database
@pytest.mark.unit
def test_create_source_content_chunk(db_session, sample_digest, sample_source):
    """Test creating a SourceContentChunk with all fields."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Full article content here",
        content_hash=hashlib.sha256(b"Full article content here").hexdigest(),
        content_length=25,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunk
    chunk_text = "This is chunk 0"
    embedding_vector = [0.1] * 1024  # 1024-dimensional vector

    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text=chunk_text,
        embedding=embedding_vector,
        token_count=5,
        start_char=0,
        end_char=15,
        extra_data={"heading": "Introduction", "section": "1"},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    # Verify
    assert chunk.id is not None
    assert chunk.source_content_id == source_content.id
    assert chunk.chunk_index == 0
    assert chunk.text == chunk_text
    assert chunk.embedding is not None
    assert chunk.token_count == 5
    assert chunk.start_char == 0
    assert chunk.end_char == 15
    assert chunk.extra_data == {"heading": "Introduction", "section": "1"}
    assert chunk.created_at is not None


@pytest.mark.database
@pytest.mark.unit
def test_source_content_chunk_without_embedding(db_session, sample_digest, sample_source):
    """Test creating a SourceContentChunk without embedding (nullable)."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunk without embedding
    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk text",
        embedding=None,  # No embedding yet
        token_count=3,
        start_char=0,
        end_char=10,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    assert chunk.embedding is None
    assert chunk.text == "Chunk text"


@pytest.mark.database
@pytest.mark.unit
def test_source_content_chunk_to_dict(db_session, sample_digest, sample_source):
    """Test SourceContentChunk.to_dict() method."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunk with embedding
    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=2,
        text="Chunk 2 text",
        embedding=[0.5] * 1024,
        token_count=10,
        start_char=100,
        end_char=150,
        extra_data={"heading": "Chapter 2"},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    # Test to_dict
    result = chunk.to_dict()

    assert result['id'] == chunk.id
    assert result['source_content_id'] == source_content.id
    assert result['chunk_index'] == 2
    assert result['text'] == "Chunk 2 text"
    assert result['token_count'] == 10
    assert result['start_char'] == 100
    assert result['end_char'] == 150
    assert result['extra_data'] == {"heading": "Chapter 2"}
    assert result['has_embedding'] is True
    assert result['created_at'] == chunk.created_at.isoformat()


@pytest.mark.database
@pytest.mark.unit
def test_source_content_chunk_to_dict_no_embedding(db_session, sample_digest, sample_source):
    """Test SourceContentChunk.to_dict() when embedding is None."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Text",
        embedding=None,
        token_count=1,
        start_char=0,
        end_char=4,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    result = chunk.to_dict()
    assert result['has_embedding'] is False


# =============================================================================
# Relationship Tests
# =============================================================================

@pytest.mark.database
@pytest.mark.unit
def test_digest_source_item_to_source_content_relationship(db_session, sample_digest, sample_source):
    """Test one-to-one relationship between DigestSourceItem and SourceContent."""
    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
        item_title="Article Title",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.commit()

    # Refresh to load relationships
    db_session.refresh(digest_source_item)
    db_session.refresh(source_content)

    # Test forward relationship (DigestSourceItem -> SourceContent)
    assert digest_source_item.source_content is not None
    assert digest_source_item.source_content.id == source_content.id

    # Test backward relationship (SourceContent -> DigestSourceItem)
    assert source_content.digest_source_item is not None
    assert source_content.digest_source_item.id == digest_source_item.id


@pytest.mark.database
@pytest.mark.unit
def test_source_content_to_chunks_relationship(db_session, sample_digest, sample_source):
    """Test one-to-many relationship between SourceContent and SourceContentChunk."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Full content here",
        content_hash=hashlib.sha256(b"Full content here").hexdigest(),
        content_length=17,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create multiple chunks
    chunk1 = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk 0",
        token_count=2,
        start_char=0,
        end_char=7,
    )
    chunk2 = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=1,
        text="Chunk 1",
        token_count=2,
        start_char=8,
        end_char=15,
    )
    chunk3 = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=2,
        text="Chunk 2",
        token_count=2,
        start_char=16,
        end_char=17,
    )
    db_session.add_all([chunk1, chunk2, chunk3])
    db_session.commit()

    # Refresh to load relationships
    db_session.refresh(source_content)

    # Test relationship
    assert len(source_content.chunks) == 3
    assert source_content.chunks[0].chunk_index == 0
    assert source_content.chunks[1].chunk_index == 1
    assert source_content.chunks[2].chunk_index == 2

    # Test to_dict includes chunk_count
    result = source_content.to_dict()
    assert result['chunk_count'] == 3


@pytest.mark.database
@pytest.mark.unit
def test_chunk_to_source_content_relationship(db_session, sample_digest, sample_source):
    """Test backward relationship from SourceContentChunk to SourceContent."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk",
        token_count=1,
        start_char=0,
        end_char=5,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    # Test backward relationship
    assert chunk.source_content is not None
    assert chunk.source_content.id == source_content.id


# =============================================================================
# Cascade Delete Tests
# =============================================================================

@pytest.mark.database
@pytest.mark.unit
def test_cascade_delete_source_content_deletes_chunks(db_session, sample_digest, sample_source):
    """Test that deleting SourceContent cascades to delete all chunks."""
    # Create prerequisite records
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content to be deleted",
        content_hash=hashlib.sha256(b"Content to be deleted").hexdigest(),
        content_length=21,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunks
    chunk1 = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk 0",
        token_count=2,
        start_char=0,
        end_char=7,
    )
    chunk2 = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=1,
        text="Chunk 1",
        token_count=2,
        start_char=8,
        end_char=15,
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    source_content_id = source_content.id
    chunk1_id = chunk1.id
    chunk2_id = chunk2.id

    # Verify chunks exist
    assert db_session.query(SourceContentChunk).filter_by(id=chunk1_id).first() is not None
    assert db_session.query(SourceContentChunk).filter_by(id=chunk2_id).first() is not None

    # Delete SourceContent
    db_session.delete(source_content)
    db_session.commit()

    # Verify SourceContent is deleted
    assert db_session.query(SourceContent).filter_by(id=source_content_id).first() is None

    # Verify chunks are also deleted (cascade)
    assert db_session.query(SourceContentChunk).filter_by(id=chunk1_id).first() is None
    assert db_session.query(SourceContentChunk).filter_by(id=chunk2_id).first() is None


@pytest.mark.database
@pytest.mark.unit
def test_cascade_delete_digest_source_item_deletes_source_content_and_chunks(
    db_session, sample_digest, sample_source
):
    """Test that deleting DigestSourceItem cascades to delete SourceContent and chunks."""
    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=sample_digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunk
    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk",
        token_count=1,
        start_char=0,
        end_char=5,
    )
    db_session.add(chunk)
    db_session.commit()

    digest_source_item_id = digest_source_item.id
    source_content_id = source_content.id
    chunk_id = chunk.id

    # Delete DigestSourceItem
    db_session.delete(digest_source_item)
    db_session.commit()

    # Verify all are deleted (cascade)
    assert db_session.query(DigestSourceItem).filter_by(id=digest_source_item_id).first() is None
    assert db_session.query(SourceContent).filter_by(id=source_content_id).first() is None
    assert db_session.query(SourceContentChunk).filter_by(id=chunk_id).first() is None


@pytest.mark.database
@pytest.mark.unit
def test_cascade_delete_digest_deletes_source_items_and_content(
    db_session, sample_source
):
    """Test that deleting Digest cascades to delete DigestSourceItem, SourceContent, and chunks."""
    # Create digest
    digest = Digest(
        url="https://example.com/digest",
        title="Test Digest for Cascade",
        summary="Summary",
        source_type="rss",
    )
    db_session.add(digest)
    db_session.flush()

    # Create DigestSourceItem
    digest_source_item = DigestSourceItem(
        digest_id=digest.id,
        source_id=sample_source.id,
        item_url="https://example.com/article",
    )
    db_session.add(digest_source_item)
    db_session.flush()

    # Create SourceContent
    source_content = SourceContent(
        digest_source_item_id=digest_source_item.id,
        content="Content",
        content_hash=hashlib.sha256(b"Content").hexdigest(),
        content_length=7,
        fetched_at=datetime.utcnow(),
    )
    db_session.add(source_content)
    db_session.flush()

    # Create chunk
    chunk = SourceContentChunk(
        source_content_id=source_content.id,
        chunk_index=0,
        text="Chunk",
        token_count=1,
        start_char=0,
        end_char=5,
    )
    db_session.add(chunk)
    db_session.commit()

    digest_id = digest.id
    digest_source_item_id = digest_source_item.id
    source_content_id = source_content.id
    chunk_id = chunk.id

    # Delete Digest
    db_session.delete(digest)
    db_session.commit()

    # Verify entire cascade
    assert db_session.query(Digest).filter_by(id=digest_id).first() is None
    assert db_session.query(DigestSourceItem).filter_by(id=digest_source_item_id).first() is None
    assert db_session.query(SourceContent).filter_by(id=source_content_id).first() is None
    assert db_session.query(SourceContentChunk).filter_by(id=chunk_id).first() is None
