"""Reconly MCP Server.

Main entry point for the Model Context Protocol server that exposes
Reconly's knowledge base to AI assistants.

Usage:
    # Start via stdio (for Claude Desktop)
    python -m reconly_mcp

    # Or use the installed script
    reconly-mcp
"""
import asyncio
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from reconly_mcp.tools import (
    TOOL_DEFINITIONS,
    ToolContext,
    handle_semantic_search,
    handle_rag_query,
    handle_get_related_digests,
    DatabaseConnectionError,
)
from reconly_mcp.formatting import format_error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("reconly_mcp")


def get_database_url() -> str:
    """Get database URL from environment.

    Requires DATABASE_URL or SKIMBERRY_DATABASE_URL environment variable.

    Returns:
        Database connection URL

    Raises:
        DatabaseConnectionError: If no database URL is configured
    """
    url = os.getenv("DATABASE_URL") or os.getenv("SKIMBERRY_DATABASE_URL")
    if not url:
        raise DatabaseConnectionError(
            "DATABASE_URL environment variable is required. "
            "Set DATABASE_URL or SKIMBERRY_DATABASE_URL to a PostgreSQL connection string."
        )
    return url


def create_database_session():
    """Create a database session.

    Returns:
        SQLAlchemy session

    Raises:
        DatabaseConnectionError: If connection fails
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    database_url = get_database_url()
    logger.info(f"Connecting to database: {database_url}")

    try:
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        # Test connection (use text() for SQLAlchemy 2.0 compatibility)
        session.execute(text("SELECT 1"))
        logger.info("Database connection established")

        return session

    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise DatabaseConnectionError(f"Could not connect to database: {e}") from e


# Create MCP server instance
server = Server("reconly")

# Global tool context (lazily initialized)
_tool_context: ToolContext | None = None


def get_tool_context() -> ToolContext:
    """Get or create the tool context with database session."""
    global _tool_context

    if _tool_context is None:
        db = create_database_session()
        _tool_context = ToolContext(db=db)

    return _tool_context


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools.

    Returns:
        List of Tool objects describing available tools
    """
    return [
        Tool(
            name=name,
            description=definition["description"],
            inputSchema=definition["inputSchema"],
        )
        for name, definition in TOOL_DEFINITIONS.items()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls.

    Routes tool calls to the appropriate handler function.

    Args:
        name: Tool name to call
        arguments: Tool arguments as dictionary

    Returns:
        List containing a single TextContent with the result
    """
    logger.info(f"Tool call: {name} with arguments: {arguments}")

    # Get tool context
    try:
        ctx = get_tool_context()
    except DatabaseConnectionError as e:
        result = format_error(
            error_type="Database Connection Error",
            message=str(e),
            suggestion="Check DATABASE_URL environment variable and ensure the database exists.",
        )
        return [TextContent(type="text", text=result)]

    # Route to handler
    try:
        if name == "semantic_search":
            result = await handle_semantic_search(
                ctx=ctx,
                query=arguments["query"],
                limit=arguments.get("limit", 10),
                feed_id=arguments.get("feed_id"),
                days=arguments.get("days"),
            )

        elif name == "rag_query":
            result = await handle_rag_query(
                ctx=ctx,
                question=arguments["question"],
                max_chunks=arguments.get("max_chunks", 10),
                feed_id=arguments.get("feed_id"),
                days=arguments.get("days"),
            )

        elif name == "get_related_digests":
            result = await handle_get_related_digests(
                ctx=ctx,
                digest_id=arguments["digest_id"],
                depth=arguments.get("depth", 2),
                min_similarity=arguments.get("min_similarity", 0.6),
            )

        else:
            result = format_error(
                error_type="Unknown Tool",
                message=f"Tool '{name}' is not implemented.",
                suggestion=f"Available tools: {', '.join(TOOL_DEFINITIONS.keys())}",
            )

    except Exception as e:
        logger.exception(f"Tool execution failed: {e}")
        result = format_error(
            error_type="Tool Execution Error",
            message=f"An unexpected error occurred: {str(e)}",
        )

    return [TextContent(type="text", text=result)]


async def run_server():
    """Run the MCP server using stdio transport."""
    logger.info("Starting Reconly MCP server...")

    # Load environment from .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.debug("Loaded environment from .env")
    except ImportError:
        pass

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP server ready, awaiting connections...")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Main entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
