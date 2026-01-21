<p align="right">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL%203.0-blue.svg" alt="License: AGPL-3.0"/></a>
</p>

<p align="center">
  <img src="reconly-logo.png" alt="Reconly Logo" width="160"/>
</p>

<h1 align="center">Reconly — Privacy-First News & Research Intelligence</h1>

<p align="center">
  Aggregate all your sources, build knowledge in your system of choice, and keep full ownership of your data.
</p>

<p align="center">
  <img src="docs/images/demo.gif" alt="Reconly Demo - Feed Management, Configuration, and AI Digests" width="700"/>
  <br/>
  <sub>
    <a href="docs/images/FeedManagement.png">Feeds</a> ·
    <a href="docs/images/Create%20Feed.png">Create Feed</a> ·
    <a href="docs/images/Digests.png">Digests</a> ·
    <a href="docs/images/Chat.png">Chat</a> ·
    <a href="docs/images/Knowledge.png">Knowledge Graph</a> ·
    <a href="docs/images/E-Mail.png">E-Mail Digest</a>
  </sub>
</p>

---

## Why Reconly?

- **Research & Monitoring** — Aggregate RSS, YouTube, websites, email, and AI agents into briefings
- **Privacy-First** — Run offline with local AI (Ollama) and private search — data stays local
- **Smart Filtering** — Keyword filters and tags to focus on what matters
- **Cost-Optimized** — Free local models to premium cloud, with automatic fallbacks
- **Knowledge Export** — Sync to Obsidian, Logseq, or any PKM via Markdown/JSON
- **AI Chat** — Ask questions about your digests and get answers with citations
- **Knowledge Graph** — Discover topic connections with semantic search — MCP-enabled
- **Automation** — Webhooks for Zapier/n8n, plugins, and community bundles
- **Docker Ready** — Production setup in 5 minutes

---

## Quick Start

**Requirements:** Docker with 2GB+ RAM

```bash
# Clone and start
git clone https://github.com/reconlyeu/reconly.git
cd reconly/docker/oss
cp .env.example .env
docker compose up -d
```

Open **http://localhost:8000** — you'll see sample feeds, sources, and digests ready to explore.

> The default `.env` loads sample data automatically. Edit `.env` to customize settings.

### Configure AI (Optional)

To generate new summaries, configure an LLM provider:

**Option A: Ollama (Free, Local, Private)** — Recommended
```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2
ollama serve
```
Reconly auto-connects to Ollama on your host machine.

**Option B: Cloud Provider**

Edit `.env` and add your API key:
```bash
ANTHROPIC_API_KEY=sk-ant-...   # or
OPENAI_API_KEY=sk-...          # or
HUGGINGFACE_API_KEY=hf_...
```

### Useful Commands

```bash
docker compose logs -f api    # View logs
docker compose down           # Stop
docker compose down -v        # Stop and delete all data
docker compose up -d --build  # Rebuild after updates
```

### Development Setup

For contributing or running without Docker, see the [Setup Guide](docs/setup.md).

---

## Features

- **AI Research Agents**: Autonomous research agents that search the web and synthesize findings
- **Consolidated Digests**: Combine multiple items into single briefings with source attribution
- **Source Content Filters**: Include/exclude keywords to filter content before summarization
- **Digest Tagging**: Organize and filter digests with tags and autocomplete
- **Webhooks**: Receive notifications on feed completion for automation workflows
- **Cost Optimized**: Automatic fallback from free to paid providers
- **Privacy First**: Run completely offline with Ollama
- **Database-Driven Feeds**: Manage sources and feeds via CLI or API
- **Per-Feed Scheduling**: Cron-based scheduling for each feed
- **Template System**: Customizable prompt and report templates
- **Feed Bundles**: Export/import feed configurations as portable JSON packages
- **Web UI**: Modern interface for managing everything
- **Email Digests**: Send beautiful HTML digests via SMTP
- **Docker Ready**: Get started in 5 minutes

### Built-in & Extensible

