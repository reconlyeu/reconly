"""Citation formatting and parsing for RAG responses.

This module handles formatting source citations for LLM prompts
and parsing citation references from LLM responses.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.rag.search.hybrid import HybridSearchResult


@dataclass
class Citation:
    """A source citation for a RAG response.

    Attributes:
        id: Citation reference number (1, 2, 3...)
        digest_id: ID of the source digest
        digest_title: Title of the source digest
        chunk_text: The relevant text chunk
        chunk_index: Position of chunk within digest
        relevance_score: Search relevance score
        url: Optional URL to the original source
        published_at: Optional publication date
    """
    id: int
    digest_id: int
    digest_title: str | None
    chunk_text: str
    chunk_index: int
    relevance_score: float
    url: str | None = None
    published_at: datetime | None = None


@dataclass
class CitationContext:
    """Context passed to the LLM for answering questions.

    Attributes:
        citations: List of source citations
        formatted_context: Formatted text for the LLM prompt
        total_chunks: Number of chunks retrieved
    """
    citations: list[Citation]
    formatted_context: str
    total_chunks: int


@dataclass
class ParsedResponse:
    """Result of parsing an LLM response for citations.

    Attributes:
        answer: The answer text with citations preserved
        cited_ids: Set of citation IDs referenced in the answer
        uncited_claims: List of sentences that might contain uncited claims
    """
    answer: str
    cited_ids: set[int] = field(default_factory=set)
    uncited_claims: list[str] = field(default_factory=list)


def format_citations_for_prompt(
    results: list["HybridSearchResult"],
    max_chunks_per_result: int = 3,
    max_total_chunks: int = 10,
) -> CitationContext:
    """Format search results as citations for the LLM prompt.

    Creates a numbered list of source citations that the LLM can
    reference in its response using [1], [2], etc.

    Args:
        results: Search results from hybrid search
        max_chunks_per_result: Maximum chunks to include per digest
        max_total_chunks: Maximum total chunks to include

    Returns:
        CitationContext with formatted text and citation metadata

    Example:
        >>> context = format_citations_for_prompt(search_results)
        >>> print(context.formatted_context)
        [1] "Machine learning continues to evolve..."
            Source: Understanding ML Trends
        [2] "Deep learning frameworks..."
            Source: AI Framework Comparison
    """
    citations: list[Citation] = []
    citation_id = 1
    total_chunks = 0

    for result in results:
        if total_chunks >= max_total_chunks:
            break

        # Take top chunks from each result
        chunks_to_use = result.matched_chunks[:max_chunks_per_result]

        for chunk in chunks_to_use:
            if total_chunks >= max_total_chunks:
                break

            citations.append(Citation(
                id=citation_id,
                digest_id=result.digest_id,
                digest_title=result.title,
                chunk_text=chunk.text,
                chunk_index=chunk.chunk_index,
                relevance_score=chunk.score,
                url=None,  # Will be populated later if available
            ))
            citation_id += 1
            total_chunks += 1

    # Format citations for prompt
    formatted_lines = []
    for citation in citations:
        # Clean and truncate chunk text for readability
        text = citation.chunk_text.strip()
        if len(text) > 500:
            text = text[:497] + "..."

        source_info = citation.digest_title or f"Digest #{citation.digest_id}"
        formatted_lines.append(f'[{citation.id}] "{text}"')
        formatted_lines.append(f"    Source: {source_info}")
        formatted_lines.append("")  # Empty line between citations

    formatted_context = "\n".join(formatted_lines)

    return CitationContext(
        citations=citations,
        formatted_context=formatted_context,
        total_chunks=len(citations),
    )


def parse_citations_from_response(text: str) -> ParsedResponse:
    """Parse citation references from an LLM response.

    Extracts [1], [2], etc. citation markers and identifies
    potentially uncited factual claims.

    Args:
        text: The LLM response text

    Returns:
        ParsedResponse with cited IDs and potential uncited claims

    Example:
        >>> result = parse_citations_from_response(
        ...     "Machine learning is evolving rapidly [1]. "
        ...     "Deep learning uses neural networks [2]."
        ... )
        >>> print(result.cited_ids)
        {1, 2}
    """
    # Find all citation references like [1], [2], [1, 2], [1][2]
    citation_pattern = r'\[(\d+)\]'
    matches = re.findall(citation_pattern, text)
    cited_ids = {int(m) for m in matches}

    # Identify potential uncited factual claims
    # Look for sentences that:
    # 1. Don't contain any citations
    # 2. Make factual-sounding statements
    uncited_claims = []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    factual_indicators = [
        r'\b\d+%',  # Percentages
        r'\b\d{4}\b',  # Years
        r'according to',
        r'studies show',
        r'research indicates',
        r'statistics',
        r'data shows',
        r'reported that',
        r'found that',
    ]

    for sentence in sentences:
        # Skip if sentence has citation
        if re.search(citation_pattern, sentence):
            continue

        # Check for factual indicators
        for indicator in factual_indicators:
            if re.search(indicator, sentence, re.IGNORECASE):
                uncited_claims.append(sentence.strip())
                break

    return ParsedResponse(
        answer=text,
        cited_ids=cited_ids,
        uncited_claims=uncited_claims,
    )


def format_citations_for_output(
    citations: list[Citation],
    cited_ids: set[int] | None = None,
) -> list[dict]:
    """Format citations for the API response.

    Optionally filters to only include citations that were
    actually referenced in the answer.

    Args:
        citations: List of all available citations
        cited_ids: Optional set of citation IDs to include

    Returns:
        List of citation dictionaries for API response
    """
    output = []

    for citation in citations:
        # Filter if cited_ids provided
        if cited_ids is not None and citation.id not in cited_ids:
            continue

        output.append({
            "id": citation.id,
            "digest_id": citation.digest_id,
            "digest_title": citation.digest_title,
            "chunk_text": citation.chunk_text,
            "chunk_index": citation.chunk_index,
            "relevance_score": citation.relevance_score,
            "url": citation.url,
        })

    return output


def enrich_citations_with_urls(
    citations: list[Citation],
    db: "Session",
) -> list[Citation]:
    """Add URLs and published dates to citations from the database.

    Args:
        citations: List of citations to enrich
        db: Database session

    Returns:
        Citations with URLs and published_at populated from digests
    """
    from reconly_core.database.models import Digest

    if not citations:
        return citations

    # Get unique digest IDs
    digest_ids = list({c.digest_id for c in citations})

    # Fetch URLs and published dates in one query
    digests = db.query(Digest.id, Digest.url, Digest.published_at).filter(
        Digest.id.in_(digest_ids)
    ).all()

    data_map = {d.id: {'url': d.url, 'published_at': d.published_at} for d in digests}

    # Update citations
    for citation in citations:
        data = data_map.get(citation.digest_id, {})
        citation.url = data.get('url')
        citation.published_at = data.get('published_at')

    return citations


@dataclass
class ExportContext:
    """Context for exporting RAG results.

    Attributes:
        question: The original question
        citations: List of citations to export
        sources_count: Number of unique sources
        chunks_count: Total chunks retrieved
        retrieved_at: When the context was retrieved
    """
    question: str
    citations: list[Citation]
    sources_count: int
    chunks_count: int
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def format_export_as_markdown(context: ExportContext) -> str:
    """Format citations as a markdown document for external LLM use.

    Creates a human-readable markdown document suitable for copy-pasting
    into external LLM interfaces like Claude or ChatGPT.

    Args:
        context: Export context with question and citations

    Returns:
        Formatted markdown string

    Example:
        >>> md = format_export_as_markdown(context)
        >>> print(md)
        # Context for: "What did SAP announce?"

        ## Source 1: SAP News Weekly
        **Published:** 2024-01-15
        **URL:** https://...

        SAP unveiled Joule AI...
    """
    lines = []

    # Header
    lines.append(f'# Context for: "{context.question}"')
    lines.append("")

    if not context.citations:
        lines.append("*No relevant sources found.*")
        return "\n".join(lines)

    # Group citations by source (digest_id) to avoid repetition
    sources: dict[int, list[Citation]] = {}
    for citation in context.citations:
        if citation.digest_id not in sources:
            sources[citation.digest_id] = []
        sources[citation.digest_id].append(citation)

    source_num = 1
    for digest_id, citations in sources.items():
        # Get source info from first citation
        first = citations[0]
        title = first.digest_title or f"Source {source_num}"

        lines.append(f"## Source {source_num}: {title}")

        # Add metadata
        if first.published_at:
            published_str = first.published_at.strftime("%Y-%m-%d")
            lines.append(f"**Published:** {published_str}")

        if first.url:
            lines.append(f"**URL:** {first.url}")

        lines.append("")

        # Add all chunks from this source
        for citation in citations:
            text = citation.chunk_text.strip()
            lines.append(text)
            lines.append("")

        lines.append("---")
        lines.append("")
        source_num += 1

    # Footer with stats
    lines.append(f"*Retrieved {context.sources_count} sources with {context.chunks_count} chunks total.*")

    return "\n".join(lines)


def format_export_as_json(context: ExportContext) -> str:
    """Format citations as a JSON document for programmatic use.

    Creates a structured JSON document with all citation metadata.

    Args:
        context: Export context with question and citations

    Returns:
        Formatted JSON string

    Example:
        >>> json_str = format_export_as_json(context)
        >>> data = json.loads(json_str)
        >>> print(data['question'])
    """
    def serialize_datetime(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    data = {
        "question": context.question,
        "retrieved_at": serialize_datetime(context.retrieved_at),
        "sources_count": context.sources_count,
        "chunks_count": context.chunks_count,
        "citations": [
            {
                "id": c.id,
                "digest_id": c.digest_id,
                "digest_title": c.digest_title,
                "chunk_text": c.chunk_text,
                "chunk_index": c.chunk_index,
                "relevance_score": round(c.relevance_score, 4),
                "url": c.url,
                "published_at": serialize_datetime(c.published_at),
            }
            for c in context.citations
        ],
    }

    return json.dumps(data, indent=2, ensure_ascii=False)
