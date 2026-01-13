# Reconly - Open Source RSS Aggregator with AI Summarization

> **Self-host your intelligent RSS reader** - Aggregate feeds, summarize with AI, all under your control.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-447%20passing-brightgreen.svg)]()

## Features

- **Multi-Source Fetching**: RSS feeds, YouTube channels, and websites
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

## Quick Start

```bash
cd reconly-oss

# Install Python packages
pip install -e packages/core
pip install -e packages/api

# Start the API server (database is created automatically)
python -m uvicorn reconly_api.main:app --reload --port 8000
```

Open `http://localhost:8000` for the API docs.

**Optional: Web UI (requires Node.js 18+)**

```bash
cd ui
npm install
npm run dev
```

UI runs at `http://localhost:4321`

**Optional: Custom configuration**

Copy `.env.example` to `.env` and edit to configure API keys, providers, etc.

**Next**: [Full Setup Guide](docs/setup.md) | [Choose an AI Provider](docs/setup.md#4-choose-your-ai-provider)

## AI Providers

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **Ollama** | Free | 100% Local | [5 min setup](docs/setup.md#option-a-ollama-local-free-private) |
| **HuggingFace** | Free tier | Cloud | API key |
| **OpenAI** | ~$0.02/article | Cloud | API key |
| **Anthropic** | ~$0.04/article | Cloud | API key |

**Recommendation**: Start with [Ollama](https://ollama.com/) for free, private, offline summarization.

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
docker-compose -f reconly-oss/docker/docker-compose.postgres.yml up -d

# 2. Configure database
export DATABASE_URL=postgresql://reconly:reconly_dev@localhost:5432/reconly

# 3. Run migrations
cd reconly-oss/packages/api
python -m alembic upgrade head

# 4. Configure embedding provider (optional, defaults to Ollama)
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=bge-m3
```

**Documentation:** See [ARCHITECTURE.md - RAG Knowledge System](../ARCHITECTURE.md#rag-knowledge-system) for complete details.

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

## Packages

- **reconly-core**: CLI, fetchers, summarizers, database models
- **reconly-api**: FastAPI server, REST endpoints, built-in scheduler

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

### Digest Modes

Each feed has a configurable **digest mode** that controls how content is consolidated:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `individual` | One digest per item (default) | Detailed per-article summaries |
| `per_source` | One digest per source | Source-level briefings |
| `all_sources` | One digest per feed run | Cross-source synthesis ("Daily Briefing") |

For `per_source` and `all_sources` modes, provenance is tracked via `DigestSourceItems`, allowing you to trace "This briefing synthesized 3 items from Bloomberg, 2 from Reuters."

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

## Enterprise Features

Need **multi-user authentication**, **team management**, or **managed hosting**?

Check out **[Reconly Enterprise](https://reconly.eu)** for SSO, team management, and managed SaaS.

## Contributing

We love contributions! See [Development Guide](docs/development.md) for setup and guidelines.

## License

**AGPL-3.0** - See [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/reconlyeu/reconly/issues)
- **Discussions**: [GitHub Discussions](https://github.com/reconlyeu/reconly/discussions)

---

**Made with care for the self-hosting community**
