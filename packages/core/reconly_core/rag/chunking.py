"""Text chunking service for RAG embedding preparation.

Splits text into semantic chunks suitable for embedding and retrieval.
Respects paragraph and heading boundaries while maintaining overlap.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore[assignment]
    _TIKTOKEN_AVAILABLE = False


@dataclass
class TextChunk:
    """A chunk of text with metadata for embedding.

    Attributes:
        text: The actual text content
        start_char: Character offset in original text
        end_char: End character offset in original text
        token_count: Number of tokens in the chunk
        chunk_index: Order within the source document (0-indexed)
        extra_data: Optional metadata (heading, section, etc.)
    """
    text: str
    start_char: int
    end_char: int
    token_count: int
    chunk_index: int = 0
    extra_data: dict = field(default_factory=dict)


class ChunkingService:
    """Service for splitting text into semantic chunks.

    Chunks are created by:
    1. Splitting on paragraph boundaries (double newlines)
    2. Respecting heading boundaries (markdown headers)
    3. Targeting a specific token count per chunk
    4. Maintaining overlap between chunks for context

    Example:
        >>> chunker = ChunkingService(target_tokens=384, overlap_tokens=64)
        >>> chunks = chunker.chunk_text("Your long text here...")
        >>> for chunk in chunks:
        ...     print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
    """

    # Default settings
    DEFAULT_TARGET_TOKENS = 384
    DEFAULT_OVERLAP_TOKENS = 64
    DEFAULT_MIN_TOKENS = 50
    DEFAULT_MAX_TOKENS = 512

    # Regex patterns
    PARAGRAPH_PATTERN = re.compile(r'\n\n+')
    HEADING_PATTERN = re.compile(r'^#{1,6}\s+.+$', re.MULTILINE)
    SENTENCE_PATTERN = re.compile(r'(?<=[.!?])\s+')

    def __init__(
        self,
        target_tokens: int = DEFAULT_TARGET_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
        min_tokens: int = DEFAULT_MIN_TOKENS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        encoding_name: str = "cl100k_base",
        db: Optional["Session"] = None,
    ):
        """
        Initialize the chunking service.

        Args:
            target_tokens: Target token count per chunk (default: 384)
            overlap_tokens: Token overlap between chunks (default: 64)
            min_tokens: Minimum tokens for a chunk (default: 50)
            max_tokens: Maximum tokens before forcing split (default: 512)
            encoding_name: Tiktoken encoding name (default: cl100k_base for GPT-4)
            db: Optional database session for reading settings
        """
        # Load settings from DB if provided
        if db is not None:
            target_tokens, overlap_tokens = self._load_settings_from_db(
                db, target_tokens, overlap_tokens
            )

        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

        # Initialize tokenizer
        self._encoding_name = encoding_name
        self._encoding = None  # Lazy load

    def _load_settings_from_db(
        self,
        db: "Session",
        default_target: int,
        default_overlap: int
    ) -> tuple[int, int]:
        """Load chunk settings from database."""
        try:
            from reconly_core.services.settings_service import SettingsService
            service = SettingsService(db)

            target = service.get("embedding.chunk_size")
            overlap = service.get("embedding.chunk_overlap")

            return (
                int(target) if target else default_target,
                int(overlap) if overlap else default_overlap,
            )
        except Exception:
            return default_target, default_overlap

    @property
    def encoding(self):
        """Lazy-load tiktoken encoding."""
        if self._encoding is None:
            if _TIKTOKEN_AVAILABLE:
                self._encoding = tiktoken.get_encoding(self._encoding_name)  # type: ignore[union-attr]
            else:
                self._encoding = None
        return self._encoding

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Uses tiktoken if available, otherwise estimates based on word count.

        Args:
            text: Text to count tokens in

        Returns:
            Token count (exact if tiktoken available, estimate otherwise)
        """
        if self.encoding is not None:
            return len(self.encoding.encode(text))
        else:
            # Rough estimate: ~4 characters per token for English
            # This is less accurate but works without tiktoken
            return len(text) // 4

    def chunk_text(self, text: str) -> List[TextChunk]:
        """
        Split text into semantic chunks.

        Args:
            text: The text to chunk

        Returns:
            List of TextChunk objects with metadata

        Example:
            >>> chunker = ChunkingService()
            >>> chunks = chunker.chunk_text(long_text)
            >>> for chunk in chunks:
            ...     print(f"[{chunk.start_char}:{chunk.end_char}] {chunk.token_count} tokens")
        """
        if not text or not text.strip():
            return []

        # First, split into paragraphs/sections
        sections = self._split_into_sections(text)

        if not sections:
            return []

        # Build chunks from sections
        chunks = self._build_chunks_from_sections(sections, text)

        return chunks

    def _split_into_sections(self, text: str) -> List[dict]:
        """
        Split text into sections (paragraphs or heading-bounded blocks).

        Returns list of dicts with 'text', 'start', 'end', 'heading' keys.
        """
        sections = []

        # Split by paragraphs first
        paragraphs = self.PARAGRAPH_PATTERN.split(text)

        current_pos = 0
        current_heading = None

        for para in paragraphs:
            if not para.strip():
                current_pos += len(para) + 2  # Account for \n\n
                continue

            # Find the start position of this paragraph in original text
            start = text.find(para, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(para)

            # Check if this paragraph is a heading
            para_stripped = para.strip()
            if para_stripped.startswith('#'):
                current_heading = para_stripped.lstrip('#').strip()

            # Skip very short paragraphs (likely artifacts)
            if len(para.strip()) < 10:
                current_pos = end + 2
                continue

            sections.append({
                'text': para.strip(),
                'start': start,
                'end': end,
                'heading': current_heading,
            })

            current_pos = end + 2

        return sections

    def _build_chunks_from_sections(
        self,
        sections: List[dict],
        original_text: str
    ) -> List[TextChunk]:
        """Build chunks from sections, respecting token limits and overlap."""
        chunks = []
        current_chunk_texts = []
        current_chunk_start = sections[0]['start'] if sections else 0
        current_token_count = 0
        current_heading = None
        chunk_index = 0

        for i, section in enumerate(sections):
            section_text = section['text']
            section_tokens = self.count_tokens(section_text)

            # Update heading if changed
            if section['heading']:
                current_heading = section['heading']

            # Check if adding this section would exceed max tokens
            if current_token_count + section_tokens > self.max_tokens and current_chunk_texts:
                # Finalize current chunk
                chunk = self._create_chunk(
                    current_chunk_texts,
                    current_chunk_start,
                    sections[i - 1]['end'],
                    current_token_count,
                    chunk_index,
                    current_heading,
                )
                chunks.append(chunk)
                chunk_index += 1

                # Start new chunk with overlap
                overlap_texts, overlap_tokens = self._get_overlap(
                    current_chunk_texts,
                    self.overlap_tokens
                )
                current_chunk_texts = overlap_texts + [section_text]
                current_chunk_start = section['start'] - sum(
                    len(t) + 2 for t in overlap_texts
                )
                current_chunk_start = max(0, current_chunk_start)
                current_token_count = overlap_tokens + section_tokens

            # Check if section itself exceeds max tokens (need to split it)
            elif section_tokens > self.max_tokens:
                # Finalize current chunk if any
                if current_chunk_texts:
                    chunk = self._create_chunk(
                        current_chunk_texts,
                        current_chunk_start,
                        sections[i - 1]['end'] if i > 0 else section['start'],
                        current_token_count,
                        chunk_index,
                        current_heading,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                # Split large section into smaller chunks
                sub_chunks = self._split_large_section(
                    section,
                    chunk_index,
                    current_heading,
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)

                # Reset
                current_chunk_texts = []
                current_chunk_start = section['end']
                current_token_count = 0

            else:
                # Add section to current chunk
                current_chunk_texts.append(section_text)
                current_token_count += section_tokens

                # Check if we've reached target size
                if current_token_count >= self.target_tokens:
                    chunk = self._create_chunk(
                        current_chunk_texts,
                        current_chunk_start,
                        section['end'],
                        current_token_count,
                        chunk_index,
                        current_heading,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                    # Start new chunk with overlap
                    overlap_texts, overlap_tokens = self._get_overlap(
                        current_chunk_texts,
                        self.overlap_tokens
                    )
                    current_chunk_texts = overlap_texts
                    current_chunk_start = section['end'] - sum(
                        len(t) + 2 for t in overlap_texts
                    )
                    current_chunk_start = max(0, current_chunk_start)
                    current_token_count = overlap_tokens

        # Handle remaining text
        if current_chunk_texts:
            final_chunk = self._create_chunk(
                current_chunk_texts,
                current_chunk_start,
                sections[-1]['end'] if sections else 0,
                current_token_count,
                chunk_index,
                current_heading,
            )
            # Only add if it meets minimum size or is the only chunk
            if final_chunk.token_count >= self.min_tokens or len(chunks) == 0:
                chunks.append(final_chunk)
            elif chunks:
                # Merge with previous chunk if too small
                prev_chunk = chunks[-1]
                merged_text = prev_chunk.text + "\n\n" + final_chunk.text
                chunks[-1] = TextChunk(
                    text=merged_text,
                    start_char=prev_chunk.start_char,
                    end_char=final_chunk.end_char,
                    token_count=self.count_tokens(merged_text),
                    chunk_index=prev_chunk.chunk_index,
                    extra_data=prev_chunk.extra_data,
                )

        return chunks

    def _create_chunk(
        self,
        texts: List[str],
        start_char: int,
        end_char: int,
        token_count: int,
        chunk_index: int,
        heading: Optional[str] = None,
    ) -> TextChunk:
        """Create a TextChunk from component texts."""
        combined_text = "\n\n".join(texts)
        extra_data = {}
        if heading:
            extra_data['heading'] = heading

        return TextChunk(
            text=combined_text,
            start_char=start_char,
            end_char=end_char,
            token_count=token_count,
            chunk_index=chunk_index,
            extra_data=extra_data,
        )

    def _get_overlap(
        self,
        texts: List[str],
        target_overlap_tokens: int
    ) -> tuple[List[str], int]:
        """
        Get texts for overlap from the end of current chunk.

        Returns tuple of (overlap_texts, overlap_token_count).
        """
        if not texts:
            return [], 0

        overlap_texts = []
        overlap_tokens = 0

        # Work backwards from the end
        for text in reversed(texts):
            text_tokens = self.count_tokens(text)
            if overlap_tokens + text_tokens <= target_overlap_tokens:
                overlap_texts.insert(0, text)
                overlap_tokens += text_tokens
            else:
                break

        return overlap_texts, overlap_tokens

    def _split_large_section(
        self,
        section: dict,
        start_chunk_index: int,
        heading: Optional[str],
    ) -> List[TextChunk]:
        """Split a large section into smaller chunks by sentences."""
        text = section['text']
        sentences = self.SENTENCE_PATTERN.split(text)

        chunks = []
        current_sentences = []
        current_tokens = 0
        chunk_index = start_chunk_index

        start_pos = section['start']

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_tokens = self.count_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_tokens and current_sentences:
                # Create chunk
                chunk_text = " ".join(current_sentences)
                end_pos = start_pos + len(chunk_text)

                extra_data = {}
                if heading:
                    extra_data['heading'] = heading

                chunks.append(TextChunk(
                    text=chunk_text,
                    start_char=start_pos,
                    end_char=end_pos,
                    token_count=current_tokens,
                    chunk_index=chunk_index,
                    extra_data=extra_data,
                ))

                chunk_index += 1
                start_pos = end_pos + 1

                # Start new chunk with some overlap
                current_sentences = current_sentences[-2:] if len(current_sentences) > 2 else []
                current_tokens = sum(self.count_tokens(s) for s in current_sentences)

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Handle remaining sentences
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            extra_data = {}
            if heading:
                extra_data['heading'] = heading

            chunks.append(TextChunk(
                text=chunk_text,
                start_char=start_pos,
                end_char=section['end'],
                token_count=current_tokens,
                chunk_index=chunk_index,
                extra_data=extra_data,
            ))

        return chunks

    def chunk_digest(
        self,
        digest,
        include_title: bool = True,
        include_summary: bool = True,
    ) -> List[TextChunk]:
        """
        Chunk a Digest model instance.

        Combines title, summary, and content for comprehensive chunking.

        Args:
            digest: Digest model instance
            include_title: Whether to prepend title to first chunk
            include_summary: Whether to include summary as separate chunk

        Returns:
            List of TextChunk objects
        """
        chunks = []
        chunk_index = 0

        # Optionally add summary as first chunk (usually more valuable)
        if include_summary and digest.summary:
            summary_text = digest.summary.strip()
            if include_title and digest.title:
                summary_text = f"# {digest.title}\n\n{summary_text}"

            summary_tokens = self.count_tokens(summary_text)
            chunks.append(TextChunk(
                text=summary_text,
                start_char=0,
                end_char=len(summary_text),
                token_count=summary_tokens,
                chunk_index=chunk_index,
                extra_data={
                    'source': 'summary',
                    'digest_id': digest.id,
                    'title': digest.title,
                },
            ))
            chunk_index += 1

        # Chunk the main content
        if digest.content:
            content_chunks = self.chunk_text(digest.content)
            for content_chunk in content_chunks:
                content_chunk.chunk_index = chunk_index
                content_chunk.extra_data['source'] = 'content'
                content_chunk.extra_data['digest_id'] = digest.id
                content_chunk.extra_data['title'] = digest.title
                chunks.append(content_chunk)
                chunk_index += 1

        return chunks
