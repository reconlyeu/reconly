# RAG Knowledge System Setup Guide

This guide walks you through setting up Reconly's RAG (Retrieval-Augmented Generation) knowledge system for semantic search and AI-powered question answering over your digest library.

## Overview

The RAG system enables:
- **Semantic Search**: Find digests by meaning, not just keywords
- **Question Answering**: Ask natural language questions with cited answers
- **Knowledge Discovery**: Find related digests and explore connections
- **Multi-Provider**: Use local (Ollama) or cloud (OpenAI, HuggingFace) embeddings

## Prerequisites

### Required
- **PostgreSQL 16+** with **pgvector extension**
- **Python 3.10+** (already installed if you're running Reconly)

### Optional
- **Ollama** (for local, free embeddings - recommended)
- **OpenAI API key** (for cloud embeddings)
- **HuggingFace API key** (for cloud embeddings)

## Step 1: Install PostgreSQL with pgvector

### Option A: Docker (Recommended)

The easiest way to get PostgreSQL with pgvector is using Docker:

```bash
# Start PostgreSQL with pgvector
cd reconly-oss
docker-compose -f docker/docker-compose.postgres.yml up -d

# Verify it's running
docker-compose -f docker/docker-compose.postgres.yml logs -f postgres
```

**Default connection details:**
- Host: `localhost`
- Port: `5432`
- Database: `reconly`
- User: `reconly`
- Password: `reconly_dev`

**Custom configuration:**

Create a `.env` file to customize:

```bash
POSTGRES_PORT=5432
POSTGRES_DB=reconly
POSTGRES_USER=reconly
POSTGRES_PASSWORD=your_secure_password
```

### Option B: System PostgreSQL

If you prefer a system-wide PostgreSQL installation:

**Ubuntu/Debian:**
```bash
# Add PostgreSQL repository
sudo apt install postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh

# Install PostgreSQL 16
sudo apt install postgresql-16 postgresql-16-pgvector

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and enable pgvector
sudo -u postgres psql
CREATE DATABASE reconly;
CREATE USER reconly WITH PASSWORD 'reconly_dev';
GRANT ALL PRIVILEGES ON DATABASE reconly TO reconly;
\c reconly
CREATE EXTENSION vector;
\q
```

**macOS (Homebrew):**
```bash
# Install PostgreSQL
brew install postgresql@16

# Start PostgreSQL
brew services start postgresql@16

# Install pgvector
brew install pgvector

# Create database
createdb reconly
psql reconly
CREATE EXTENSION vector;
\q
```

**Verify pgvector installation:**
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

You should see the `vector` extension listed.

## Step 2: Configure Database Connection

Set the `DATABASE_URL` environment variable to point to PostgreSQL:

**In your `.env` file:**
```bash
DATABASE_URL=postgresql://reconly:reconly_dev@localhost:5432/reconly
```

**Or export directly:**
```bash
export DATABASE_URL=postgresql://reconly:reconly_dev@localhost:5432/reconly
```

**Connection string format:**
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

## Step 3: Run Database Migrations

Apply migrations to create the necessary tables:

```bash
cd reconly-oss/packages/api
python -m alembic upgrade head
```

This creates:
- `digest_chunks` table for storing text chunks with embeddings
- Vector indexes for fast similarity search
- Full-text search indexes

**Verify tables were created:**
```bash
psql postgresql://reconly:reconly_dev@localhost:5432/reconly

\dt
# Should show digest_chunks table

\d digest_chunks
# Should show embedding column with vector type

\q
```

## Step 4: Configure Embedding Provider

Choose an embedding provider. Ollama is recommended for local/free operation.

### Option A: Ollama (Recommended - Local & Free)

**1. Install Ollama:**

Visit [ollama.com](https://ollama.com) and download for your platform, or:

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Windows
# Download from https://ollama.com/download
```

**2. Start Ollama service:**

```bash
# Linux/macOS
ollama serve

# Windows
# Ollama runs as a service automatically
```

**3. Pull embedding model:**

```bash
# Recommended: BGE-M3 (1024 dimensions, multilingual)
ollama pull bge-m3

# Alternative: Nomic Embed Text (768 dimensions, fast)
ollama pull nomic-embed-text
```

**4. Configure Reconly:**

In your `.env` file:
```bash
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
OLLAMA_BASE_URL=http://localhost:11434  # Default
```

**Test connection:**
```bash
curl http://localhost:11434/api/tags
# Should return list of available models
```

### Option B: OpenAI

**1. Get API key:**

Visit [platform.openai.com](https://platform.openai.com) and create an API key.

**2. Configure Reconly:**

In your `.env` file:
```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small  # or text-embedding-3-large
OPENAI_API_KEY=sk-...your-key...
```

**Cost:** ~$0.0001 per 1K tokens (~$0.01 per 100 digests)

### Option C: HuggingFace

**1. Get API token:**

Visit [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) and create a token.

**2. Configure Reconly:**

In your `.env` file:
```bash
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=BAAI/bge-m3
HF_API_KEY=hf_...your-token...
```

**Free tier available** for development usage.

## Step 5: Embed Existing Digests

If you have existing digests, generate embeddings for them:

**Option A: Via API (when running):**

```bash
# Start API server
cd reconly-oss/packages/api
python -m uvicorn reconly_api.main:app --reload

# In another terminal, trigger embedding
curl -X POST http://localhost:8000/api/v1/embeddings/embed-all \
  -H "Content-Type: application/json" \
  -d '{"limit": 100}'
```

**Option B: Via Python:**

```python
from reconly_core.database import get_db
from reconly_core.rag import EmbeddingService

# Get database session
db = next(get_db())

# Create embedding service
service = EmbeddingService(db)

# Embed digests without embeddings (async)
import asyncio
async def embed_all():
    results = await service.embed_unembedded_digests(
        limit=None,  # Process all
        include_failed=True
    )
    print(f"Embedded {len(results)} digests")

asyncio.run(embed_all())
```

**Monitor progress:**

```python
stats = service.get_chunk_statistics()
print(f"Total chunks: {stats['total_chunks']}")
print(f"Completed: {stats['embedding_status']['completed']}")
print(f"Pending: {stats['embedding_status']['pending']}")
print(f"Failed: {stats['embedding_status']['failed']}")
```

## Step 6: Test the System

### Test Vector Search

```python
from reconly_core.database import get_db
from reconly_core.rag import get_embedding_provider
from reconly_core.rag.search import VectorSearchService

db = next(get_db())
provider = get_embedding_provider(db=db)
search = VectorSearchService(db, provider)

# Search for similar content
import asyncio
results = asyncio.run(search.search(
    query="machine learning trends",
    limit=5
))

for r in results:
    print(f"Score: {r.score:.3f} - {r.text[:100]}...")
```

### Test RAG Question Answering

```python
from reconly_core.rag import RAGService, RAGFilters
from reconly_core.summarizers import get_summarizer

# Get LLM summarizer
summarizer = get_summarizer(db=db, enable_fallback=False)

# Create RAG service
rag = RAGService(db, provider, summarizer)

# Ask a question
result = asyncio.run(rag.query(
    question="What are the latest AI trends?",
    filters=RAGFilters(days=30),  # Last 30 days
    max_chunks=10
))

print(f"Answer: {result.answer}")
print(f"Grounded: {result.grounded}")
print(f"\nCitations:")
for citation in result.citations:
    print(f"[{citation.id}] {citation.digest_title}")
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://localhost/reconly | PostgreSQL connection string |
| `EMBEDDING_PROVIDER` | `ollama` | Provider name: ollama, openai, huggingface |
| `EMBEDDING_MODEL` | `bge-m3` | Model identifier (provider-specific) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OPENAI_API_KEY` | - | OpenAI API key (if using OpenAI) |
| `HF_API_KEY` | - | HuggingFace token (if using HF) |

### Database Settings (Optional)

You can also configure via the settings API:

```bash
# Set embedding provider
curl -X PUT http://localhost:8000/api/v1/settings/embedding.provider \
  -H "Content-Type: application/json" \
  -d '{"value": "ollama"}'

# Set embedding model
curl -X PUT http://localhost:8000/api/v1/settings/embedding.model \
  -H "Content-Type: application/json" \
  -d '{"value": "bge-m3"}'

# Set chunk size
curl -X PUT http://localhost:8000/api/v1/settings/embedding.chunk_size \
  -H "Content-Type: application/json" \
  -d '{"value": 384}'
```

## Troubleshooting

### PostgreSQL Connection Issues

**Error:** `could not connect to server`

```bash
# Check if PostgreSQL is running
docker-compose -f docker/docker-compose.postgres.yml ps

# Check logs
docker-compose -f docker/docker-compose.postgres.yml logs postgres

# Restart PostgreSQL
docker-compose -f docker/docker-compose.postgres.yml restart postgres
```

### pgvector Extension Not Found

**Error:** `extension "vector" is not available`

```bash
# Verify pgvector image
docker-compose -f docker/docker-compose.postgres.yml pull postgres

# Check extension in database
docker exec -it reconly-postgres psql -U reconly -d reconly -c "SELECT * FROM pg_extension WHERE extname='vector';"

# If missing, enable manually
docker exec -it reconly-postgres psql -U reconly -d reconly -c "CREATE EXTENSION vector;"
```

### Ollama Connection Issues

**Error:** `Could not connect to Ollama server`

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama (Linux/macOS)
ollama serve

# Check Ollama logs
journalctl -u ollama -f  # Linux
# Or check system logs on macOS
```

### Embedding Generation Fails

**Error:** `Embedding model 'bge-m3' is not available`

```bash
# Pull the model
ollama pull bge-m3

# List available models
ollama list

# Test embedding directly
curl http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3",
  "prompt": "test text"
}'
```

### Search Returns No Results

**Check embedding status:**

```sql
-- Connect to database
psql postgresql://reconly:reconly_dev@localhost:5432/reconly

-- Check digest embedding status
SELECT embedding_status, COUNT(*)
FROM digests
GROUP BY embedding_status;

-- Check chunks
SELECT COUNT(*) FROM digest_chunks;

-- Find digests without embeddings
SELECT id, title, embedding_status
FROM digests
WHERE embedding_status IS NULL OR embedding_status = 'failed'
LIMIT 10;
```

**Re-embed failed digests:**

```python
from reconly_core.rag import EmbeddingService
service = EmbeddingService(db)

# Re-embed failed digests
await service.embed_unembedded_digests(
    include_failed=True,
    limit=100
)
```

## Performance Tuning

### Indexing Strategy

For best performance, ensure vector indexes are created:

```sql
-- Check existing indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'digest_chunks';

-- Create HNSW index if missing (recommended for <500K chunks)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON digest_chunks
USING hnsw (embedding vector_cosine_ops);

-- Or create IVFFlat for large datasets (>1M chunks)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
ON digest_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Chunk Size Optimization

Adjust chunk size based on your content:

```bash
# For technical documentation (more context)
embedding.chunk_size=512
embedding.chunk_overlap=96

# For news articles (standard)
embedding.chunk_size=384
embedding.chunk_overlap=64

# For tweets/short content
embedding.chunk_size=256
embedding.chunk_overlap=32
```

### Database Maintenance

Run periodic maintenance:

```sql
-- Analyze table for query optimization
ANALYZE digest_chunks;

-- Vacuum to reclaim space
VACUUM ANALYZE digest_chunks;

-- Reindex if performance degrades
REINDEX INDEX idx_chunks_embedding_hnsw;
```

## Next Steps

- **Explore the API**: See API documentation for RAG endpoints
- **Build a search UI**: Integrate search into your frontend
- **Tune parameters**: Experiment with chunk sizes and search modes
- **Monitor performance**: Track embedding costs and search latency

For more details, see:
- [ARCHITECTURE.md - RAG Knowledge System](../../ARCHITECTURE.md#rag-knowledge-system)
- [API Documentation](api.md) - RAG endpoints
- [Development Guide](development.md) - Contributing to RAG features
