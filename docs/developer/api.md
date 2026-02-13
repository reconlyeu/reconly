# API Documentation

Reconly provides a RESTful API built with FastAPI for programmatic access to all features.

## Base URL

```
http://localhost:8000/api/v1
```

## Interactive Documentation

FastAPI provides built-in interactive docs:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Authentication

**Current Status**: Stub authentication (development only)
- All requests authenticated as default dev user
- Located in: `packages/api/reconly_api/auth/jwt.py`

**TODO**: Implement proper JWT authentication with user registration, token validation, and role-based access control.

## Endpoints

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/stats` | Dashboard statistics and overview |

### Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sources` | List all sources |
| POST | `/sources` | Create a new source |
| GET | `/sources/{id}` | Get source by ID |
| PUT | `/sources/{id}` | Update a source |
| PATCH | `/sources/{id}` | Partial update (e.g., toggle enabled) |
| DELETE | `/sources/{id}` | Delete a source |

#### Source Types

- `rss` - RSS/Atom feeds
- `youtube` - YouTube videos and channels (with transcript extraction)
- `website` - General websites
- `blog` - Blog feeds

#### Example: Create RSS Source

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hacker News",
    "type": "rss",
    "url": "https://news.ycombinator.com/rss",
    "enabled": true
  }'
```

#### YouTube Sources

YouTube sources support both individual videos and entire channels. The fetcher automatically detects URL type and extracts transcripts.

**Supported URL Formats:**

| Format | Example | Description |
|--------|---------|-------------|
| Video (watch) | `https://youtube.com/watch?v=dQw4w9WgXcQ` | Single video |
| Video (short) | `https://youtu.be/dQw4w9WgXcQ` | Single video (short URL) |
| Channel ID | `https://youtube.com/channel/UCxxxxxx` | Channel by ID |
| Handle | `https://youtube.com/@fireship` | Channel by handle |
| Custom URL | `https://youtube.com/c/Fireship` | Legacy custom URL |
| User URL | `https://youtube.com/user/Google` | Legacy user URL |

**Example: Create YouTube Video Source**

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Specific Tutorial",
    "type": "youtube",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "enabled": true
  }'
```

**Example: Create YouTube Channel Source**

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fireship",
    "type": "youtube",
    "url": "https://www.youtube.com/@fireship",
    "enabled": true
  }'
```

**How Channel Fetching Works:**

1. Channel ID is extracted from the URL (for handles, the page is fetched to resolve the ID)
2. The channel's RSS feed is fetched to get recent video list
3. Transcripts are fetched for each new video (up to 5 per run by default)
4. Videos without available transcripts are skipped gracefully
5. The `since` parameter filters videos published after the last feed run

**Notes:**
- Transcripts require either auto-generated or manually uploaded captions
- Default language preference: German (`de`), English (`en`)
- Channel sources respect incremental fetching (only new videos since last run)

#### Source Content Filters

Sources support keyword-based filtering to include or exclude content before summarization:

| Field | Type | Description |
|-------|------|-------------|
| `include_keywords` | `string[]` | Items must match at least one keyword to be processed |
| `exclude_keywords` | `string[]` | Items matching any keyword are excluded |
| `filter_mode` | `string` | Where to search: `title_only`, `content`, or `both` (default) |

**Example: Create Source with Content Filters**

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Filtered Tech News",
    "type": "rss",
    "url": "https://news.ycombinator.com/rss",
    "include_keywords": ["AI", "machine learning", "LLM"],
    "exclude_keywords": ["crypto", "blockchain"],
    "filter_mode": "both",
    "enabled": true
  }'
```

**Filter Behavior:**
- Keywords are case-insensitive
- Supports regex patterns (e.g., `"^Breaking:.*"`)
- Include filter: item must match **at least one** keyword
- Exclude filter: item must **not match any** keyword
- Both filters can be combined (include is applied first)

#### Source Configuration Options

The `config` JSON field supports type-specific settings:

| Option | Type | Description |
|--------|------|-------------|
| `max_items` | `int` | Maximum items to fetch per run (default varies by type) |
| `fetch_full_content` | `bool` | Fetch full article content (RSS) |

**Example: Source with max_items**

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Top HN Stories",
    "type": "rss",
    "url": "https://news.ycombinator.com/rss",
    "config": {"max_items": 10},
    "enabled": true
  }'
```

