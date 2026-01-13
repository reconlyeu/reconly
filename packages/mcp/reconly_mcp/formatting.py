"""MCP-specific citation and result formatting.

Formats RAG results for optimal display in MCP tool responses.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.rag import (
        HybridSearchResult,
        RAGResult,
        GraphData,
    )


def format_search_results(
    results: list["HybridSearchResult"],
    max_chunks_per_result: int = 2,
    max_chunk_length: int = 300,
) -> str:
    """Format hybrid search results for MCP tool response.

    Creates a readable text representation of search results
    suitable for AI assistant consumption.

    Args:
        results: Search results from HybridSearchService
        max_chunks_per_result: Maximum chunks to show per digest
        max_chunk_length: Maximum characters per chunk

    Returns:
        Formatted string with search results

    Example output:
        ## Search Results (5 matches)

        ### 1. Understanding Machine Learning Trends
        **Score:** 0.85 | **Digest ID:** 42

        > Machine learning continues to evolve rapidly with new
        > architectures and training techniques...

        > Deep learning frameworks have become more accessible...

        ---
    """
    if not results:
        return "No results found for your query."

    lines = [f"## Search Results ({len(results)} matches)\n"]

    for idx, result in enumerate(results, start=1):
        title = result.title or f"Digest #{result.digest_id}"
        lines.append(f"### {idx}. {title}")
        lines.append(f"**Score:** {result.score:.2f} | **Digest ID:** {result.digest_id}")
        lines.append("")

        # Add chunks
        chunks_to_show = result.matched_chunks[:max_chunks_per_result]
        for chunk in chunks_to_show:
            text = chunk.text.strip()
            if len(text) > max_chunk_length:
                text = text[:max_chunk_length - 3] + "..."

            # Format as blockquote, handling newlines
            quoted = "\n".join(f"> {line}" for line in text.split("\n"))
            lines.append(quoted)
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def format_rag_response(
    result: "RAGResult",
    include_metadata: bool = True,
) -> str:
    """Format RAG query result for MCP tool response.

    Creates a response with the answer, inline citations, and
    a sources section at the end.

    Args:
        result: RAGResult from RAGService.query()
        include_metadata: Whether to include timing/model metadata

    Returns:
        Formatted string with answer and citations

    Example output:
        Machine learning is evolving rapidly [1], with new architectures
        emerging frequently [2]. Deep learning has become more accessible
        through improved frameworks [1].

        ## Sources

        [1] **Understanding ML Trends** (Digest #42)
            "Machine learning continues to evolve..."

        [2] **AI Framework Comparison** (Digest #58)
            "Deep learning frameworks have become..."

        ---
        *Model: llama-3.3-70b | Search: 45ms | Generation: 1250ms*
    """
    lines = []

    # Add answer
    lines.append(result.answer)
    lines.append("")

    # Add sources section
    if result.citations:
        lines.append("## Sources\n")
        for citation in result.citations:
            source_info = citation.digest_title or f"Digest #{citation.digest_id}"
            lines.append(f"[{citation.id}] **{source_info}** (Digest #{citation.digest_id})")

            # Truncate chunk text
            text = citation.chunk_text.strip()
            if len(text) > 200:
                text = text[:197] + "..."

            lines.append(f'    "{text}"')

            if citation.url:
                lines.append(f"    URL: {citation.url}")

            lines.append("")

    # Add metadata
    if include_metadata:
        lines.append("---")
        metadata_parts = []
        if result.model_used:
            metadata_parts.append(f"Model: {result.model_used}")
        if result.search_took_ms:
            metadata_parts.append(f"Search: {result.search_took_ms:.0f}ms")
        if result.generation_took_ms:
            metadata_parts.append(f"Generation: {result.generation_took_ms:.0f}ms")

        if metadata_parts:
            lines.append(f"*{' | '.join(metadata_parts)}*")

    return "\n".join(lines)


def format_related_digests(
    graph_data: "GraphData",
    center_digest_id: int,
) -> str:
    """Format knowledge graph relationships for MCP tool response.

    Creates a readable representation of related digests and
    their relationship types.

    Args:
        graph_data: GraphData from GraphService.get_graph_data()
        center_digest_id: The digest ID that was queried

    Returns:
        Formatted string with related digests

    Example output:
        ## Related Digests for "Understanding ML Trends" (ID: 42)

        ### Semantically Similar
        - **AI Framework Comparison** (ID: 58, Score: 0.89)
        - **Neural Network Advances** (ID: 61, Score: 0.82)

        ### Same Source
        - **Deep Learning Guide** (ID: 43, Score: 0.75)

        ### Shared Tags
        - **Python ML Libraries** (ID: 102, Score: 0.68)
          Tags: machine-learning, python
    """
    if not graph_data.nodes:
        return f"No related digests found for digest #{center_digest_id}."

    # Find center node
    center_node = None
    for node in graph_data.nodes:
        if node.type == "digest" and node.data.get("digest_id") == center_digest_id:
            center_node = node
            break

    center_title = center_node.label if center_node else f"Digest #{center_digest_id}"

    lines = [f"## Related Digests for \"{center_title}\" (ID: {center_digest_id})\n"]

    # Group edges by relationship type
    relationships: dict[str, list[tuple]] = {
        "semantic": [],
        "source": [],
        "tag": [],
    }

    # Build node lookup
    node_lookup = {node.id: node for node in graph_data.nodes}

    # Collect relationships from center node
    center_node_id = f"d_{center_digest_id}"
    for edge in graph_data.edges:
        if edge.source == center_node_id:
            target_node = node_lookup.get(edge.target)
            if target_node and target_node.type == "digest":
                relationships[edge.type].append((target_node, edge))

    # Format semantic relationships
    if relationships["semantic"]:
        lines.append("### Semantically Similar")
        for node, edge in sorted(relationships["semantic"], key=lambda x: -x[1].score):
            digest_id = node.data.get("digest_id", "?")
            lines.append(f"- **{node.label}** (ID: {digest_id}, Score: {edge.score:.2f})")
        lines.append("")

    # Format source relationships
    if relationships["source"]:
        lines.append("### Same Source")
        for node, edge in sorted(relationships["source"], key=lambda x: -x[1].score):
            digest_id = node.data.get("digest_id", "?")
            lines.append(f"- **{node.label}** (ID: {digest_id}, Score: {edge.score:.2f})")
        lines.append("")

    # Format tag relationships
    if relationships["tag"]:
        lines.append("### Shared Tags")
        for node, edge in sorted(relationships["tag"], key=lambda x: -x[1].score):
            digest_id = node.data.get("digest_id", "?")
            shared_tags = edge.extra_data.get("shared_tags", [])
            tag_info = f"\n  Tags: {', '.join(shared_tags)}" if shared_tags else ""
            lines.append(f"- **{node.label}** (ID: {digest_id}, Score: {edge.score:.2f}){tag_info}")
        lines.append("")

    # Summary if no relationships found
    if not any(relationships.values()):
        lines.append("No related digests found in the knowledge graph.")
        lines.append("")
        lines.append("*Tip: Relationships are computed automatically after digests are embedded.*")

    return "\n".join(lines)


def format_error(
    error_type: str,
    message: str,
    suggestion: str | None = None,
) -> str:
    """Format an error message for MCP tool response.

    Args:
        error_type: Type of error (e.g., "EmbeddingServiceUnavailable")
        message: Error message
        suggestion: Optional suggestion for resolution

    Returns:
        Formatted error string
    """
    lines = [
        f"## Error: {error_type}",
        "",
        message,
    ]

    if suggestion:
        lines.extend([
            "",
            f"**Suggestion:** {suggestion}",
        ])

    return "\n".join(lines)
