"""Tests for the citation formatting and parsing module."""
import json
from datetime import datetime

import pytest

from reconly_core.rag.citations import (
    Citation,
    ExportContext,
    format_citations_for_prompt,
    parse_citations_from_response,
    format_citations_for_output,
    format_export_as_markdown,
    format_export_as_json,
)


class MockChunkMatch:
    """Mock chunk match for testing."""
    def __init__(self, text: str, score: float, chunk_index: int):
        self.text = text
        self.score = score
        self.chunk_index = chunk_index


class MockHybridSearchResult:
    """Mock search result for testing."""
    def __init__(self, digest_id: int, title: str, matched_chunks: list):
        self.digest_id = digest_id
        self.title = title
        self.matched_chunks = matched_chunks


class TestFormatCitationsForPrompt:
    """Tests for format_citations_for_prompt function."""

    def test_formats_single_result(self):
        """Test formatting a single search result."""
        results = [
            MockHybridSearchResult(
                digest_id=42,
                title="Test Article",
                matched_chunks=[
                    MockChunkMatch("This is the chunk text.", 0.9, 0)
                ]
            )
        ]

        context = format_citations_for_prompt(results)

        assert len(context.citations) == 1
        assert context.citations[0].id == 1
        assert context.citations[0].digest_id == 42
        assert context.citations[0].digest_title == "Test Article"
        assert context.citations[0].chunk_text == "This is the chunk text."
        assert context.total_chunks == 1
        assert '[1] "This is the chunk text."' in context.formatted_context
        assert "Source: Test Article" in context.formatted_context

    def test_formats_multiple_results(self):
        """Test formatting multiple search results."""
        results = [
            MockHybridSearchResult(
                digest_id=1,
                title="First Article",
                matched_chunks=[
                    MockChunkMatch("First chunk.", 0.9, 0)
                ]
            ),
            MockHybridSearchResult(
                digest_id=2,
                title="Second Article",
                matched_chunks=[
                    MockChunkMatch("Second chunk.", 0.8, 0)
                ]
            )
        ]

        context = format_citations_for_prompt(results)

        assert len(context.citations) == 2
        assert context.citations[0].id == 1
        assert context.citations[1].id == 2
        assert context.total_chunks == 2

    def test_respects_max_chunks_per_result(self):
        """Test that max_chunks_per_result is respected."""
        results = [
            MockHybridSearchResult(
                digest_id=1,
                title="Article",
                matched_chunks=[
                    MockChunkMatch(f"Chunk {i}.", 0.9 - i * 0.1, i)
                    for i in range(5)
                ]
            )
        ]

        context = format_citations_for_prompt(results, max_chunks_per_result=2)

        assert len(context.citations) == 2
        assert context.total_chunks == 2

    def test_respects_max_total_chunks(self):
        """Test that max_total_chunks is respected across results."""
        results = [
            MockHybridSearchResult(
                digest_id=i,
                title=f"Article {i}",
                matched_chunks=[
                    MockChunkMatch(f"Chunk from article {i}.", 0.9, 0)
                ]
            )
            for i in range(10)
        ]

        context = format_citations_for_prompt(results, max_total_chunks=3)

        assert len(context.citations) == 3
        assert context.total_chunks == 3

    def test_truncates_long_text_in_formatted_output(self):
        """Test that long chunk text is truncated in formatted context."""
        long_text = "x" * 600  # Longer than 500 char limit
        results = [
            MockHybridSearchResult(
                digest_id=1,
                title="Article",
                matched_chunks=[
                    MockChunkMatch(long_text, 0.9, 0)
                ]
            )
        ]

        context = format_citations_for_prompt(results)

        # The full text is preserved in the citation object
        assert len(context.citations[0].chunk_text) == 600
        # But the formatted context has truncated text
        assert "[1]" in context.formatted_context
        assert "..." in context.formatted_context