### Feeds

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/feeds` | List all feeds |
| POST | `/feeds` | Create a new feed |
| GET | `/feeds/{id}` | Get feed by ID |
| PUT | `/feeds/{id}` | Update a feed |
| DELETE | `/feeds/{id}` | Delete a feed |
| POST | `/feeds/{id}/run` | Manually trigger a feed run |
| GET | `/feeds/{id}/runs` | Get feed run history |

#### Example: Create Feed with Schedule

```bash
curl -X POST http://localhost:8000/api/v1/feeds \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Tech Digest",
    "schedule_cron": "0 8 * * *",
    "schedule_enabled": true,
    "source_ids": [1, 2, 3]
  }'
```

#### Example: Trigger Feed Run

```bash
curl -X POST http://localhost:8000/api/v1/feeds/1/run
```

#### Webhooks

Feeds can trigger webhooks on completion for automation workflows (n8n, Zapier, custom scripts).

Configure webhooks via the `output_config` JSON field:

```bash
curl -X PUT http://localhost:8000/api/v1/feeds/1 \
  -H "Content-Type: application/json" \
  -d '{
    "output_config": {
      "db": true,
      "webhook_url": "https://your-webhook.example.com/endpoint"
    }
  }'
```

**Webhook Payload:**

```json
{
  "event": "feed.run_completed",
  "feed_id": 1,
  "feed_name": "Morning Tech Digest",
  "feed_run_id": 42,
  "status": "completed",
  "digests": [
    {
      "id": 123,
      "title": "Article Title",
      "summary": "AI-generated summary...",
      "url": "https://example.com/article",
      "source_name": "Hacker News"
    }
  ],
  "stats": {
    "sources_processed": 3,
    "items_processed": 15,
    "digests_created": 12
  },
  "timestamp": "2026-01-08T10:30:00Z"
}
```

**Webhook Headers:**

| Header | Description |
|--------|-------------|
| `X-Reconly-Event` | Event type (e.g., `feed.run_completed`) |
| `X-Reconly-Delivery` | Unique delivery UUID |
| `X-Reconly-Timestamp` | Unix timestamp |
| `X-Reconly-Signature` | HMAC-SHA256 signature (if secret configured) |

**Notes:**
- Webhooks are sent asynchronously after feed completion
- Failed webhook delivery does not affect the feed run
- See [n8n Integration Guide](../admin/integrations/n8n.md) for workflow examples

### Feed Bundles

Feed bundles enable exporting and importing complete feed configurations as portable JSON packages.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/feeds/{id}/export` | Export feed as JSON bundle |
| POST | `/bundles/validate` | Validate bundle schema |
| POST | `/bundles/preview` | Preview import (dry run) |
| POST | `/bundles/import` | Import bundle to create feed |
| GET | `/bundles/schema` | Get JSON schema definition |

#### Example: Export Feed Bundle

```bash
curl -X POST http://localhost:8000/api/v1/feeds/1/export \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "category": "tech",
    "tags": ["ai", "news"]
  }'
```

**Response:**

```json
{
  "success": true,
  "filename": "morning-tech-digest-1.0.0.json",
  "bundle": {
    "schema_version": "1.0",
    "bundle": {
      "id": "morning-tech-digest",
      "name": "Morning Tech Digest",
      "version": "1.0.0",
      "sources": [
        {
          "name": "Hacker News",
          "type": "rss",
          "url": "https://news.ycombinator.com/rss"
        }
      ],
      "prompt_template": {
        "name": "Morning Tech Digest - Prompt Template",
        "system_prompt": "...",
        "user_prompt_template": "..."
      }
    }
  }
}
```

#### Example: Validate Bundle

```bash
curl -X POST http://localhost:8000/api/v1/bundles/validate \
  -H "Content-Type: application/json" \
  -d '{
    "bundle": {
      "schema_version": "1.0",
      "bundle": {
        "id": "my-feed",
        "name": "My Feed",
        "version": "1.0.0",
        "sources": [{"name": "Test", "type": "rss", "url": "https://example.com/feed"}]
      }
    }
  }'
```

**Response:**

```json
{
  "is_valid": true,
  "errors": [],
  "warnings": []
}
```

#### Example: Preview Import

```bash
curl -X POST http://localhost:8000/api/v1/bundles/preview \
  -H "Content-Type: application/json" \
  -d '{"bundle": {...}}'
```

Shows what would be created without actually importing.

#### Example: Import Bundle

```bash
curl -X POST http://localhost:8000/api/v1/bundles/import \
  -H "Content-Type: application/json" \
  -d '{
    "bundle": {...},
    "skip_duplicate_sources": true
  }'
```

**Response:**

```json
{
  "success": true,
  "feed_id": 5,
  "feed_name": "Morning Tech Digest",
  "sources_created": 2,
  "prompt_template_id": 10,
  "report_template_id": 8,
  "errors": [],
  "warnings": ["Source 'Hacker News' already exists, reusing"]
}
```

