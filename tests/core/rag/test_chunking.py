"""Tests for the ChunkingService."""
import pytest
from reconly_core.rag.chunking import ChunkingService, TextChunk


class TestChunkingService:
    """Test suite for ChunkingService."""

    @pytest.fixture
    def chunker(self):
        """Return configured chunking service."""
        return ChunkingService(
            target_tokens=100,
            overlap_tokens=20,
            min_tokens=10,
            max_tokens=150,
        )

    def test_initialization_defaults(self):
        """Test default initialization values."""
        chunker = ChunkingService()
        assert chunker.target_tokens == 384
        assert chunker.overlap_tokens == 64
        assert chunker.min_tokens == 50
        assert chunker.max_tokens == 512

    def test_initialization_custom_values(self):
        """Test initialization with custom values."""
        chunker = ChunkingService(
            target_tokens=256,
            overlap_tokens=32,
            min_tokens=25,
            max_tokens=400,
        )
        assert chunker.target_tokens == 256
        assert chunker.overlap_tokens == 32
        assert chunker.min_tokens == 25
        assert chunker.max_tokens == 400

    def test_count_tokens(self, chunker):
        """Test token counting."""
        # Simple text
        text = "Hello, world!"
        count = chunker.count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty_string(self, chunker):
        """Test token counting for empty string."""
        assert chunker.count_tokens("") == 0

    def test_chunk_text_empty_string(self, chunker):
        """Test chunking empty string returns empty list."""
        chunks = chunker.chunk_text("")
        assert chunks == []

    def test_chunk_text_whitespace_only(self, chunker):
        """Test chunking whitespace-only string returns empty list."""
        chunks = chunker.chunk_text("   \n\n   ")
        assert chunks == []

    def test_chunk_text_single_paragraph(self, chunker):
        """Test chunking a single short paragraph."""
        text = "This is a short paragraph that fits in one chunk."
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        assert chunks[0].text == text.strip()
        assert chunks[0].chunk_index == 0
        assert chunks[0].start_char >= 0
        assert chunks[0].end_char > chunks[0].start_char

    def test_chunk_text_multiple_paragraphs(self, chunker):
        """Test chunking multiple paragraphs."""
        text = """First paragraph with some content.

Second paragraph with different content.

Third paragraph to complete the test."""

        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        # Check that all text is covered
        all_chunk_text = " ".join(c.text for c in chunks)
        assert "First paragraph" in all_chunk_text
        assert "Third paragraph" in all_chunk_text

    def test_chunk_text_respects_headings(self, chunker):
        """Test that heading boundaries are respected."""
        text = """# Introduction

This is the introduction section.

# Main Content

This is the main content section.

# Conclusion

This is the conclusion."""

        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        # Check that heading info is tracked
        for chunk in chunks:
            if chunk.extra_data:
                assert isinstance(chunk.extra_data.get('heading'), (str, type(None)))

    def test_chunk_text_creates_valid_chunks(self, chunker):
        """Test that all chunks have valid structure."""
        text = "A " * 500  # Long text to force multiple chunks

        chunks = chunker.chunk_text(text)

        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, TextChunk)
            assert chunk.chunk_index == i
            assert len(chunk.text) > 0
            assert chunk.token_count > 0
            assert chunk.end_char > chunk.start_char

    def test_chunk_indices_are_sequential(self, chunker):
        """Test that chunk indices are sequential starting from 0."""
        text = "A " * 500  # Long text

        chunks = chunker.chunk_text(text)

        indices = [c.chunk_index for c in chunks]
        expected = list(range(len(chunks)))
        assert indices == expected

    def test_chunk_text_long_content(self):
        """Test chunking very long content."""
        chunker = ChunkingService(target_tokens=50, max_tokens=100)
        # Create long text with multiple paragraphs
        text = "\n\n".join(["This is paragraph number " + str(i) + "." for i in range(50)])

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1
        # Verify no chunk exceeds max tokens by too much
        for chunk in chunks:
            assert chunk.token_count <= chunker.max_tokens * 1.5  # Allow some buffer

    def test_chunk_text_preserves_content(self, chunker):
        """Test that chunking doesn't lose content."""
        text = "Important content that should not be lost.\n\nMore important content here.\n\nFinal section."

        chunks = chunker.chunk_text(text)
        combined = " ".join(c.text for c in chunks)

        assert "Important content" in combined
        assert "More important content" in combined
        assert "Final section" in combined


class TestTextChunk:
    """Test the TextChunk dataclass."""

    def test_text_chunk_creation(self):
        """Test creating a TextChunk."""
        chunk = TextChunk(
            text="Test content",
            start_char=0,
            end_char=12,
            token_count=3,
            chunk_index=0,
        )

        assert chunk.text == "Test content"
        assert chunk.start_char == 0
        assert chunk.end_char == 12
        assert chunk.token_count == 3
        assert chunk.chunk_index == 0
        assert chunk.extra_data == {}

    def test_text_chunk_with_extra_data(self):
        """Test TextChunk with extra metadata."""
        chunk = TextChunk(
            text="Test content",
            start_char=0,
            end_char=12,
            token_count=3,
            chunk_index=0,
            extra_data={"heading": "Introduction", "source": "summary"},
        )

        assert chunk.extra_data["heading"] == "Introduction"
        assert chunk.extra_data["source"] == "summary"


