# Feature Setup Guide

After completing the [Quick Start](../README.md#quick-start), you have basic RSS summarization working. This guide shows how to enable additional features based on your needs and hardware capabilities.

## Feature Matrix

| Feature | Quick Start | What You Need | Setup Time |
|---------|-------------|---------------|------------|
| **RSS/YouTube Summarization** | ✅ Included | Ollama + any model | - |
| **Chat Interface** | ✅ Included | Same as above | - |
| **Semantic Search (RAG)** | ❌ Needs setup | Embedding model | ~5 min |
| **Knowledge Graph** | ❌ Needs setup | Embedding model | ~5 min |
| **AI Research Agents** | ❌ Needs setup | Search provider | ~10 min |
| **Email Fetching** | ❌ Needs setup | IMAP credentials | ~5 min |
| **GPT Researcher (Deep)** | ❌ Needs setup | pip install + search | ~15 min |

---

## 1. Semantic Search & Knowledge Graph (RAG)

Enable intelligent search across your digest archive and visualize topic connections.

### What You Get

- **Semantic Search**: Find digests by meaning, not just keywords ("articles about startup funding" finds "Series A round" articles)
- **Chat with Citations**: Ask questions and get answers with source citations
- **Knowledge Graph**: Visualize relationships between topics

### Requirements

- PostgreSQL with pgvector (already running from Quick Start)
- Embedding model in Ollama (~2GB additional disk space)

### Setup

**1. Pull an embedding model:**

```bash
# Recommended: BGE-M3 (multilingual, high quality)
ollama pull bge-m3

# Alternative: Nomic (faster, English-focused)
ollama pull nomic-embed-text
```

**2. Configure (add to your `.env`):**

```bash
# Embedding configuration
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
```

**3. Restart Reconly:**

```bash
# If using Docker
cd docker/oss && docker compose restart

# If running directly
# Restart the API server
```

**4. Embed existing digests** (optional, for existing data):

```bash
curl -X POST http://localhost:8000/api/v1/embeddings/embed-all
```

New digests are automatically embedded after each feed run.

### Verify It Works

1. Go to **Chat** in the UI
2. Ask: "What topics have I read about this week?"
3. You should get answers with citations to specific digests

**Detailed guide:** [RAG Setup](rag-setup.md)

---

## 2. AI Research Agents

Enable autonomous web research on topics you define.

### What You Get

- **Automated Research**: Define a topic, get comprehensive reports
- **Multi-Source**: Searches the web, synthesizes findings, cites sources
- **Scheduled Research**: Run research on a schedule like any other source

### Requirements

- Search provider (SearXNG recommended for self-hosted, or Tavily API)
- LLM with good reasoning (qwen2.5:7b works, larger models better)

### Setup Option A: SearXNG (Self-Hosted, Unlimited)

**1. Start SearXNG with Docker:**

```bash
docker run -d --name searxng \
  -p 8888:8080 \
  -e SEARXNG_BASE_URL=http://localhost:8888 \
  searxng/searxng
```

**2. Configure (add to your `.env`):**

```bash
SEARXNG_URL=http://localhost:8888
```

### Setup Option B: Tavily API (Cloud, Easy)

**1. Get API key** from [tavily.com](https://tavily.com) (1000 free searches/month)

**2. Configure:**

```bash
TAVILY_API_KEY=tvly-your-key-here
```

### Setup Option C: DuckDuckGo (No Setup, Rate Limited)

Works out of the box but has aggressive rate limits. Good for testing.

### Using Agent Sources

1. Go to **Sources** → **Add Source**
2. Select **AI Agent** as source type
3. Enter your research topic (e.g., "Latest developments in quantum computing")
4. Choose strategy: Simple (fast) or Comprehensive (thorough)
5. Add to a feed and run

**Detailed guide:** [AI Research Agents](sources/agent-research-source.md)

---

## 3. GPT Researcher (Comprehensive Research)

Enable deep, multi-agent research for thorough analysis.

### What You Get

- **Comprehensive Reports**: 2000+ word reports with 20-50 sources
- **Multi-Agent Architecture**: Planner → Executors → Publisher
- **Deep Analysis**: Due diligence level research

### Requirements

- Search provider (from step 2 above)
- `gpt-researcher` Python package
- More capable LLM recommended (llama3.1:70b ideal, qwen2.5:7b minimum)

### Setup

**1. Install GPT Researcher:**

```bash
# If using pip install directly
pip install gpt-researcher>=0.9.0

# Or install with research extras
pip install -e "packages/core[research]"
```

**2. Verify installation:**

```bash
curl http://localhost:8000/api/v1/agent-runs/capabilities
```

You should see `"comprehensive": {"available": true}` in the response.

### Using Deep Research

1. Create an Agent source
2. Select **Comprehensive** or **Deep** strategy
3. Configure max subtopics (3-5 recommended)
4. Run the source

**Note:** Deep research takes 3-5 minutes and uses significant LLM tokens.

**Detailed guide:** [AI Research Agents - GPT Researcher](sources/agent-research-source.md#gpt-researcher-setup)

---

## 4. Email Fetching (IMAP)

Summarize newsletters and email digests automatically.

### What You Get

- **Newsletter Summarization**: Daily/weekly newsletter digests
- **Multi-Provider**: Gmail, Outlook, or any IMAP server
- **Filtering**: By sender, subject, or folder
- **OAuth Support**: Secure authentication for Gmail/Outlook

### Requirements

- IMAP credentials (app password recommended)
- Or OAuth setup for Gmail/Outlook

### Quick Setup (Generic IMAP)

**1. Create app password** (for Gmail):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Enable 2-Step Verification
   - Create an App Password for "Mail"

**2. Add email source:**
   - Go to **Sources** → **Add Source**
   - Select **Email (IMAP)**
   - Enter your credentials
   - Configure folders and filters

### Configuration Options

| Option | Description |
|--------|-------------|
| `folders` | Which folders to fetch from (`INBOX`, `Newsletters`, etc.) |
| `from_filter` | Filter by sender (`*@newsletter.com`) |
| `subject_filter` | Filter by subject (`*Weekly Digest*`) |

**Detailed guide:** [Email Source Setup](sources/imap-email-source.md)

---

## Hardware Recommendations

### Minimum (Basic Summarization)

- **CPU**: Any modern CPU
- **RAM**: 8GB
- **Disk**: 10GB free
- **GPU**: Not required
- **Model**: qwen2.5:7b or phi3:mini

### Recommended (Full Features)

- **CPU**: 4+ cores
- **RAM**: 16GB
- **Disk**: 50GB free (for models + embeddings)
- **GPU**: Optional but helpful
- **Models**: qwen2.5:7b + bge-m3 embedding

### Power User (Deep Research)

- **CPU**: 8+ cores
- **RAM**: 32GB+
- **Disk**: 100GB+ free
- **GPU**: Recommended (RTX 3080+ or Apple M1 Pro+)
- **Models**: llama3.1:70b or claude-3-5-sonnet

---

## Troubleshooting

### Embeddings Not Working

**Symptom:** Chat says "No relevant content found" or semantic search returns nothing.

**Fix:**
1. Check embedding model is pulled: `ollama list`
2. Verify EMBEDDING_MODEL in .env matches a pulled model
3. Re-embed digests: `curl -X POST localhost:8000/api/v1/embeddings/embed-all`

### Agent Research Fails

**Symptom:** Agent sources fail with "Search provider not configured"

**Fix:**
1. Set SEARXNG_URL or TAVILY_API_KEY in .env
2. Test search: `curl http://localhost:8888/search?q=test` (for SearXNG)
3. Restart Reconly

### "(no model selected)" in Chat

**Symptom:** Chat sidebar shows provider but "(no model selected)"

**Fix:**
1. Set OLLAMA_MODEL in .env (e.g., `OLLAMA_MODEL=qwen2.5:7b`)
2. Restart Reconly
3. Verify: `curl localhost:8000/api/v1/providers/default`

---

## See Also

- [Configuration Reference](configuration.md) - All environment variables
- [RAG Setup](rag-setup.md) - Detailed embedding configuration
- [Agent Sources](sources/agent-research-source.md) - Research agent details
- [Email Sources](sources/imap-email-source.md) - IMAP configuration
- [Deployment](deployment.md) - Production setup
