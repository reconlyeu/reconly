# n8n Integration Guide

This guide shows how to integrate Reconly with [n8n](https://n8n.io/), the workflow automation platform.

## Overview

Reconly's REST API makes it easy to integrate with n8n for:
- Automated digest generation workflows
- Export to external services (Notion, Obsidian, etc.)
- Scheduled content processing
- Multi-step content pipelines

## Prerequisites

- Reconly API running and accessible
- n8n instance (self-hosted or cloud)
- Basic n8n workflow knowledge

## Authentication

If Reconly has authentication enabled (`RECONLY_AUTH_PASSWORD` set):

### Option 1: HTTP Basic Auth

```
Authorization: Basic base64(user:password)
```

In n8n, use the "HTTP Request" node with:
- Authentication: Basic Auth
- User: `user`
- Password: Your `RECONLY_AUTH_PASSWORD`

### Option 2: Session Cookie

First, login to get a session cookie:
```
POST /api/v1/auth/login/
Content-Type: application/json

{"password": "your-password"}
```

Then use the returned cookie in subsequent requests.

## Common Workflows

### 1. Scheduled Feed Processing

Trigger feed runs on a schedule:

```
┌─────────────┐     ┌────────────────┐     ┌───────────────┐
│ Cron Trigger│ ──▶ │ HTTP Request   │ ──▶ │ Slack/Email   │
│ Daily 9AM   │     │ POST /feeds/1/ │     │ Notification  │
│             │     │ runs/          │     │               │
└─────────────┘     └────────────────┘     └───────────────┘
```

**HTTP Request Node Configuration:**
- Method: `POST`
- URL: `http://your-reconly:8000/api/v1/feeds/{feed_id}/runs/`
- Body: `{"dry_run": false}`

### 2. Export Digests to Notion

Export new digests to Notion database:

```
┌─────────────┐     ┌────────────────┐     ┌────────────────┐     ┌───────────┐
│ Cron Trigger│ ──▶ │ HTTP Request   │ ──▶ │ Split Items    │ ──▶ │ Notion    │
│ Hourly      │     │ GET /digests/  │     │                │     │ Create    │
└─────────────┘     └────────────────┘     └────────────────┘     └───────────┘
```

**Get Digests Request:**
- Method: `GET`
- URL: `http://your-reconly:8000/api/v1/digests/?limit=10&created_after={last_sync}`

**Notion Create Page:**
- Database ID: Your Notion database
- Properties:
  - Title: `{{$json.title}}`
  - URL: `{{$json.url}}`
  - Summary: `{{$json.summary}}`

### 3. Export to Obsidian Vault (via Sync)

Export digests in Obsidian-compatible markdown:

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────┐
│ Cron Trigger│ ──▶ │ HTTP Request   │ ──▶ │ Write to File   │
│ Daily       │     │ GET /digests/  │     │ (Obsidian vault)│
│             │     │ export/?format │     │                 │
│             │     │ =obsidian      │     │                 │
└─────────────┘     └────────────────┘     └─────────────────┘
```

**Export Request:**
- Method: `GET`
- URL: `http://your-reconly:8000/api/v1/digests/export/?format=obsidian&created_after={date}`

The response is Markdown with YAML frontmatter, ready for Obsidian.

### 4. Webhook-Triggered Processing

Process new RSS items as they arrive:

```
┌─────────────┐     ┌────────────────┐     ┌────────────────┐
│ Webhook     │ ──▶ │ HTTP Request   │ ──▶ │ Process Result │
│ (RSS feed   │     │ POST /feeds/   │     │ (Email, Slack) │
│  webhook)   │     │ {id}/runs/     │     │                │
└─────────────┘     └────────────────┘     └────────────────┘
```

## API Endpoints Reference

### Feeds

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/feeds/` | GET | List all feeds |
| `/api/v1/feeds/{id}/` | GET | Get feed details |
| `/api/v1/feeds/{id}/runs/` | POST | Trigger feed run |

### Digests

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/digests/` | GET | List digests (with filters) |
| `/api/v1/digests/{id}/` | GET | Get single digest |
| `/api/v1/digests/export/` | GET | Export digests |

### Export Formats

| Format | Content-Type | Description |
|--------|--------------|-------------|
| `json` | application/json | JSON array of digests |
| `csv` | text/csv | CSV with headers |
| `obsidian` | text/markdown | Markdown with YAML frontmatter |

## Example: Full Automation Workflow

Complete workflow for daily digest processing and export:

```json
{
  "name": "Daily Reconly Digest",
  "nodes": [
    {
      "name": "Cron",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "triggerTimes": {
          "item": [{"hour": 9, "minute": 0}]
        }
      }
    },
    {
      "name": "Run Feed",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://reconly:8000/api/v1/feeds/1/runs/",
        "authentication": "basicAuth",
        "options": {}
      }
    },
    {
      "name": "Wait",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 5,
        "unit": "minutes"
      }
    },
    {
      "name": "Get New Digests",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "http://reconly:8000/api/v1/digests/?limit=50",
        "authentication": "basicAuth"
      }
    },
    {
      "name": "Send to Slack",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#digests",
        "text": "New digests available: {{$json.total}} items"
      }
    }
  ]
}
```

## Query Parameters for Filtering

When fetching digests, use these query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max items to return |
| `offset` | int | Skip first N items |
| `feed_id` | int | Filter by feed |
| `source_id` | int | Filter by source |
| `created_after` | datetime | Items created after date |
| `created_before` | datetime | Items created before date |
| `search` | string | Full-text search |

Example:
```
GET /api/v1/digests/?feed_id=1&created_after=2024-01-01&limit=20
```

## Error Handling

Add error handling nodes to your workflow:

```
┌─────────────┐     ┌────────────────┐
│ HTTP Request│ ──▶ │ IF Status != 200│ ──▶ Error Handler
│             │     │                │
└─────────────┘     └────────────────┘
                           │
                           ▼
                    Success Path
```

Common error responses:
- `401` - Authentication required
- `404` - Feed/digest not found
- `400` - Invalid request parameters
- `500` - Server error (check logs)

## Tips

1. **Use variables** for Reconly URL and credentials
2. **Add retry logic** for network resilience
3. **Store last sync timestamp** to avoid duplicate processing
4. **Use pagination** for large digest exports
5. **Set appropriate timeouts** for feed runs (can take minutes)

## Docker Compose Example

Running Reconly and n8n together:

```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=reconly
      - POSTGRES_PASSWORD=reconly
      - POSTGRES_DB=reconly
    volumes:
      - postgres_data:/var/lib/postgresql/data

  reconly:
    image: reconly:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://reconly:reconly@postgres:5432/reconly
    depends_on:
      - postgres

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=password
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  postgres_data:
  n8n_data:
```

## Resources

- [n8n Documentation](https://docs.n8n.io/)
- [Reconly API Documentation](/docs)
- [n8n HTTP Request Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/)
