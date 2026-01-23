# Setup Guide

This guide covers the complete setup for Reconly, including the backend API and web UI.

## Prerequisites

- **Python 3.10+** - For the backend API
- **Docker Desktop** - For PostgreSQL database
- **Node.js 18+** - For the web UI (optional, only if running the dev UI)
- **Git** - For cloning the repository

## Quick Start

### 1. Install Python Packages

```bash
# Install core package
pip install -e packages/core

# Install API package
pip install -e packages/api
```

> **Windows users**: If `pip` is not recognized, use `py -m pip` instead (e.g., `py -m pip install -e packages/core`).

### 2. Start PostgreSQL

Reconly requires PostgreSQL with the pgvector extension for full functionality.

```bash
# Start PostgreSQL with Docker
docker-compose -f docker/docker-compose.postgres.yml up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `reconly`
- User: `reconly`
- Password: `reconly_dev`

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env
```

The default `DATABASE_URL` in `.env.example` is already configured for the Docker PostgreSQL instance.

### 4. Start the Server

```bash
python -m uvicorn reconly_api.main:app --reload --port 8000
```

> **Windows users**: If `python` is not recognized, use `py -m uvicorn ...` instead.

The database schema is created automatically on first startup.

### 5. Populate Sample Data (Optional)

```bash
python packages/api/scripts/populate_sample_data.py
```

This creates:
- Default user: `dev@example.com`
- 4 sample sources (Hacker News, TechCrunch, Fireship YouTube, Paul Graham's Blog)
- 1 sample feed: "Tech Daily Digest" (scheduled daily at 8 AM)
- 6 system prompt templates (German/English: Standard, Quick Brief, Deep Analysis)
- 5 system report templates (Markdown, HTML Email, Simple List, Obsidian, JSON)

### 6. Configure Your AI Provider (Optional)

By default, Reconly uses HuggingFace with sensible defaults. To customize, copy `.env.example` to `.env` and edit.

Reconly supports multiple AI providers with intelligent fallback:

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **Ollama** | Free | 100% Local | 5 min |
| **LM Studio** | Free | 100% Local | 5 min |
| **HuggingFace** | Free tier | Cloud | API key |
| **OpenAI** | ~$0.02/article | Cloud | API key |
| **Anthropic** | ~$0.04/article | Cloud | API key |

**Recommendation**: Start with **[Ollama](https://ollama.com)** or **[LM Studio](https://lmstudio.ai)** for free, private, offline summarization.

#### Option A: Ollama (Local, Free, Private)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (choose based on your hardware)
ollama pull llama3.2      # Recommended: good balance of speed and quality
ollama pull qwen2.5:7b    # Lighter alternative for less powerful machines

# Configure (optional)
echo "DEFAULT_PROVIDER=ollama" >> .env
```

#### Option B: LM Studio (Local, Free, Private)

1. Download and install [LM Studio](https://lmstudio.ai)
2. Download a model (e.g., Llama 3.2, Qwen 2.5 7B for lighter hardware)
3. Start the local server (Developer tab → Start Server)
4. Configure Reconly:

```bash
# .env file
DEFAULT_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

#### Option C: Cloud Providers

```bash
# .env file
HUGGINGFACE_API_KEY=hf_your_key_here      # Free tier
OPENAI_API_KEY=sk-your_openai_key_here    # Paid
ANTHROPIC_API_KEY=sk-ant-your-key-here    # Paid
DEFAULT_PROVIDER=huggingface
```

### 7. Web UI (Optional)

The web UI requires Node.js 18+.

```bash
cd ui
npm install
npm run dev
```

> **Windows users**: If you see "running scripts is disabled", run this first in PowerShell:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

The UI runs at `http://localhost:4321` and connects to the API at `http://localhost:8000`.

**Endpoints:**
- API: `http://localhost:8000/api/v1/*`
- API docs: `http://localhost:8000/docs`
- Web UI (dev): `http://localhost:4321`

## Database Schema

The database includes the following tables:

| Table | Description |
|-------|-------------|
| `users` | User accounts (dev user for OSS mode) |
| `sources` | Content sources (RSS, YouTube, websites, blogs) |
| `feeds` | Feed configurations with schedules and template assignments |
| `feed_sources` | Many-to-many junction between feeds and sources |
| `prompt_templates` | LLM prompt configurations for summarization |
| `report_templates` | Jinja2 templates for digest output formatting |
| `feed_runs` | Execution history for feeds |
| `digests` | Processed content output |
| `tags` & `digest_tags` | Tagging system for digests |
| `llm_usage_logs` | Per-request LLM usage tracking |

## Database Migrations

For **fresh installations**, no migrations needed - tables are created automatically when the server starts.

For **upgrades** (existing installations), use Alembic to apply schema changes:

```bash
cd packages/api

# Run migrations (from packages/api directory)
python -m alembic upgrade head

# Create new migration (after model changes)
python -m alembic revision --autogenerate -m "description"

# View migration history
python -m alembic history
```

> **Note**: Run Alembic from the `packages/api` directory. The `.env` file in the project root is loaded automatically.

## Import Sources from YAML

You can manage sources via YAML import or directly in the database.

```bash
# Create config/sources.yaml
cat > config/sources.yaml << 'EOF'
sources:
  - name: "Hacker News"
    type: rss
    url: https://news.ycombinator.com/rss
    tags: [tech, news]
    enabled: true

  - name: "TechCrunch"
    type: rss
    url: https://techcrunch.com/feed/
    tags: [tech, startups]
    enabled: true

  # YouTube channel - fetches transcripts from recent videos
  - name: "Fireship"
    type: youtube
    url: https://www.youtube.com/@fireship
    tags: [tech, tutorials]
    enabled: true

  # YouTube single video
  - name: "Specific Tutorial"
    type: youtube
    url: https://www.youtube.com/watch?v=VIDEO_ID
    tags: [tutorial]
    enabled: true

settings:
  language: en
  provider: ollama
EOF

# Import sources and create a feed
python -m reconly_core.cli.main --import --create-feed --feed-name "Tech News"
```

> **YouTube Sources**: Both video URLs and channel URLs are supported. Channel URLs (like `@fireship`) will automatically fetch transcripts from recent videos. See [API Documentation](api.md#youtube-sources) for supported URL formats.

## Troubleshooting

### Windows: Python/pip not recognized
- Use `py` instead of `python` (e.g., `py -m pip install ...`)
- Or reinstall Python and check **"Add python.exe to PATH"** during installation

### Windows: npm scripts disabled
Run in PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Database connection errors
- Ensure PostgreSQL is running: `docker-compose -f docker/docker-compose.postgres.yml up -d`
- Verify `DATABASE_URL` in `.env` matches your PostgreSQL configuration
- Run migrations: `cd packages/api && python -m alembic upgrade head`

### UI Not Loading
- Verify `ui/dist/` directory exists and contains files
- Check FastAPI logs for UI_DIR path detection
- Rebuild UI: `cd ui && npm run build`

### API Errors
- Check database connection in `packages/api/reconly_api/config.py`
- Verify all dependencies installed
- Check logs for specific error messages

### CORS Issues
- Update `cors_origins` in config.py if developing UI separately
- Default allows localhost origins in development

## Next Steps

- [CLI Reference](cli.md) - Command-line usage
- [API Documentation](api.md) - REST API endpoints
- [UI Development](ui.md) - Frontend architecture
- [Deployment](deployment.md) - Docker and production setup