class TestChunkSourceContent:
    """Test suite for ChunkingService.chunk_source_content()."""

    @pytest.fixture
    def chunker(self):
        """Return configured chunking service."""
        return ChunkingService(
            target_tokens=100,
            overlap_tokens=20,
            min_tokens=10,
            max_tokens=150,
        )

    @pytest.fixture
    def sample_source_content(self, db_session):
        """Create a sample SourceContent for testing."""
        from reconly_core.database.models import Source, Digest, DigestSourceItem, SourceContent
        from datetime import datetime
        import hashlib

        # Create source
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        # Create digest
        digest = Digest(
            url="https://test.example.com/digest/sample",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        # Create digest source item
        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/article",
            item_title="Test Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content
        content = """
        Artificial intelligence is transforming many industries.

        Machine learning algorithms are becoming more sophisticated every day.
        They can now process natural language, recognize images, and make predictions
        with impressive accuracy.

        Deep learning, a subset of machine learning, uses neural networks with
        multiple layers to learn complex patterns.
        """.strip()

        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()
        db_session.refresh(source_content)

        return source_content

    def test_chunk_source_content_basic(self, chunker, sample_source_content):
        """Test chunking source content with normal content."""
        chunks = chunker.chunk_source_content(sample_source_content)

        # Verify chunks were created
        assert len(chunks) > 0

        # Verify all chunks have correct structure
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, TextChunk)
            assert chunk.chunk_index == i
            assert len(chunk.text) > 0
            assert chunk.token_count > 0
            assert chunk.end_char > chunk.start_char

            # Verify extra_data contains source content metadata
            assert 'source' in chunk.extra_data
            assert chunk.extra_data['source'] == 'source_content'
            assert 'source_content_id' in chunk.extra_data
            assert chunk.extra_data['source_content_id'] == sample_source_content.id
            assert 'digest_source_item_id' in chunk.extra_data
            assert chunk.extra_data['digest_source_item_id'] == sample_source_content.digest_source_item_id

    def test_chunk_source_content_empty(self, chunker, db_session):
        """Test chunking source content with empty content."""
        from reconly_core.database.models import Source, Digest, DigestSourceItem, SourceContent
        from datetime import datetime
        import hashlib

        # Create source and digest
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{id(source)}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/empty",
            item_title="Empty Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content with empty content
        content = ""
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=0,
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()

        # Test chunking
        chunks = chunker.chunk_source_content(source_content)

        # Should return empty list
        assert chunks == []

    def test_chunk_source_content_whitespace_only(self, chunker, db_session):
        """Test chunking source content with whitespace-only content."""
        from reconly_core.database.models import Source, Digest, DigestSourceItem, SourceContent
        from datetime import datetime
        import hashlib

        # Create source and digest
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{id(source)}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/whitespace",
            item_title="Whitespace Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content with whitespace only
        content = "   \n\n   \t   "
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()

        # Test chunking
        chunks = chunker.chunk_source_content(source_content)

        # Should return empty list
        assert chunks == []

    def test_chunk_source_content_none(self, chunker, db_session):
        """Test chunking source content with None content."""
        from reconly_core.database.models import Source, Digest, DigestSourceItem, SourceContent
        from datetime import datetime

        # Create source and digest
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{id(source)}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/none",
            item_title="None Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create source content with empty string (None would violate NOT NULL)
        # We test the None case by setting content to empty string then patching it
        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content="",  # Use empty string for DB, will patch to None for test
            content_hash="none",
            content_length=0,
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()

        # Patch content to None to test None handling
        source_content.content = None

        # Test chunking
        chunks = chunker.chunk_source_content(source_content)

        # Should return empty list
        assert chunks == []

    def test_chunk_source_content_preserves_metadata(self, chunker, sample_source_content):
        """Test that all chunks contain the correct metadata."""
        chunks = chunker.chunk_source_content(sample_source_content)

        # Verify every chunk has the metadata
        for chunk in chunks:
            assert chunk.extra_data['source_content_id'] == sample_source_content.id
            assert chunk.extra_data['digest_source_item_id'] == sample_source_content.digest_source_item_id
            assert chunk.extra_data['source'] == 'source_content'

    def test_chunk_source_content_long_content(self, chunker, db_session):
        """Test chunking very long source content."""
        from reconly_core.database.models import Source, Digest, DigestSourceItem, SourceContent
        from datetime import datetime
        import hashlib

        # Create source and digest
        source = Source(name="Test Source", type="manual", url="https://test.example.com", config={})
        db_session.add(source)
        db_session.flush()

        digest = Digest(
            url=f"https://test.example.com/digest/{id(source)}",
            title="Test Digest",
            content="Test digest content",
            source_id=source.id,
            source_type="manual",
        )
        db_session.add(digest)
        db_session.flush()

        digest_source_item = DigestSourceItem(
            digest_id=digest.id,
            source_id=source.id,
            item_url="https://test.example.com/long",
            item_title="Long Article",
            item_published_at=datetime.utcnow(),
        )
        db_session.add(digest_source_item)
        db_session.flush()

        # Create very long content
        content = "\n\n".join([
            f"This is paragraph number {i}. It contains important information about topic {i}."
            for i in range(100)
        ])
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        source_content = SourceContent(
            digest_source_item_id=digest_source_item.id,
            content=content,
            content_hash=content_hash,
            content_length=len(content),
            fetched_at=datetime.utcnow(),
        )
        db_session.add(source_content)
        db_session.commit()

        # Test chunking
        chunks = chunker.chunk_source_content(source_content)

        # Should create multiple chunks
        assert len(chunks) > 1

        # Verify indices are sequential
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

        # Verify all chunks have metadata
        for chunk in chunks:
            assert chunk.extra_data['source_content_id'] == source_content.id