All core components can be extended via the [plugin system](https://github.com/reconlyeu/reconly-extensions):

| Component | Built-in | Extensible |
|-----------|----------|------------|
| **Sources** | RSS, YouTube, Website, Email (IMAP), Research Agents | Custom fetchers |
| **LLM Providers** | Ollama, HuggingFace, OpenAI, Anthropic | Custom providers |
| **Exporters** | Obsidian, JSON, CSV | Custom formats |

---

## AI Providers

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **Ollama** | Free | 100% Local | [5 min setup](docs/setup.md#option-a-ollama-local-free-private) |
| **HuggingFace** | Free tier | Cloud | API key |
| **OpenAI** | ~$0.02/article | Cloud | API key |
| **Anthropic** | ~$0.04/article | Cloud | API key |

**Recommendation**: Start with [Ollama](https://ollama.com/) for free, private, offline summarization.

---

## AI Research Agents

Create autonomous research agents that investigate topics on schedule — like having a personal research assistant.

**How it works:**
1. You define a research prompt (e.g., "Latest developments in AI agents this week")
2. The agent uses web search and page fetching to gather information
3. Results are synthesized into a digest, just like other sources
4. Runs on schedule like any feed

**Quick Setup:**

```bash
# SearXNG (self-hosted, supports many search engines)
AGENT_SEARCH_PROVIDER=searxng
SEARXNG_URL=http://localhost:8080
```

SearXNG is a meta-search engine that can query Google, Bing, DuckDuckGo, Brave, and many more search backends - all while respecting your privacy.

**Creating an Agent Source:**

1. Go to **Sources → Add Source**
2. Select type: **Agent**
3. Enter your research prompt in the URL field
4. Set max iterations (default: 5)
5. Add to a Feed and run

**Example prompts:**
- "Research news about competitor companies Feedly and Inoreader this week"
- "Find recent developments in local LLM deployment and performance"
- "Summarize this week's AI safety research papers and discussions"

**Agent Run History:**

View detailed execution logs including:
- Tool calls (searches performed, pages fetched)
- Iterations and duration
- Sources consulted
- Token usage and costs

---

## RAG Knowledge System

Reconly includes semantic search and AI-powered question answering over your digest library.

**Features:**
- Semantic search across all digests using vector embeddings
- Natural language Q&A with citations
- Knowledge graph discovery
- Multi-provider embedding support (Ollama, OpenAI, HuggingFace)

The Docker setup includes PostgreSQL with pgvector — RAG features work out of the box.

**Configure embedding provider (optional):**
```bash
# In .env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
```

**Documentation:** See [RAG Setup Guide](docs/rag-setup.md) for details.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup Guide](docs/setup.md) | Installation, database, AI providers |
| [RAG Setup Guide](docs/rag-setup.md) | Embedding providers, semantic search |
| [Configuration Reference](docs/configuration.md) | All environment variables |
| [CLI Reference](docs/cli.md) | Command-line usage and options |
| [API Documentation](docs/api.md) | REST API endpoints |
| [Bundle Specification](docs/bundles/BUNDLE_SPEC.md) | Feed bundle JSON schema |
| [AI Bundle Creator](docs/bundles/BUNDLE_CREATOR_PROMPT.md) | LLM-assisted bundle creation |
| [Development Guide](docs/development.md) | Contributing, testing, UI development |
| [Deployment](docs/deployment.md) | Docker, production, Nginx |

---

## Architecture

```
User
  └── Sources (RSS, YouTube, websites)
  └── Feeds (groups of sources with schedule + digest mode)
        └── FeedRuns (execution history)
              └── Digests (summarized content)
                    └── DigestSourceItems (provenance for consolidated digests)
                    └── Tags (organization and filtering)
  └── Templates (prompts and reports)
```

### Packages

- **reconly-core**: CLI, fetchers, summarizers, database models
- **reconly-api**: FastAPI server, REST endpoints, built-in scheduler

### Digest Modes

Each feed has a configurable **digest mode** that controls how content is consolidated:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `individual` | One digest per item (default) | Detailed per-article summaries |
| `per_source` | One digest per source | Source-level briefings |
| `all_sources` | One digest per feed run | Cross-source synthesis ("Daily Briefing") |

For `per_source` and `all_sources` modes, provenance is tracked via `DigestSourceItems`, allowing you to trace "This briefing synthesized 3 items from Bloomberg, 2 from Reuters."

---

## Configuration

### Edition System

Reconly has two editions:

| Edition | Features | Use Case |
|---------|----------|----------|
| **OSS** (default) | Full functionality, no cost tracking | Self-hosted, bring your own API keys |
| **Enterprise** | Cost tracking, multi-user, billing | Commercial deployments |

Set via environment variable:
```bash
RECONLY_EDITION=oss  # or 'enterprise'
```

### Password Protection (Optional)

Protect your instance with a simple password:

```bash
# In .env
RECONLY_AUTH_PASSWORD=your-secure-password
```

When set:
- All API routes require authentication
- Web UI shows login page
- Supports session cookies and HTTP Basic Auth (for CLI/scripts)

```bash
# CLI access with Basic Auth
curl -u :your-password http://localhost:8000/api/v1/sources
```

---

## Enterprise Features

Need **multi-user authentication**, **team management**, or **managed hosting**?

Check out **[Reconly Enterprise](https://reconly.eu)** for SSO, team management, and managed SaaS.

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Container won't start | Check logs: `docker compose logs api` |
| Database connection error | Ensure postgres is healthy: `docker compose ps` |
| Empty UI (no data) | Set `LOAD_SAMPLE_DATA=true` in `.env` and restart |
| LLM not working | Ensure Ollama is running or API key is set in `.env` |

### Agent Source Issues

| Problem | Solution |
|---------|----------|
| "SearXNG URL required" | Set `SEARXNG_URL` in `.env` and restart the API |
| Agent returns empty results | Check SearXNG connectivity; try a simpler prompt |
| "Max iterations reached" | Increase `max_iterations` on the source (default: 5, max: 20) |

### RAG/Search Issues

| Problem | Solution |
|---------|----------|
| "pgvector extension not found" | Use the Docker setup — pgvector is included |
| Embeddings not generating | Check `EMBEDDING_PROVIDER` config; ensure Ollama has `bge-m3` model |
| Search returns no results | Embeddings may not be generated yet; check digest `embedding_status` |

---

## Contributing

We love contributions! See [Development Guide](docs/development.md) for setup and guidelines.

---

## License

**AGPL-3.0** — See [LICENSE](LICENSE) for details.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/reconlyeu/reconly/issues)
- **Discussions**: [GitHub Discussions](https://github.com/reconlyeu/reconly/discussions)

---

<p align="center">
  <strong>Made with care for the self-hosting community</strong>
</p>
