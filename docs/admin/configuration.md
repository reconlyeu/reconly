# Configuration Reference

Complete reference for all Reconly environment variables and configuration options.

## Quick Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql://localhost/reconly` | PostgreSQL connection string |
| `DEFAULT_PROVIDER` | No | `ollama` | Default LLM provider |
| `RECONLY_EDITION` | No | `oss` | Edition (oss/enterprise) |
| `RECONLY_AUTH_PASSWORD` | No | *(none)* | Optional password protection |

## LLM Providers

### Ollama (Recommended for OSS)

Local, free, private AI summarization.

```bash
# .env
DEFAULT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL=llama3.2      # Or qwen2.5:7b for lighter hardware
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `DEFAULT_MODEL` | `llama3.2` | Model to use for summarization |

**Docker Note**: Use `http://host.docker.internal:11434` to access Ollama running on the host.

### LM Studio (Recommended for OSS)

Local, free, private AI summarization via [LM Studio](https://lmstudio.ai).

```bash
# .env
DEFAULT_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio server URL |

**Setup**: Download a model in LM Studio, then enable the local server in the Developer tab.

**Docker Note**: Use `http://host.docker.internal:1234/v1` to access LM Studio running on the host.

### OpenAI

```bash
OPENAI_API_KEY=sk-...
DEFAULT_PROVIDER=openai
OPENAI_MODEL=gpt-4-turbo
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4-turbo` | Model ID |
| `OPENAI_BASE_URL` | *(OpenAI default)* | Custom endpoint for OpenAI-compatible APIs |

### Anthropic Claude

```bash
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_PROVIDER=anthropic
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |

### HuggingFace

```bash
HUGGINGFACE_API_KEY=hf_...
DEFAULT_PROVIDER=huggingface
DEFAULT_HF_MODEL=glm-4
```

| Variable | Default | Description |
|----------|---------|-------------|
| `HUGGINGFACE_API_KEY` | *(required)* | HuggingFace API key |
| `DEFAULT_HF_MODEL` | `glm-4` | Model ID (glm-4, mixtral, llama, mistral) |

### Provider Priority

When `enable_fallback=True` (default), providers are tried in this order:

1. **Local providers** (Ollama, LM Studio) - Free, private
2. **Free cloud providers** (HuggingFace free tier) - No cost
3. **Paid cloud providers** (OpenAI, Anthropic) - Sorted by cost

## Edition & Authentication

### Edition System

```bash
# Backend edition
RECONLY_EDITION=oss  # or 'enterprise'

# Frontend edition (for UI builds)
VITE_EDITION=oss  # or 'enterprise'
```

| Edition | Features |
|---------|----------|
| `oss` | Full functionality, cost fields return 0.0 |
| `enterprise` | Real cost tracking, multi-user (requires enterprise package) |

### Password Protection

Optional simple password protection for OSS deployments:

```bash
RECONLY_AUTH_PASSWORD=your-secure-password
```

When set:
- All API routes require authentication
- Web UI shows login page
- Session cookies (7-day expiry) for browser access
- HTTP Basic Auth for CLI/scripts

```bash
# CLI access with Basic Auth
curl -u :your-password http://localhost:8000/api/v1/sources
```

## Database

PostgreSQL is required for Reconly. The database stores sources, feeds, digests, and embeddings.

```bash
# PostgreSQL connection string
DATABASE_URL=postgresql://user:password@localhost:5432/reconly
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://localhost/reconly` | PostgreSQL connection string |

## Email (SMTP)

For sending digest emails:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=digests@yourdomain.com
SMTP_FROM_NAME=Reconly Digests
SMTP_USE_TLS=true
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | *(required for email)* | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(required)* | SMTP username |
| `SMTP_PASSWORD` | *(required)* | SMTP password |
| `SMTP_FROM_EMAIL` | *(required)* | From email address |
| `SMTP_FROM_NAME` | `Reconly` | From display name |
| `SMTP_USE_TLS` | `true` | Use TLS encryption |

## Application Settings

```bash
# Security
SECRET_KEY=your-secret-key-change-in-production

# Server
DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(auto-generated)* | Secret for signing sessions |
| `DEBUG` | `false` | Enable debug mode |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `RATE_LIMIT_PER_MINUTE` | `60` | API rate limit per IP |

## Feed Scheduling

Feeds can be scheduled to run automatically using cron expressions. The scheduler runs in-process using APScheduler - no external services like Redis or Celery required.

```bash
# Optional: Set timezone for cron schedules (default: system local timezone)
SCHEDULER_TIMEZONE=Europe/Berlin
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_TIMEZONE` | *(system local)* | Timezone for cron expressions (e.g., `Europe/Berlin`, `America/New_York`) |

**Cron Expression Format**: `minute hour day month weekday`
- `0 9 * * *` - Daily at 9:00 AM
- `0 8 * * 1-5` - Weekdays at 8:00 AM
- `0 */6 * * *` - Every 6 hours

The scheduler starts automatically with the API and loads all feed schedules from the database.

## Summarization Settings

```bash
DEFAULT_LANGUAGE=en
DEFAULT_SUMMARY_LENGTH=150
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_LANGUAGE` | `en` | Default summary language (en, de) |
| `DEFAULT_SUMMARY_LENGTH` | `150` | Target summary word count |

## Runtime Settings API

Settings can be modified at runtime via the UI or API without restarting the application.

### Settings Priority

1. **Database** - Settings saved via UI (highest priority)
2. **Environment** - `.env` file values
3. **Defaults** - Built-in fallback values

### Editable vs Locked Settings

| Setting | Editable | Why |
|---------|----------|-----|
| Default Provider | Yes | No security risk |
| Default Model | Yes | No security risk |
| API Keys | No | Security - env-only |
| SMTP Host/Port | Yes | Non-secret |
| SMTP Password | No | Security - env-only |
| Export Format | Yes | User preference |

### API Endpoints

```bash
# Get all settings with source info
curl http://localhost:8000/api/v1/settings

# Update editable settings
curl -X PUT http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"settings": [{"key": "llm.default_provider", "value": "openai"}]}'

