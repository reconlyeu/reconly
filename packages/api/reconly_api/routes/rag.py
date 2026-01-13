"""RAG (Retrieval-Augmented Generation) API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGExportRequest,
    RAGExportResponse,
    ExportCitation,
    ExportFormat,
    Citation as CitationSchema,
    RAGFilters as RAGFiltersSchema,
)

router = APIRouter()


def _get_rag_service(db: Session):
    """Create RAG service with embedding provider and summarizer.

    Returns:
        Tuple of (RAGService, embedding_provider)

    Raises:
        HTTPException: If dependencies are missing
    """
    from reconly_core.rag import get_embedding_provider
    from reconly_core.rag.rag_service import RAGService
    from reconly_core.summarizers.factory import get_summarizer

    embedding_provider = get_embedding_provider(db=db)
    summarizer = get_summarizer(db=db, enable_fallback=False)

    return RAGService(
        db=db,
        embedding_provider=embedding_provider,
        summarizer=summarizer,
    )


def _convert_filters(filters: RAGFiltersSchema | None):
    """Convert schema filters to service filters."""
    if not filters:
        return None

    from reconly_core.rag.rag_service import RAGFilters
    return RAGFilters(
        feed_id=filters.feed_id,
        source_id=filters.source_id,
        days=filters.days,
    )


@router.post("/query/", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    """
    Query the knowledge base using RAG (Retrieval-Augmented Generation).

    This endpoint retrieves relevant chunks from indexed digests and
    generates an answer with inline citations [1], [2], etc.

    **How it works:**
    1. Searches the knowledge base using hybrid (vector + full-text) search
    2. Retrieves the most relevant chunks from your digests
    3. Generates an answer grounded in the retrieved sources
    4. Returns the answer with citations to the original sources

    **Filters:**
    - `feed_id`: Only search digests from a specific feed
    - `source_id`: Only search digests from a specific source
    - `days`: Only search digests created within the last N days

    **Options:**
    - `max_chunks`: Control how many source chunks are retrieved (1-50)
    - `include_answer`: Set to `false` to only retrieve chunks without generating

    **Response:**
    - `answer`: The generated answer with inline citations
    - `citations`: List of source citations with digest info
    - `grounded`: Whether the response is properly grounded in sources
    - `model_used`: The LLM model that generated the answer
    """
    try:
        rag_service = _get_rag_service(db)
        filters = _convert_filters(request.filters)

        result = await rag_service.query(
            question=request.question,
            filters=filters,
            max_chunks=request.max_chunks,
            include_answer=request.include_answer,
        )

        citations = [
            CitationSchema(
                id=c.id,
                digest_id=c.digest_id,
                digest_title=c.digest_title,
                chunk_text=c.chunk_text,
                chunk_index=c.chunk_index,
                relevance_score=c.relevance_score,
                url=c.url,
            )
            for c in result.citations
        ]

        return RAGQueryResponse(
            answer=result.answer,
            citations=citations,
            chunks_retrieved=result.chunks_retrieved,
            grounded=result.grounded,
            model_used=result.model_used,
            search_took_ms=result.search_took_ms,
            generation_took_ms=result.generation_took_ms,
            total_took_ms=result.total_took_ms,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency for RAG: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/search/", response_model=RAGQueryResponse)
async def rag_search(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    """
    Search for relevant chunks without generating an answer.

    This is a convenience endpoint equivalent to calling `/query/`
    with `include_answer: false`. Useful for:
    - Previewing what sources would be used for a question
    - Building custom answer generation workflows
    - Debugging and testing the search functionality

    Returns the same response format as `/query/` but with an empty
    answer field.
    """
    # Force include_answer to False
    request.include_answer = False

    return await rag_query(request, db)


@router.post("/export/", response_model=RAGExportResponse)
async def rag_export(
    request: RAGExportRequest,
    db: Session = Depends(get_db),
) -> RAGExportResponse:
    """
    Export RAG context in a specified format for use with external LLMs.

    This endpoint retrieves relevant chunks and formats them for easy
    copy-paste into external LLM interfaces like Claude or ChatGPT.

    **Formats:**
    - `markdown`: Human-readable document with sources grouped and formatted
    - `json`: Structured data for programmatic use

    **Use Cases:**
    - Copy context to Claude, ChatGPT, or other LLM interfaces
    - Build custom RAG pipelines with external LLMs
    - Archive retrieved context for later reference
    - Integrate with external tools and workflows

    **Markdown Format Example:**
    ```markdown
    # Context for: "What did SAP announce about AI?"

    ## Source 1: SAP News Weekly
    **Published:** 2024-01-15
    **URL:** https://...

    SAP unveiled Joule AI, their new enterprise assistant...

    ---

    *Retrieved 2 sources with 5 chunks total.*
    ```

    The response always includes both the formatted `content` string and
    the structured `citations` array for maximum flexibility.
    """
    try:
        from reconly_core.rag.citations import (
            ExportContext,
            format_export_as_markdown,
            format_export_as_json,
        )

        rag_service = _get_rag_service(db)
        filters = _convert_filters(request.filters)

        result = await rag_service.search_only(
            question=request.question,
            filters=filters,
            max_chunks=request.max_chunks,
        )

        unique_sources = len({c.digest_id for c in result.citations})

        export_context = ExportContext(
            question=request.question,
            citations=result.citations,
            sources_count=unique_sources,
            chunks_count=result.chunks_retrieved,
        )

        if request.format == ExportFormat.markdown:
            content = format_export_as_markdown(export_context)
        else:
            content = format_export_as_json(export_context)

        export_citations = [
            ExportCitation(
                id=c.id,
                digest_id=c.digest_id,
                digest_title=c.digest_title,
                chunk_text=c.chunk_text,
                chunk_index=c.chunk_index,
                relevance_score=c.relevance_score,
                url=c.url,
                published_at=c.published_at,
            )
            for c in result.citations
        ]

        return RAGExportResponse(
            question=request.question,
            format=request.format,
            content=content,
            citations=export_citations,
            sources_count=unique_sources,
            chunks_count=result.chunks_retrieved,
            search_took_ms=result.search_took_ms,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency for RAG: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG export failed: {str(e)}"
        )
