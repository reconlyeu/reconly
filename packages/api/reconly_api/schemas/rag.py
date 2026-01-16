"""RAG (Retrieval-Augmented Generation) API schemas."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(str, Enum):
    """Supported export formats for RAG context."""
    markdown = "markdown"
    json = "json"


class ChunkSource(str, Enum):
    """Which type of chunks to search.

    - source_content: Search SourceContentChunk embeddings (cleaner, no template noise)
    - digest: Search DigestChunk embeddings (includes formatted summaries)
    """
    source_content = "source_content"
    digest = "digest"


class RAGFilters(BaseModel):
    """Filters for RAG queries."""
    feed_id: int | None = Field(
        None,
        description="Filter by feed ID"
    )
    source_id: int | None = Field(
        None,
        description="Filter by source ID"
    )
    days: int | None = Field(
        None,
        ge=1,
        description="Filter for digests created within N days"
    )
    chunk_source: ChunkSource | None = Field(
        None,
        description=(
            "Which chunks to search: 'source_content' (default, cleaner results) "
            "or 'digest' (includes template formatting). If not specified, defaults "
            "to 'source_content'."
        )
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feed_id": 1,
                "days": 30,
                "chunk_source": "source_content"
            }
        }
    )


class RAGQueryRequest(BaseModel):
    """Request for a RAG query."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to answer"
    )
    filters: RAGFilters | None = Field(
        None,
        description="Optional filters to narrow the search"
    )
    max_chunks: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of chunks to retrieve (1-50)"
    )
    include_answer: bool = Field(
        default=True,
        description="If False, only return relevant chunks without generating an answer"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are the latest trends in machine learning?",
                "filters": {
                    "days": 30
                },
                "max_chunks": 10,
                "include_answer": True
            }
        }
    )


class Citation(BaseModel):
    """A source citation from the knowledge base."""
    id: int = Field(
        ...,
        description="Citation reference number (1, 2, 3...)"
    )
    digest_id: int = Field(
        ...,
        description="ID of the source digest"
    )
    digest_title: str | None = Field(
        None,
        description="Title of the source digest"
    )
    chunk_text: str = Field(
        ...,
        description="The relevant text chunk from the source"
    )
    chunk_index: int = Field(
        ...,
        description="Position of this chunk within the digest"
    )
    relevance_score: float = Field(
        ...,
        description="Relevance score from search (0.0 to 1.0)"
    )
    url: str | None = Field(
        None,
        description="URL to the original source"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "digest_id": 42,
                "digest_title": "Understanding Machine Learning Trends",
                "chunk_text": "Machine learning continues to evolve rapidly...",
                "chunk_index": 0,
                "relevance_score": 0.92,
                "url": "https://example.com/article"
            }
        }
    )


class RAGQueryResponse(BaseModel):
    """Response from a RAG query."""
    answer: str = Field(
        ...,
        description="The generated answer with inline citations [1], [2], etc."
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of source citations referenced in the answer"
    )
    chunks_retrieved: int = Field(
        ...,
        description="Number of chunks that were retrieved from the knowledge base"
    )
    grounded: bool = Field(
        ...,
        description="Whether the response is properly grounded in the source material"
    )
    model_used: str = Field(
        ...,
        description="Name of the LLM model used to generate the answer"
    )
    search_took_ms: float = Field(
        default=0.0,
        description="Time taken for the search in milliseconds"
    )
    generation_took_ms: float = Field(
        default=0.0,
        description="Time taken for answer generation in milliseconds"
    )
    total_took_ms: float = Field(
        default=0.0,
        description="Total time for the RAG query in milliseconds"
    )
    chunk_source: ChunkSource = Field(
        default=ChunkSource.source_content,
        description="Which chunk source was used for this search"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "answer": "According to recent sources, machine learning is evolving in several key areas [1]. Deep learning frameworks continue to improve [2].",
                "citations": [
                    {
                        "id": 1,
                        "digest_id": 42,
                        "digest_title": "Understanding ML Trends",
                        "chunk_text": "Machine learning continues to evolve...",
                        "chunk_index": 0,
                        "relevance_score": 0.92,
                        "url": "https://example.com/ml-trends"
                    },
                    {
                        "id": 2,
                        "digest_id": 43,
                        "digest_title": "AI Framework Comparison",
                        "chunk_text": "Deep learning frameworks are improving...",
                        "chunk_index": 1,
                        "relevance_score": 0.87,
                        "url": "https://example.com/frameworks"
                    }
                ],
                "chunks_retrieved": 10,
                "grounded": True,
                "model_used": "llama3.2",
                "search_took_ms": 45.2,
                "generation_took_ms": 1234.5,
                "total_took_ms": 1279.7,
                "chunk_source": "source_content"
            }
        }
    )


class RAGExportRequest(BaseModel):
    """Request to export RAG context in a specific format."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to retrieve context for"
    )
    format: ExportFormat = Field(
        default=ExportFormat.markdown,
        description="Export format: 'markdown' for human-readable, 'json' for structured data"
    )
    filters: RAGFilters | None = Field(
        None,
        description="Optional filters to narrow the search"
    )
    max_chunks: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of chunks to retrieve (1-50)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What did SAP announce about AI?",
                "format": "markdown",
                "max_chunks": 10
            }
        }
    )


class ExportCitation(BaseModel):
    """A citation in the export response with additional metadata."""
    id: int = Field(..., description="Citation reference number")
    digest_id: int = Field(..., description="ID of the source digest")
    digest_title: str | None = Field(None, description="Title of the source digest")
    chunk_text: str = Field(..., description="The relevant text chunk")
    chunk_index: int = Field(..., description="Position of chunk within digest")
    relevance_score: float = Field(..., description="Relevance score (0.0-1.0)")
    url: str | None = Field(None, description="URL to the original source")
    published_at: datetime | None = Field(None, description="Publication date of the source")

    model_config = ConfigDict(from_attributes=True)


class RAGExportResponse(BaseModel):
    """Response containing exported RAG context."""
    question: str = Field(
        ...,
        description="The original question"
    )
    format: ExportFormat = Field(
        ...,
        description="The export format used"
    )
    content: str = Field(
        ...,
        description="The exported content (markdown string or JSON string)"
    )
    citations: list[ExportCitation] = Field(
        default_factory=list,
        description="Structured citation data (always included regardless of format)"
    )
    sources_count: int = Field(
        ...,
        description="Number of unique sources retrieved"
    )
    chunks_count: int = Field(
        ...,
        description="Total number of chunks retrieved"
    )
    search_took_ms: float = Field(
        default=0.0,
        description="Time taken for the search in milliseconds"
    )
    chunk_source: ChunkSource = Field(
        default=ChunkSource.source_content,
        description="Which chunk source was used for this search"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What did SAP announce about AI?",
                "format": "markdown",
                "content": "# Context for: \"What did SAP announce about AI?\"\n\n## Source 1: SAP News Weekly\n...",
                "citations": [
                    {
                        "id": 1,
                        "digest_id": 42,
                        "digest_title": "SAP News Weekly",
                        "chunk_text": "SAP unveiled Joule AI...",
                        "chunk_index": 0,
                        "relevance_score": 0.95,
                        "url": "https://example.com/sap-news",
                        "published_at": "2024-01-15T00:00:00Z"
                    }
                ],
                "sources_count": 2,
                "chunks_count": 5,
                "search_took_ms": 45.2,
                "chunk_source": "source_content"
            }
        }
    )