class TestParseCitationsFromResponse:
    """Tests for parse_citations_from_response function."""

    def test_parses_single_citation(self):
        """Test parsing a single citation."""
        text = "This is important [1]."
        result = parse_citations_from_response(text)

        assert 1 in result.cited_ids
        assert len(result.cited_ids) == 1

    def test_parses_multiple_citations(self):
        """Test parsing multiple citations."""
        text = "First point [1]. Second point [2]. Third point [3]."
        result = parse_citations_from_response(text)

        assert result.cited_ids == {1, 2, 3}

    def test_handles_repeated_citations(self):
        """Test that repeated citations are deduplicated."""
        text = "First [1]. Again [1]. Once more [1]."
        result = parse_citations_from_response(text)

        assert result.cited_ids == {1}

    def test_handles_no_citations(self):
        """Test handling response with no citations."""
        text = "This response has no citations at all."
        result = parse_citations_from_response(text)

        assert len(result.cited_ids) == 0

    def test_preserves_answer_text(self):
        """Test that the original answer text is preserved."""
        text = "The answer is 42 [1]."
        result = parse_citations_from_response(text)

        assert result.answer == text

    def test_detects_potential_uncited_claims(self):
        """Test detection of potential uncited factual claims."""
        text = "According to studies, 80% of users prefer this. Reported in 2024."
        result = parse_citations_from_response(text)

        # Should detect claims with percentages and years
        assert len(result.uncited_claims) > 0

    def test_no_uncited_claims_when_cited(self):
        """Test that cited claims are not flagged."""
        text = "According to studies, 80% of users prefer this [1]."
        result = parse_citations_from_response(text)

        assert len(result.uncited_claims) == 0


class TestFormatCitationsForOutput:
    """Tests for format_citations_for_output function."""

    def test_formats_all_citations(self):
        """Test formatting all citations for output."""
        citations = [
            Citation(
                id=1,
                digest_id=42,
                digest_title="Test Article",
                chunk_text="Test text",
                chunk_index=0,
                relevance_score=0.9,
                url="https://example.com"
            )
        ]

        output = format_citations_for_output(citations)

        assert len(output) == 1
        assert output[0]["id"] == 1
        assert output[0]["digest_id"] == 42
        assert output[0]["digest_title"] == "Test Article"
        assert output[0]["url"] == "https://example.com"

    def test_filters_by_cited_ids(self):
        """Test filtering citations by cited IDs."""
        citations = [
            Citation(id=1, digest_id=1, digest_title="A", chunk_text="", chunk_index=0, relevance_score=0.9),
            Citation(id=2, digest_id=2, digest_title="B", chunk_text="", chunk_index=0, relevance_score=0.8),
            Citation(id=3, digest_id=3, digest_title="C", chunk_text="", chunk_index=0, relevance_score=0.7),
        ]

        output = format_citations_for_output(citations, cited_ids={1, 3})

        assert len(output) == 2
        assert output[0]["id"] == 1
        assert output[1]["id"] == 3