**Import Behavior:**
- Sources with matching URLs are reused (not duplicated)
- Templates are created with `origin='imported'` and bundle provenance
- Feed names are deduplicated with numeric suffix if needed

**See Also:**
- [Bundle Specification](bundles/BUNDLE_SPEC.md) - Complete schema reference
- [AI-Assisted Bundle Creation](bundles/BUNDLE_CREATOR_PROMPT.md) - LLM conversation guide

### Templates

#### Prompt Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/templates/prompt` | List prompt templates |
| POST | `/templates/prompt` | Create prompt template |
| GET | `/templates/prompt/{id}` | Get prompt template |
| PUT | `/templates/prompt/{id}` | Update prompt template |
| DELETE | `/templates/prompt/{id}` | Delete prompt template |

#### Report Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/templates/report` | List report templates |
| POST | `/templates/report` | Create report template |
| GET | `/templates/report/{id}` | Get report template |
| PUT | `/templates/report/{id}` | Update report template |
| DELETE | `/templates/report/{id}` | Delete report template |

### Digests

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/digests` | List digests with pagination |
| GET | `/digests/{id}` | Get digest by ID |
| PUT | `/digests/{id}` | Update digest (e.g., tags) |
| DELETE | `/digests/{id}` | Delete a digest |
| GET | `/digests/search` | Search digests by query |

#### Query Parameters for `/digests`

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Number of results (default: 20) |
| `offset` | int | Pagination offset |
| `feed_id` | int | Filter by feed |
| `source_id` | int | Filter by source |
| `tags` | string | Filter by tag names (comma-separated) |
| `from_date` | date | Filter by start date |
| `to_date` | date | Filter by end date |

#### Example: Filter Digests by Tags

```bash
# Filter by single tag
curl "http://localhost:8000/api/v1/digests/?tags=python"

# Filter by multiple tags (OR logic - matches any tag)
curl "http://localhost:8000/api/v1/digests/?tags=python,machine-learning,ai"
```

#### Example: Update Digest Tags

```bash
curl -X PUT http://localhost:8000/api/v1/digests/123 \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["python", "tutorial", "beginner"]
  }'
```

#### Example: Search Digests

```bash
curl "http://localhost:8000/api/v1/digests/search?q=machine%20learning&limit=10"
```

### Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tags/` | List all tags with digest counts |
| GET | `/tags/suggestions/` | Search tags for autocomplete |

#### Example: List All Tags

```bash
curl "http://localhost:8000/api/v1/tags/"
```

**Response:**

```json
{
  "items": [
    {"id": 1, "name": "ai", "digest_count": 42},
    {"id": 2, "name": "machine-learning", "digest_count": 28},
    {"id": 3, "name": "python", "digest_count": 15}
  ],
  "total": 3
}
```

Tags are sorted alphabetically by name.

#### Example: Tag Autocomplete

```bash
curl "http://localhost:8000/api/v1/tags/suggestions/?q=py"
```

**Response:**

```json
{
  "items": [
    {"id": 3, "name": "python", "digest_count": 15},
    {"id": 7, "name": "pytorch", "digest_count": 8}
  ]
}
```

- Returns tags matching the query prefix
- Limited to 10 suggestions
- Sorted by usage frequency (most used first)

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/summary` | Overall usage summary |
| GET | `/analytics/by-provider` | Usage breakdown by LLM provider |
| GET | `/analytics/over-time` | Usage trends over time |

### Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/providers` | List configured providers with available models |

The providers endpoint dynamically discovers available models from each configured provider:
- **Ollama**: Queries local server for installed models
- **OpenAI/Anthropic**: Returns supported model list
- **HuggingFace**: Returns available inference models

#### Example Response

```json
{
  "providers": [
    {
      "name": "ollama",
      "enabled": true,
      "status": "connected",
      "models": ["llama3.2", "mistral", "codellama"]
    },
    {
      "name": "openai",
      "enabled": true,
      "status": "configured",
      "models": ["gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
    },
    {
      "name": "anthropic",
      "enabled": true,
      "status": "configured",
      "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"]
    }
  ]
}
```

## Error Handling

All errors return a consistent JSON structure:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Rate Limiting

The API includes rate limiting middleware. Default limits:
- 100 requests per minute per IP
- Configurable in `packages/api/reconly_api/config.py`

## CORS

CORS is enabled for development. Configure allowed origins in `config.py`:

```python
cors_origins = [
    "http://localhost:4321",  # Astro dev server
    "http://localhost:8000",  # Production UI
]
```

## WebSocket (Planned)

Future support for real-time updates:
- Live feed run progress
- New digest notifications
- Provider status changes
