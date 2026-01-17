# Demo Mode Guide

Experience Reconly instantly with pre-populated sample data and local AI — no API keys or setup required.

## Overview

Demo mode provides a complete, self-contained Reconly experience that runs locally with Docker. It includes:

- **7 curated feeds** covering tech news, AI research, GitHub trends, financial analysis, and more
- **16 pre-configured sources** from popular RSS feeds, YouTube channels, and websites
- **Ollama LLM** for local, private AI summarization (no cloud API keys needed)
- **PostgreSQL with pgvector** for full database and RAG features
- **Ready-to-run configuration** to start generating digests immediately

Perfect for:
- Evaluating Reconly before setting up your own instance
- Testing features and UI without configuration
- Understanding how feeds, sources, and digests work together
- Learning Reconly's capabilities hands-on

## System Requirements

- **Docker Desktop** or Docker Engine with Docker Compose
- **8GB+ RAM** allocated to Docker (for Ollama model)
- **~10GB disk space** for Docker images and Ollama model
- **Operating System**: macOS, Linux, or Windows with WSL2

## Quick Start

### 1. Clone and Navigate

```bash
git clone https://github.com/reconlyeu/reconly.git
cd reconly/docker/demo
```

### 2. Start Demo Mode

```bash
docker compose up
```

**First startup** takes 2-5 minutes to:
1. Pull Docker images (PostgreSQL, Ollama, Reconly API)
2. Download the `qwen2.5:3b` model (~2GB)
3. Initialize the database and run migrations
4. Load demo seed data (feeds, sources, tags, templates)

You'll see progress in the terminal:
```
[INFO] Waiting for PostgreSQL to be ready...
[OK] PostgreSQL is ready!
[INFO] Waiting for Ollama to be ready...
[OK] Ollama is ready!
[INFO] Model 'qwen2.5:3b' is available!
[INFO] Running database migrations...
[OK] Database migrations complete!
[INFO] Loading demo seed data...
[OK] Demo seed data loaded successfully!
```

### 3. Access the Web UI

Open **http://localhost:8000** in your browser.

You'll see a demo mode indicator banner at the top of the page, confirming you're running in demo mode.

### 4. Explore the Demo

Navigate through the UI to explore:
- **Feeds** - 7 pre-configured feeds with different digest modes
- **Sources** - 16 sources including RSS, YouTube, and web content
- **Templates** - Prompt and report templates for customization
- **Tags** - Organizational tags for categorizing digests

To generate your first digests, click on a feed and hit "Run Now". The Ollama model will summarize the fetched content.

## What's Included

### Demo Feeds

The demo includes 7 feeds showcasing different use cases:

| Feed | Sources | Digest Mode | Description |
|------|---------|-------------|-------------|
| **Tech Daily** | Hacker News, TechCrunch, Fireship | Individual | Daily tech news from top sources |
| **GitHub Trending** | GitHub Trending, GitHub Blog | Individual | Trending repositories and platform updates |
| **NVDA Analyst Watch** | 5 financial sources | Individual | Comprehensive NVIDIA coverage and analyst ratings |
| **AI Research Digest** | ArXiv, Ollama Blog, Hugging Face | Per-Source | Latest AI/ML research and developments |
| **Self-Hosted Weekly** | r/selfhosted | Individual | Community picks for self-hosted tools |
| **Productivity Inbox** | TLDR Newsletter | Individual | Curated tech news summaries |
| **Paul Graham Essays** | Paul Graham's Blog | Individual | Timeless essays on startups and tech |

### Demo Sources

16 pre-configured sources across multiple types:

- **RSS Feeds**: Hacker News, TechCrunch, GitHub Blog, ArXiv, and more
- **YouTube**: Fireship channel
- **Financial News**: Seeking Alpha, Yahoo Finance, Motley Fool, MarketWatch, Benzinga
- **Developer Communities**: r/selfhosted
- **Newsletters**: TLDR
- **Blogs**: Paul Graham, Ollama, Hugging Face

### Digest Modes

Run the feeds to see different digest modes in action:
- **Individual digests** - One summary per article (most feeds)
- **Per-source digests** - Consolidated summaries per source (AI Research Digest)
- **Different templates** - Standard summaries, quick briefs, deep analysis, financial analysis

## Demo Mode Indicator

When running in demo mode, you'll see a banner at the top of the web UI:

> You're exploring Reconly in demo mode with sample data. [Learn how to set up your own instance](https://github.com/reconlyeu/reconly#quick-start)

This confirms you're using pre-loaded demo data and not your production instance.

## Customization

### Change the Port

By default, the demo runs on port 8000. To use a different port:

```bash
# Create a .env file in docker/demo/
echo "API_PORT=8080" > .env

# Start with custom port
docker compose up
```

Access at **http://localhost:8080**

### Force Reset Demo Data

If you've modified the demo data and want to reset to defaults:

```bash
# Stop and remove containers and volumes
docker compose down -v

# Start fresh
docker compose up
```

This completely resets:
- All database data
- All demo feeds, sources, and digests
- Ollama models (will re-download on next startup)

### Add Your Own API Keys

Want to test with commercial LLM providers? Edit `.env` in `docker/demo/`:

```bash
# Copy the example environment file
cp .env.demo .env

# Edit and add your API keys
nano .env
```

Add keys for providers you want to test:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
HUGGINGFACE_API_KEY=hf_...
```

Then restart:
```bash
docker compose down
docker compose up
```

## Transitioning to Production

Ready to set up your own instance? Follow these steps:

### Option 1: Use Production Docker Compose

```bash
# Navigate to production OSS setup
cd ../oss

# Copy and configure environment
cp .env.example .env
nano .env  # Add your LLM API keys

# Start production instance
docker compose up -d
```

Your data will be in a separate database. See [Setup Guide](setup.md) for complete instructions.

### Option 2: Manual Setup

For maximum control:

1. **Install dependencies**: Python 3.10+, PostgreSQL 16+
2. **Configure environment**: Copy `.env.example` to `.env` and add API keys
3. **Start database**: `docker compose -f docker/docker-compose.postgres.yml up -d`
4. **Run migrations**: `cd packages/api && python -m alembic upgrade head`
5. **Start API**: `python -m uvicorn reconly_api.main:app --reload --port 8000`

Full details in the [Setup Guide](setup.md).

### Migrating Demo Data

Demo data is for exploration only. For production:
1. Start with a fresh database (do not copy demo data)
2. Add your own sources and feeds through the UI
3. Configure your preferred LLM providers
4. Set up scheduling for automated feed runs

## Stopping Demo Mode

### Stop Containers (Keep Data)

```bash
docker compose down
```

This stops containers but preserves data in Docker volumes. Next `docker compose up` will restart with existing data.

### Stop and Remove All Data

```bash
docker compose down -v
```

This removes:
- All containers
- All volumes (database, Ollama models, app data)
- Network configuration

Next startup will be a fresh demo installation.

## Troubleshooting

### First Startup Takes Too Long

The initial startup downloads:
- PostgreSQL image (~50MB)
- Ollama image (~1GB)
- Reconly API image (~500MB)
- qwen2.5:3b model (~2GB)

This is normal. Subsequent startups are much faster (5-10 seconds).

### Port 8000 Already in Use

Change the port in `.env`:
```bash
echo "API_PORT=8080" > .env
docker compose up
```

### Ollama Model Download Fails

Check your internet connection and Docker disk space. If it fails, restart:

```bash
docker compose down
docker compose up
```

The model download will resume from where it left off.

### Demo UI Shows "Not Demo Mode"

Ensure you're running from `docker/demo/` directory, not `docker/oss/`:

```bash
cd docker/demo
docker compose up
```

### Database Connection Errors

PostgreSQL may not be ready yet. Wait 30 seconds and refresh the browser. If the issue persists:

```bash
docker compose restart postgres
```

### Out of Memory Errors

Ollama requires at least 8GB RAM. Check Docker Desktop settings:
- **macOS/Windows**: Docker Desktop → Settings → Resources → Memory (set to 8GB+)
- **Linux**: Docker has access to full system memory by default

## Advanced Configuration

### Use a Different Ollama Model

Edit `docker/demo/.env`:

```bash
OLLAMA_MODEL=llama3.1:8b
```

Restart to pull the new model:
```bash
docker compose down
docker compose up
```

### View Container Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f ollama
docker compose logs -f postgres
```

### Access PostgreSQL Directly

```bash
docker exec -it reconly-demo-postgres psql -U reconly -d reconly
```

### Shell into API Container

```bash
docker exec -it reconly-demo-api bash
```

## Next Steps

After exploring demo mode:
1. **Read the [Setup Guide](setup.md)** for production installation
2. **Check [Configuration Reference](configuration.md)** for all environment variables
3. **Explore [API Documentation](api.md)** for programmatic access
4. **Learn about [RAG Setup](rag-setup.md)** for semantic search and Q&A

## Support

- **Issues**: [GitHub Issues](https://github.com/reconlyeu/reconly/issues)
- **Discussions**: [GitHub Discussions](https://github.com/reconlyeu/reconly/discussions)
- **Documentation**: [docs/](.)

---

**Happy exploring!** Demo mode is the fastest way to understand what Reconly can do for your research workflow.