class TestFormatExportAsMarkdown:
    """Tests for format_export_as_markdown function."""

    def test_formats_basic_export(self):
        """Test basic markdown export formatting."""
        citations = [
            Citation(
                id=1,
                digest_id=42,
                digest_title="SAP News Weekly",
                chunk_text="SAP unveiled Joule AI, their new enterprise assistant.",
                chunk_index=0,
                relevance_score=0.95,
                url="https://example.com/sap-news",
                published_at=datetime(2024, 1, 15),
            )
        ]
        context = ExportContext(
            question="What did SAP announce about AI?",
            citations=citations,
            sources_count=1,
            chunks_count=1,
        )

        markdown = format_export_as_markdown(context)

        assert '# Context for: "What did SAP announce about AI?"' in markdown
        assert "## Source 1: SAP News Weekly" in markdown
        assert "**Published:** 2024-01-15" in markdown
        assert "**URL:** https://example.com/sap-news" in markdown
        assert "SAP unveiled Joule AI" in markdown
        assert "*Retrieved 1 sources with 1 chunks total.*" in markdown

    def test_formats_multiple_sources(self):
        """Test markdown export with multiple sources."""
        citations = [
            Citation(
                id=1,
                digest_id=1,
                digest_title="Source A",
                chunk_text="Content from A.",
                chunk_index=0,
                relevance_score=0.9,
            ),
            Citation(
                id=2,
                digest_id=2,
                digest_title="Source B",
                chunk_text="Content from B.",
                chunk_index=0,
                relevance_score=0.8,
            ),
        ]
        context = ExportContext(
            question="Test question",
            citations=citations,
            sources_count=2,
            chunks_count=2,
        )

        markdown = format_export_as_markdown(context)

        assert "## Source 1: Source A" in markdown
        assert "## Source 2: Source B" in markdown
        assert "*Retrieved 2 sources with 2 chunks total.*" in markdown

    def test_groups_chunks_by_source(self):
        """Test that multiple chunks from same source are grouped."""
        citations = [
            Citation(id=1, digest_id=1, digest_title="Source", chunk_text="Chunk 1", chunk_index=0, relevance_score=0.9),
            Citation(id=2, digest_id=1, digest_title="Source", chunk_text="Chunk 2", chunk_index=1, relevance_score=0.85),
        ]
        context = ExportContext(
            question="Test",
            citations=citations,
            sources_count=1,
            chunks_count=2,
        )

        markdown = format_export_as_markdown(context)

        # Should only have one source header
        assert markdown.count("## Source 1:") == 1
        assert "Chunk 1" in markdown
        assert "Chunk 2" in markdown

    def test_handles_empty_citations(self):
        """Test markdown export with no citations."""
        context = ExportContext(
            question="Unknown topic",
            citations=[],
            sources_count=0,
            chunks_count=0,
        )

        markdown = format_export_as_markdown(context)

        assert '*No relevant sources found.*' in markdown


class TestFormatExportAsJson:
    """Tests for format_export_as_json function."""

    def test_formats_basic_export(self):
        """Test basic JSON export formatting."""
        citations = [
            Citation(
                id=1,
                digest_id=42,
                digest_title="SAP News Weekly",
                chunk_text="SAP unveiled Joule AI.",
                chunk_index=0,
                relevance_score=0.95123,
                url="https://example.com",
                published_at=datetime(2024, 1, 15, 10, 30),
            )
        ]
        context = ExportContext(
            question="What did SAP announce?",
            citations=citations,
            sources_count=1,
            chunks_count=1,
        )

        json_str = format_export_as_json(context)
        data = json.loads(json_str)

        assert data["question"] == "What did SAP announce?"
        assert data["sources_count"] == 1
        assert data["chunks_count"] == 1
        assert len(data["citations"]) == 1
        assert data["citations"][0]["id"] == 1
        assert data["citations"][0]["digest_id"] == 42
        assert data["citations"][0]["digest_title"] == "SAP News Weekly"
        assert data["citations"][0]["relevance_score"] == 0.9512  # Rounded to 4 decimals
        assert data["citations"][0]["url"] == "https://example.com"
        assert "2024-01-15" in data["citations"][0]["published_at"]

    def test_handles_null_values(self):
        """Test JSON export with null optional fields."""
        citations = [
            Citation(
                id=1,
                digest_id=1,
                digest_title=None,
                chunk_text="Text",
                chunk_index=0,
                relevance_score=0.9,
                url=None,
                published_at=None,
            )
        ]
        context = ExportContext(
            question="Test",
            citations=citations,
            sources_count=1,
            chunks_count=1,
        )

        json_str = format_export_as_json(context)
        data = json.loads(json_str)

        assert data["citations"][0]["digest_title"] is None
        assert data["citations"][0]["url"] is None
        assert data["citations"][0]["published_at"] is None

    def test_output_is_valid_json(self):
        """Test that output is valid JSON."""
        context = ExportContext(
            question="Test query with \"quotes\"",
            citations=[],
            sources_count=0,
            chunks_count=0,
        )

        json_str = format_export_as_json(context)

        # Should not raise
        data = json.loads(json_str)
        assert data["question"] == 'Test query with "quotes"'
