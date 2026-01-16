"""Reconly MCP Server.

Model Context Protocol server that exposes Reconly's knowledge base
to AI assistants like Claude Desktop.

Available tools:
    - semantic_search: Search digests using semantic similarity
    - rag_query: Ask questions and get answers with citations
    - get_related_digests: Find related digests via knowledge graph

Usage:
    # Start server via stdio (for Claude Desktop)
    python -m reconly_mcp

    # Or use the installed script
    reconly-mcp
"""

__version__ = "1.0.0"


def main():
    """Main entry point for the MCP server.

    Lazy import to avoid loading heavy dependencies at package import time.
    """
    from reconly_mcp.server import main as _main
    return _main()


__all__ = ["main"]
