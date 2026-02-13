# Demo Mode Guide

Demo mode provides an **instant, fully-functional** Reconly experience with pre-loaded data. No LLM required — all summaries and embeddings are pre-generated.

## Quick Start

```bash
git clone https://github.com/reconlyeu/reconly.git
cd reconly/docker/demo
docker compose up
```

Open **http://localhost:8002** — ready in ~30 seconds.

## What's Included

| Content | Count |
|---------|-------|
| **Feeds** | 7 |
| **Sources** | 16 |
| **Digests** | 41 |
| **Embeddings** | 87 chunks |
| **Tags** | 12 |

### Demo Feeds

| Feed | Description | Digests |
|------|-------------|---------|
| **Tech Daily** | HN, TechCrunch, Fireship | 8 |
| **GitHub Trending** | Open source projects | 6 |
| **NVDA Analyst Watch** | NVIDIA financial analysis | 4 |
| **AI Research Digest** | ArXiv, Ollama, HuggingFace | 9 |
| **Self-Hosted Weekly** | Homelab and self-hosting | 5 |
| **Productivity Inbox** | Productivity tools | 4 |
| **Paul Graham Essays** | Startup wisdom | 4 |

### Demo Sources

16 pre-configured sources:

- **Tech News**: Hacker News, TechCrunch
- **YouTube**: Fireship
- **GitHub**: Trending repos, GitHub Blog
- **Finance**: Seeking Alpha, Yahoo Finance, Motley Fool, MarketWatch, Benzinga
- **AI/ML**: ArXiv, Ollama Blog, Hugging Face Blog
- **Communities**: r/selfhosted
- **Newsletters**: TLDR
- **Blogs**: Paul Graham Essays

## System Requirements

- **Docker** with 2GB+ RAM
- **~500MB disk space**
- No GPU required
- No API keys required

## Features to Explore

1. **Browse Feeds** — View the 7 pre-configured feeds with different digest modes
2. **Read Digests** — Explore 48 AI-generated summaries
3. **Knowledge Graph** — Semantic search across all content (143 embedded chunks)
4. **Tags & Filtering** — Filter content by topic tags
5. **Demo Banner** — UI indicator confirming demo mode

## Stopping Demo

```bash
docker compose down      # Stop containers (keeps data)
docker compose down -v   # Stop and reset all data
```

## Customization

### Change Port

Demo defaults to port 8002 (to avoid conflict with productive instance on 8000).

```bash
API_PORT=8080 docker compose up
```

Access at http://localhost:8080

### Reset Demo Data

```bash
docker compose down -v   # Remove volumes
docker compose up        # Fresh start
```

## Transitioning to Production

Demo mode is read-only with static data. To use Reconly for real:

1. **Stop demo**: `docker compose down -v`
2. **Set up production**: Follow the [Setup Guide](setup.md)
3. **Configure LLM**: Add Ollama/LM Studio locally or cloud API keys
4. **Add your sources**: Create feeds with your RSS/YouTube/email sources

### Production Setup

```bash
# Navigate to production OSS setup
cd ../oss

# Copy and configure environment
cp .env.example .env
# Edit .env to add your LLM API keys

# Start production instance
docker compose up -d
```

## Troubleshooting

### Port Already in Use

```bash
API_PORT=8080 docker compose up
```

### Database Connection Errors

Wait 10 seconds for PostgreSQL to initialize, then refresh browser.

### Demo Banner Not Showing

Ensure you're running from `docker/demo/` directory:
```bash
cd docker/demo
docker compose up
```

## Technical Details

- **Database**: PostgreSQL 16 with pgvector, pre-loaded via SQL init script
- **Embeddings**: Pre-computed with bge-m3 (1024 dimensions, 143 chunks)
- **No migrations**: Schema included in database dump
- **UI**: Served by FastAPI static file handler
- **Startup**: ~30 seconds (no model downloads)

## Next Steps

After exploring demo mode:
- [Setup Guide](setup.md) — Production installation
- [Configuration Reference](configuration.md) — Environment variables
- [RAG Setup](rag-setup.md) — Semantic search and Q&A

---

**Happy exploring!** Demo mode is the fastest way to understand Reconly's capabilities.
