# Feature Setup Guide

After completing the [Quick Start](../index.md), you have RSS, YouTube, and website summarization working. This guide shows how to enable additional features based on your needs and hardware capabilities.

## Feature Matrix

| Feature | Quick Start | What You Need |
|---------|-------------|---------------|
| **Content Summarization** (RSS, YouTube, Website) | ✅ Included | Ollama + any model |
| **Chat Interface** | ✅ Included | Same as above |
| **Webhook & PKM Export** | ✅ Included | Just configure URL |
| **Semantic Search & Knowledge Graph** | ❌ Optional | Embedding model |
| **AI Research Agents** | ❌ Optional | GPT Researcher + search provider |
| **Email Integration** | ❌ Optional | SMTP and/or IMAP credentials |

---

## 1. Semantic Search & Knowledge Graph

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

- **Comprehensive Reports**: 2000+ word reports with 20-50 sources
- **Multi-Source**: Searches the web, synthesizes findings, cites sources
- **Scheduled Research**: Run research on a schedule like any other source

### Requirements

- GPT Researcher package (powers the research engine)
- Search provider (SearXNG recommended)
- LLM with good reasoning (qwen2.5:7b minimum, larger models better)

### Docker Setup (Recommended)

If you're running Reconly with Docker Compose, GPT Researcher is already included in the image. Just start with the `research` profile to add SearXNG:

```bash
cd docker/oss
docker compose --profile research up -d
```

This starts SearXNG + Valkey alongside Reconly. SearXNG is available at `http://localhost:8888`.

Add to your `.env` to connect the API to SearXNG:
```bash
SEARXNG_URL=http://searxng:8080
```

Verify GPT Researcher is available:
```bash
curl http://localhost:8000/api/v1/agent-runs/capabilities
# Should show "comprehensive": {"available": true}
```

### Manual Setup (without Docker Compose)

If you're running Reconly directly (not via Docker), install GPT Researcher and a search provider separately.

**Install GPT Researcher:**
```bash
pip install -e "packages/core[research]"
```

**Configure a search provider:**

#### Option A: SearXNG (Recommended)

Self-hosted, unlimited searches, privacy-respecting.

```bash
docker run -d --name searxng \
  -p 8888:8080 \
  -e SEARXNG_BASE_URL=http://localhost:8888 \
  searxng/searxng
```

Add to `.env`:
```bash
SEARXNG_URL=http://localhost:8888
```

#### Option B: Tavily API

Cloud-based, easy setup. Get API key from [tavily.com](https://tavily.com) (1000 free searches/month).

```bash
TAVILY_API_KEY=tvly-your-key-here
```

#### Option C: DuckDuckGo

Works out of the box but has aggressive rate limits. Good for testing only.

### Using Agent Sources

1. Go to **Sources** → **Add Source**
2. Select **AI Agent** as source type
3. Enter your research topic (e.g., "Latest developments in quantum computing")
4. Choose strategy: Simple (fast) or Comprehensive (thorough)
5. Add to a feed and run

**Note:** Comprehensive research takes 3-5 minutes and uses significant LLM tokens.

**Detailed guide:** [AI Research Agents](sources/agent-research-source.md)

---

## 3. Email Integration

Send digests to your inbox and/or fetch newsletters to summarize. Configure one or both based on your needs.

### Sending Digests (SMTP)

Receive your feed digests via email on a schedule.

**Configure SMTP** (add to your `.env`):

```bash
# Gmail example
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Reconly Digests
SMTP_USE_TLS=true
```

**For Gmail**, create an App Password at [Google Account Security](https://myaccount.google.com/security) (requires 2-Step Verification).

**Other providers:**

| Provider | SMTP_HOST | Notes |
|----------|-----------|-------|
| SendGrid | `smtp.sendgrid.net` | Use `apikey` as username |
| Mailgun | `smtp.mailgun.org` | Domain-specific credentials |
| AWS SES | `email-smtp.{region}.amazonaws.com` | IAM credentials |

After configuring, enable email delivery in your feed settings.

### Fetching Newsletters (IMAP)

Summarize newsletters and email digests automatically.

**Setup:**
1. Go to **Sources** → **Add Source**
2. Select **Email (IMAP)**
3. Enter your IMAP credentials (Gmail requires an App Password)
4. Configure folders and filters

**Filtering options:**

| Option | Example |
|--------|---------|
| `folders` | `INBOX`, `Newsletters` |
| `from_filter` | `*@newsletter.com` |
| `subject_filter` | `*Weekly Digest*` |

**Detailed guides:** [SMTP Configuration](configuration.md#email-smtp) · [IMAP Source Setup](sources/imap-email-source.md)

---

## Hardware Recommendations

| Tier | RAM | Disk | Models |
|------|-----|------|--------|
| **Minimum** | 8GB | 10GB | qwen2.5:7b |
| **Recommended** | 16GB | 50GB | qwen2.5:7b + bge-m3 |

GPU is optional but speeds up inference. Any modern CPU works.

---

## Troubleshooting

### Embeddings Not Working

Chat says "No relevant content found" or semantic search returns nothing.

1. Check embedding model is pulled: `ollama list`
2. Verify EMBEDDING_MODEL in .env matches a pulled model
3. Re-embed digests: `curl -X POST localhost:8000/api/v1/embeddings/embed-all`

### Agent Research Fails

Agent sources fail with "Search provider not configured" or produce poor results.

1. Verify GPT Researcher is installed: `curl localhost:8000/api/v1/agent-runs/capabilities`
2. Set SEARXNG_URL or TAVILY_API_KEY in .env
3. Test search: `curl http://localhost:8888/search?q=test` (for SearXNG)
4. Restart Reconly

### "(no model selected)" in Chat

Chat sidebar shows provider but "(no model selected)".

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
