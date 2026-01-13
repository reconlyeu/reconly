# Reconly MCP Server

Model Context Protocol (MCP) server that exposes Reconly's knowledge base to AI assistants like Claude Desktop.

## Installation

```bash
# Install from source
cd packages/mcp
pip install -e .

# Or install with uv
uv pip install -e .
```

## Configuration

The MCP server requires a connection to the Reconly database. Configure via environment variables:

```bash
# Database connection (PostgreSQL required)
DATABASE_URL=postgresql://user:pass@localhost/reconly

# Embedding provider (optional, defaults to Ollama)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3

# LLM provider for RAG queries (optional)
DEFAULT_PROVIDER=huggingface
DEFAULT_MODEL=llama-3.3-70b
```

## Usage

### Starting the Server

```bash
# Start via stdio (for Claude Desktop)
python -m reconly_mcp

# Or use the installed script
reconly-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "reconly": {
      "command": "python",
      "args": ["-m", "reconly_mcp"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/reconly"
      }
    }
  }
}
```

Or if using the installed script:

```json
{
  "mcpServers": {
    "reconly": {
      "command": "reconly-mcp",
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/reconly"
      }
    }
  }
}
```

## Available Tools

### semantic_search

Search the knowledge base using hybrid vector + full-text search.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | The search query text |
| `limit` | integer | No | Maximum results (default: 10, max: 50) |
| `feed_id` | integer | No | Filter to a specific feed ID |
| `days` | integer | No | Filter to digests within N days |

**Example:**
```
Search for "machine learning frameworks" in digests from the last 30 days
```

**Response format:**
```markdown
## Search Results (5 matches)

### 1. Understanding ML Trends
**Score:** 0.85 | **Digest ID:** 42

> Machine learning continues to evolve rapidly with new
> architectures and training techniques...

---
```

### rag_query

Ask questions and get answers with citations from the knowledge base.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `question` | string | Yes | The question to answer |
| `max_chunks` | integer | No | Context chunks to retrieve (default: 10, max: 20) |
| `feed_id` | integer | No | Filter sources to a specific feed ID |
| `days` | integer | No | Filter to sources within N days |

**Example:**
```
What are the latest developments in transformer architectures?
```

**Response format:**
```markdown
Transformer architectures have seen significant developments [1],
including improved attention mechanisms [2] and more efficient
training methods [1].

## Sources

[1] **Understanding ML Trends** (Digest #42)
    "Machine learning continues to evolve..."

[2] **AI Framework Comparison** (Digest #58)
    "Deep learning frameworks have become..."

---
*Model: llama-3.3-70b | Search: 45ms | Generation: 1250ms*
```

### get_related_digests

Find related digests using the knowledge graph.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `digest_id` | integer | Yes | ID of the digest to find relations for |
| `depth` | integer | No | Relationship hops to traverse (default: 2, max: 4) |
| `min_similarity` | number | No | Minimum score (default: 0.6, range: 0-1) |

**Example:**
```
Find digests related to digest #42
```

**Response format:**
```markdown
## Related Digests for "Understanding ML Trends" (ID: 42)

### Semantically Similar
- **AI Framework Comparison** (ID: 58, Score: 0.89)
- **Neural Network Advances** (ID: 61, Score: 0.82)

### Same Source
- **Deep Learning Guide** (ID: 43, Score: 0.75)

### Shared Tags
- **Python ML Libraries** (ID: 102, Score: 0.68)
  Tags: machine-learning, python
```

## Error Handling

The server provides informative error messages when issues occur:

**Embedding Service Unavailable:**
```markdown
## Error: Embedding Service Unavailable

The embedding service is not configured or not running.

**Suggestion:** Ensure Ollama is running with an embedding model,
or configure an alternative embedding provider.
```

**Database Connection Error:**
```markdown
## Error: Database Connection Error

Could not connect to database: [details]

**Suggestion:** Check DATABASE_URL environment variable and
ensure the database exists.
```

## Requirements

- Python 3.10+
- Reconly database with indexed digests
- Embedding service (Ollama, OpenAI, or HuggingFace)
- LLM service for RAG queries

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Architecture

```
reconly_mcp/
  __init__.py     # Package exports
  __main__.py     # Allow python -m execution
  server.py       # MCP server implementation
  tools.py        # Tool handlers
  formatting.py   # Response formatting
```

The server uses:
- **HybridSearchService** for semantic search
- **RAGService** for question answering
- **GraphService** for knowledge graph queries

## License

AGPL-3.0
