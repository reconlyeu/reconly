<p align="center">
  <img src="reconly-logo.png" alt="Reconly Logo" width="200"/>
</p>

<p align="center">
  <strong>Privacy-first research intelligence platform. Aggregate all your sources, build knowledge in your system of choice, and keep full ownership of your data.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="docs/setup.md">Documentation</a> •
  <a href="#use-cases">Use Cases</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL%203.0-blue.svg" alt="License: AGPL-3.0"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/></a>
  <img src="https://img.shields.io/badge/tests-447%20passing-brightgreen.svg" alt="Tests"/>
  <a href="https://github.com/reconlyeu/reconly/commits/main"><img src="https://img.shields.io/github/last-commit/reconlyeu/reconly" alt="Last Commit"/></a>
</p>

---

> **Status:** Beta - Stable core, API may change. Actively developed.

---

## Why Reconly?

- **Privacy-First** — Run completely offline with local AI (Ollama, more coming soon)
- **AI Research Agents** — Autonomous web research on any topic
- **Consolidated Digests** — Turn dozens of articles from multiple sources into AI-summarized briefings, customized to your needs
- **Smart Filtering** — Keyword-based content filters
- **Cost-Optimized** — From local models to cloud open-source to premium commercial, with automatic fallbacks
- **Docker Ready** — Production setup in 5 minutes

---

## Table of Contents

- [Quick Start](#quick-start)
- [Use Cases](#use-cases)
- [Features](#features)
- [AI Providers](#ai-providers)
- [AI Research Agents](#ai-research-agents)
- [RAG Knowledge System](#rag-knowledge-system-optional)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/reconlyeu/reconly.git
cd reconly

# Start all services (API + PostgreSQL)
cd docker/oss
docker-compose up -d

# Access the API
open http://localhost:8000/docs
```

### Option 2: Manual Setup

**Prerequisites:** Python 3.10+, PostgreSQL 16+ (or use Docker for database only)

```bash
# 1. Install Python packages
pip install -e packages/core
pip install -e packages/api

# 2. Start PostgreSQL (if not running)
docker-compose -f docker/docker-compose.postgres.yml up -d

# 3. Configure database
export DATABASE_URL=postgresql://reconly:reconly@localhost:5432/reconly

# 4. Run migrations
cd packages/api && python -m alembic upgrade head

# 5. Start the API server
python -m uvicorn reconly_api.main:app --reload --port 8000
```

### Optional: Web UI

```bash
cd ui
npm install
npm run dev
# UI runs at http://localhost:4321
```

### Next Steps

1. **Configure an AI Provider** — Start with [Ollama](https://ollama.com/) for free, private summarization
2. **Add your first feed** — Via the UI at http://localhost:4321 or the API
3. **Read the full guide** — [Setup Guide](docs/setup.md)

---

## Use Cases

- **Research & Monitoring** — Aggregate RSS feeds, YouTube channels, websites, email (IMAP), and autonomous research agents into consolidated briefings
- **Privacy-First Intelligence** — Run entirely offline with local AI (Ollama) — your data never leaves your machine
- **Knowledge Management** — Export digests to Obsidian, Logseq, or any PKM tool via Markdown, JSON, or custom formats
- **Knowledge Graph** — Discover connections between topics with semantic search and AI-powered Q&A over your digest library
- **Automation Workflows** — Trigger webhooks on feed completion for integration with Zapier, n8n, or custom pipelines
- **Extensibility** — Connect new sources and destinations via plugins, or install community bundles from the marketplace

---

## Features

- **Multi-Source Fetching**: RSS feeds, YouTube channels, and websites
- **AI Research Agents**: Autonomous research agents that search the web and synthesize findings
- **AI Summarization**: Local (Ollama), Free (HuggingFace), and Cloud (OpenAI, Anthropic)
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
- **Extensible**: Plugin architecture for custom fetchers and exporters
- **Docker Ready**: Get started in 5 minutes

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
# Option A: Brave Search (recommended, free tier at https://brave.com/search/api/)
AGENT_SEARCH_PROVIDER=brave
BRAVE_API_KEY=your-api-key

# Option B: SearXNG (self-hosted, fully private)
AGENT_SEARCH_PROVIDER=searxng
SEARXNG_URL=http://localhost:8080
```

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

## RAG Knowledge System (Optional)

Reconly includes semantic search and AI-powered question answering over your digest library.

**Features:**
- Semantic search across all digests using vector embeddings
- Natural language Q&A with citations
- Knowledge graph discovery
- Multi-provider embedding support (Ollama, OpenAI, HuggingFace)

**Requirements:**
- PostgreSQL with pgvector extension (for production)
- Embedding provider (Ollama recommended for local/free)

**Quick Setup:**

```bash
# 1. Start PostgreSQL with pgvector
docker-compose -f docker/docker-compose.postgres.yml up -d

# 2. Configure database
export DATABASE_URL=postgresql://reconly:reconly_dev@localhost:5432/reconly

# 3. Run migrations
cd packages/api
python -m alembic upgrade head

# 4. Configure embedding provider (optional, defaults to Ollama)
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=bge-m3
```

**Documentation:** See [RAG Setup Guide](docs/rag-setup.md) for complete details.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup Guide](docs/setup.md) | Installation, database, AI providers |
| [RAG Setup Guide](docs/rag-setup.md) | PostgreSQL + pgvector, embedding providers, semantic search |
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

### Agent Source Issues

| Problem | Solution |
|---------|----------|
| "Brave API key required" | Set `BRAVE_API_KEY` in `.env` and restart the API |
| "SearXNG URL required" | Set `SEARXNG_URL` in `.env` or switch to `AGENT_SEARCH_PROVIDER=brave` |
| Agent returns empty results | Check search provider connectivity; try a simpler prompt |
| "Max iterations reached" | Increase `max_iterations` on the source (default: 5, max: 20) |
| Search rate limit errors | Brave free tier: 2000 queries/month; consider SearXNG for unlimited |
| Agent runs but no digest | Ensure the agent source is added to a Feed and the feed is run |

### Common API Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 404 on `/api/v1/feeds/` | Server not running | Start with `uvicorn reconly_api.main:app` |
| 401 Unauthorized | Password protection enabled | Set `RECONLY_AUTH_PASSWORD` or authenticate |
| 500 Database error | PostgreSQL not running | Start PostgreSQL: `docker-compose up -d postgres` |
| LLM timeout | Provider unreachable | Check Ollama is running or API keys are valid |

### RAG/Search Issues

| Problem | Solution |
|---------|----------|
| "pgvector extension not found" | Run: `CREATE EXTENSION vector;` in PostgreSQL |
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
