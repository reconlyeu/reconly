# Deployment Guide

This guide covers deploying Reconly to production environments.

## Docker Deployment

### Quick Start

```bash
cd docker/oss

# Configure environment (optional - defaults work for local Ollama)
echo "API_PORT=8085" > .env  # Use a different port if 8000 is taken

# Start services
docker-compose up -d

# View logs
docker-compose logs -f api
```

The application will automatically:
- Create database tables on first startup
- Seed default prompt templates (German/English) and report templates
- Start the feed scheduler

Access the UI at `http://localhost:8085` (or your configured port).

### Docker Compose Configuration

The provided `docker/oss/docker-compose.yml` pulls a pre-built image from the container registry. The Dockerfile uses a multi-stage build:
1. **Stage 1**: Builds the Vue/Astro UI with Node.js
2. **Stage 2**: Creates the Python API image with bundled UI

See `docker/oss/docker-compose.yml` in the repository for the full configuration. Key settings:

- **`RECONLY_VERSION`** — Docker image tag (default: `latest`)
- **`API_PORT`** — Host port (default: `8000`)
- **`POSTGRES_PASSWORD`** — Database password (default: `reconly`)
- **`DEFAULT_PROVIDER`** — LLM provider: `ollama`, `openai`, `anthropic`, `huggingface`
- **`RECONLY_AUTH_PASSWORD`** — Optional password protection for the UI
- **`LOAD_SAMPLE_DATA`** — Load demo feeds on first start (default: `false`)

For building from source instead, use the dev compose file:
```bash
docker compose -f docker-compose.dev.yml up -d --build
```

### Rebuilding After Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Force full rebuild (no cache)
docker-compose build --no-cache && docker-compose up -d
```

### Windows Notes

When creating `.env` files on Windows PowerShell, use ASCII encoding:
```powershell
# Correct way to create .env on Windows
Set-Content -Path .env -Value "API_PORT=8085" -Encoding ASCII

# NOT: echo "API_PORT=8085" > .env  (creates UTF-16, which Docker can't read)
```

### Environment Variables

```bash
# Database (PostgreSQL required)
DATABASE_URL=postgresql://user:pass@host:5432/reconly

# LLM Providers
DEFAULT_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
HUGGINGFACE_API_KEY=hf_xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=xxx

# Security
SECRET_KEY=your-secret-key-here
CORS_ORIGINS=https://your-domain.com

# Scheduler (optional)
SCHEDULER_TIMEZONE=Europe/Berlin
```

## Manual Deployment

### 1. Install Dependencies

```bash
# System dependencies
apt-get update
apt-get install -y python3.11 python3.11-venv nodejs npm

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install packages
pip install -e packages/core
pip install -e packages/api
pip install gunicorn
```

### 2. Build UI

```bash
cd ui
npm install
npm run build
```

### 3. Initialize Database

The database is automatically initialized on first startup:
- Tables are created via SQLAlchemy's `create_all()`
- Default prompt and report templates are seeded

For schema migrations on existing databases:
```bash
cd packages/api
python -m alembic upgrade head
```

### 4. Run with Gunicorn

```bash
cd packages/api
gunicorn reconly_api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 5. Systemd Service

```ini
# /etc/systemd/system/reconly.service
[Unit]
Description=Reconly API
After=network.target

[Service]
User=reconly
Group=reconly
WorkingDirectory=/opt/reconly/packages/api
Environment="PATH=/opt/reconly/venv/bin"
ExecStart=/opt/reconly/venv/bin/gunicorn reconly_api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable reconly
sudo systemctl start reconly
```

## Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/reconly
server {
    listen 80;
    server_name reconly.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name reconly.example.com;

    ssl_certificate /etc/letsencrypt/live/reconly.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reconly.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (future)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## PostgreSQL Setup

PostgreSQL is required for Reconly:

```bash
# Install PostgreSQL
apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres createuser reconly
sudo -u postgres createdb reconly -O reconly
sudo -u postgres psql -c "ALTER USER reconly PASSWORD 'secure-password';"

# Update environment
export DATABASE_URL=postgresql://reconly:secure-password@localhost:5432/reconly

# Run migrations
cd packages/api
python -m alembic upgrade head
```

## Feed Scheduling

Feed scheduling is handled automatically by the built-in APScheduler. No external services like Redis or Celery are required.

The scheduler:
- Starts automatically with the API
- Uses your local timezone by default (configurable via `SCHEDULER_TIMEZONE`)
- Loads all feed schedules from the database on startup
- Syncs schedules when feeds are created/updated/deleted via the UI

To configure the timezone:
```bash
# .env
SCHEDULER_TIMEZONE=Europe/Berlin
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### Logs

```bash
# API logs (includes scheduler activity)
journalctl -u reconly -f
```

## Backup

### Database

```bash
# PostgreSQL backup
pg_dump reconly > backups/reconly-$(date +%Y%m%d).sql
```

### Configuration

```bash
tar -czf backups/config-$(date +%Y%m%d).tar.gz config/ .env
```

## Security Checklist

- [ ] Use HTTPS with valid SSL certificate
- [ ] Set strong `SECRET_KEY`
- [ ] Configure `CORS_ORIGINS` for your domain only
- [ ] Configure PostgreSQL with strong password
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Set `RECONLY_AUTH_PASSWORD` for password protection
- [ ] Regular backups
- [ ] Monitor logs for anomalies
