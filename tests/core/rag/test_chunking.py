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