# Reset a setting to default
curl -X POST http://localhost:8000/api/v1/settings/reset \
  -H "Content-Type: application/json" \
  -d '{"key": "llm.default_provider"}'
```

### Source Indicators

The API returns a `source` field indicating where each value comes from:
- `database` - Saved via UI/API
- `environment` - From `.env` file
- `default` - Built-in fallback

## Docker Configuration

When running with Docker, additional considerations apply:

```bash
# docker/oss/.env
API_PORT=8000
OLLAMA_HOST=http://host.docker.internal:11434
DEFAULT_PROVIDER=ollama
```

### Accessing Host Services

From Docker containers, use `host.docker.internal` to access services on the host machine:

- Ollama: `http://host.docker.internal:11434`
- Local PostgreSQL: `postgresql://user:pass@host.docker.internal:5432/db`

## Example Configurations

### Minimal (Ollama Only)

```bash
# .env
DEFAULT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### Production (PostgreSQL + OpenAI)

```bash
# .env
DATABASE_URL=postgresql://reconly:secret@db.example.com:5432/reconly
DEFAULT_PROVIDER=openai
OPENAI_API_KEY=sk-...
SECRET_KEY=generate-with-openssl-rand-hex-32
SMTP_HOST=smtp.sendgrid.net
SMTP_USER=apikey
SMTP_PASSWORD=SG...
SMTP_FROM_EMAIL=digests@yourdomain.com
```

### Password-Protected Instance

```bash
# .env
DEFAULT_PROVIDER=ollama
RECONLY_AUTH_PASSWORD=my-secret-password
```

## Environment File Locations

| File | Purpose |
|------|---------|
| `.env` | Root configuration (API + development) |
| `docker/oss/.env` | Docker-specific configuration |
| `ui/.env` | UI build-time configuration |

## LLM Chat Configuration

The chat feature allows conversational interaction with Reconly through LLM tool calling.

### Provider Selection

```bash
# Default chat provider (ollama, openai, anthropic, lmstudio)
DEFAULT_CHAT_PROVIDER=ollama
```

If not set, uses the first available provider from the fallback chain.

### Recommended Models

#### Ollama (Local, Free)

Best for privacy and development. No API costs.

| Model | Best For | Notes |
|-------|----------|-------|
| **llama3.2** | General use | Best balance of speed and quality |
| **qwen2.5:7b** | Lower-powered hardware | Lighter model, still capable |
| **mistral** | Fast responses | Good for simple tasks |
| **qwen2.5** | Tool calling | Strong structured output |
| **codellama** | Technical questions | Better for code and technical content |

```bash
DEFAULT_CHAT_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

**Setup:**

```bash
# Choose based on your hardware
ollama pull llama3.2      # Recommended for most users
ollama pull qwen2.5:7b    # For less powerful machines (8GB RAM)
ollama serve
```

#### LM Studio (Local, Free)

Best for privacy with a visual interface. No API costs.

Use the same models as Ollama (Llama 3.2, Qwen 2.5, Mistral) downloaded through LM Studio's interface.

```bash
DEFAULT_CHAT_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
```

**Setup:** Download a model in LM Studio, then start the local server from the Developer tab.

#### OpenAI (Cloud, Paid)

Best for production use.

| Model | Best For | Speed | Cost |
|-------|----------|-------|------|
| **gpt-4o** | Production | Fast | Medium |
| **gpt-4-turbo** | Quality | Medium | High |
| **gpt-3.5-turbo** | Budget | Very Fast | Low |

```bash
DEFAULT_CHAT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

#### Anthropic Claude (Cloud, Paid)

Best for complex reasoning and long conversations.

| Model | Best For | Context | Speed |
|-------|----------|---------|-------|
| **claude-sonnet-4-20250514** | General use | 200K | Fast |
| **claude-3-5-haiku-20241022** | Budget | 200K | Very Fast |
| **claude-opus-4-5** | Quality | 200K | Slow |

```bash
DEFAULT_CHAT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Per-Conversation Settings

Override defaults when creating conversations:

```bash
curl -X POST http://localhost:8000/api/v1/chat/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Research Discussion",
    "model_provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514"
  }'
```

## See Also

- [Installation Guide](installation.md) - Getting started
- [Deployment Guide](deployment.md) - Production deployment
- [Adding Providers](../developer/adding-providers.md) - Custom LLM providers
