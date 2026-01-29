# Reconly Feed Bundle Specification

> **Version:** 1.0
> **Status:** Stable

A Feed Bundle is a portable JSON package containing everything needed to recreate a complete feed configuration in Reconly.

---

## Quick Example

```json
{
  "schema_version": "1.0",
  "bundle": {
    "id": "ai-news-daily",
    "name": "AI News Daily",
    "version": "1.0.0",
    "description": "Daily digest of AI and machine learning news",
    "category": "tech",
    "tags": ["ai", "machine-learning", "news"],
    "language": "en",
    "sources": [
      {
        "name": "Hacker News",
        "type": "rss",
        "url": "https://news.ycombinator.com/rss",
        "include_keywords": ["AI", "GPT", "LLM", "machine learning"],
        "filter_mode": "both"
      },
      {
        "name": "MIT Technology Review AI",
        "type": "rss",
        "url": "https://www.technologyreview.com/feed/"
      }
    ],
    "prompt_template": {
      "name": "AI News Summary",
      "system_prompt": "You are an AI research analyst. Summarize technical content clearly and highlight practical implications.",
      "user_prompt_template": "Summarize this article in {target_length} words:\n\nTitle: {title}\n\nContent:\n{content}",
      "language": "en",
      "target_length": 150
    },
    "schedule": {
      "cron": "0 8 * * *",
      "description": "Daily at 8:00 AM"
    },
    "digest_mode": "individual"
  }
}
```

---

## Schema Structure

### Top Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Must be `"1.0"` |
| `bundle` | object | Yes | The feed bundle definition |
| `compatibility` | object | No | Version requirements |
| `metadata` | object | No | License and links |

---

## Bundle Object

### Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | string | `^[a-z0-9-]+$` (kebab-case) | Unique bundle identifier, auto-generated from name |
| `name` | string | 1-255 chars | Human-readable bundle name |
| `version` | string | Semver `X.Y.Z` | Bundle version (e.g., `"1.0.0"`) |
| `sources` | array | Min 1 item | List of content sources |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | - | Bundle description (max 2000 chars) |
| `author` | object | - | Author information |
| `category` | string | - | One of: `news`, `finance`, `tech`, `science`, `entertainment`, `sports`, `business`, `other` |
| `tags` | array | `[]` | Discovery tags (max 10) |
| `language` | string | - | Primary language code (`en`, `de`, etc.) |
| `prompt_template` | object | - | Custom summarization prompt |
| `report_template` | object | - | Custom output formatting |
| `schedule` | object | - | Cron schedule configuration |
| `output_config` | object | - | Output destinations |
| `digest_mode` | string | `"individual"` | One of: `individual`, `per_source`, `all_sources` |

---

## Source Object

Each source defines a content origin to fetch and summarize.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Source display name (1-255 chars) |
| `type` | string | One of: `rss`, `youtube`, `website`, `blog`, `podcast`, `imap`, `agent` |
| `url` | string | Valid URL for the source (or research prompt for `agent` type) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config` | object | - | Type-specific settings (e.g., `max_items`) |
| `default_language` | string | - | Language code for this source |
| `include_keywords` | array | - | Items must match at least one keyword |
| `exclude_keywords` | array | - | Items matching any keyword are excluded |
| `filter_mode` | string | `"both"` | Where to search: `title_only`, `content`, `both` |
| `use_regex` | boolean | `false` | Interpret keywords as regex patterns |

### Source Types

#### RSS (`type: "rss"`)

Standard RSS/Atom feed.

```json
{
  "name": "TechCrunch",
  "type": "rss",
  "url": "https://techcrunch.com/feed/",
  "config": {
    "max_items": 10,
    "fetch_full_content": true
  }
}
```

#### YouTube (`type: "youtube"`)

YouTube channel or single video. Transcripts are extracted automatically.

```json
{
  "name": "Fireship",
  "type": "youtube",
  "url": "https://www.youtube.com/@fireship"
}
```

**Supported URL formats:**
- Channel by handle: `https://youtube.com/@fireship`
- Channel by ID: `https://youtube.com/channel/UCxxxxxx`
- Single video: `https://youtube.com/watch?v=VIDEO_ID`

#### Website (`type: "website"`)

Single webpage for periodic monitoring.

```json
{
  "name": "Company Blog",
  "type": "website",
  "url": "https://example.com/blog"
}
```

#### Blog (`type: "blog"`)

Blog with pagination support.

```json
{
  "name": "Personal Blog",
  "type": "blog",
  "url": "https://blog.example.com"
}
```

#### IMAP (`type: "imap"`)

Email inbox monitoring via IMAP. Supports Gmail, Outlook, or generic IMAP servers.

```json
{
  "name": "Newsletter Inbox",
  "type": "imap",
  "url": "imap://imap.gmail.com:993",
  "config": {
    "folders": ["INBOX"],
    "from_filter": "newsletter@example.com"
  }
}
```

**Note:** Requires a Connection to be configured separately with credentials.

#### Agent (`type: "agent"`)

AI-powered research agent that autonomously searches the web and synthesizes findings.

```json
{
  "name": "AI Research Agent",
  "type": "agent",
  "url": "Research the latest developments in enterprise AI adoption",
  "config": {
    "research_strategy": "comprehensive",
    "max_iterations": 8,
    "report_format": "APA"
  }
}
```

**Configuration options:**
- `research_strategy`: `simple` (fast, 2 min), `comprehensive` (thorough, 5 min), or `deep` (most thorough, 10 min)
- `max_iterations`: Maximum research iterations (default: 5)
- `report_format`: Citation format for comprehensive/deep strategies (APA, MLA, CMS, Harvard, IEEE)
- `max_subtopics`: Maximum subtopics for deep research (1-10)

**Note:** The `url` field is repurposed as the research prompt/topic for agent sources.

---

## Prompt Template Object

Defines how content is summarized by the LLM.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Template name (1-255 chars) |
| `system_prompt` | string | Yes | - | System instructions for the LLM |
| `user_prompt_template` | string | Yes | - | User prompt with variables |
| `description` | string | No | - | Template description |
| `language` | string | No | `"en"` | Output language |
| `target_length` | integer | No | `150` | Target word count (10-2000) |

### Template Variables (Jinja2)

Prompt templates use **Jinja2** syntax (same as report templates). Use `{{ variable }}` for values and `{% for %}` for loops.

**For individual article summarization (`individual` mode):**

| Variable | Description |
|----------|-------------|
| `{{ title }}` | Content title |
| `{{ content }}` | Full content text |
| `{{ source_type }}` | Type of source (rss, youtube, etc.) |
| `{{ target_length }}` | Target word count |

**For consolidated digests (`all_sources` or `per_source` mode):**

| Variable | Description |
|----------|-------------|
| `{{ item_count }}` | Number of articles |
| `{{ source_count }}` | Number of unique sources |
| `{{ articles }}` | Pre-formatted article text |
| `{{ items }}` | List of article dicts (for iteration) |
| `{{ target_length }}` | Target word count |

Each item in `items` has: `title`, `content`, `source_name`, `url`, `published_at`

### Example Prompt Templates

**Concise Summary:**
```json
{
  "name": "Quick Brief",
  "system_prompt": "You are a concise news summarizer. Focus on key facts only.",
  "user_prompt_template": "Summarize in {{ target_length }} words:\n\n{{ title }}\n\n{{ content }}",
  "target_length": 50
}
```

**Technical Analysis:**
```json
{
  "name": "Technical Deep Dive",
  "system_prompt": "You are a senior software engineer. Analyze technical content, highlight architecture decisions, trade-offs, and practical implications.",
  "user_prompt_template": "Provide a technical analysis of this article:\n\nTitle: {{ title }}\n\nContent:\n{{ content }}\n\nInclude: key technical concepts, architecture decisions, and practical takeaways.",
  "target_length": 300
}
```

**Executive Brief:**
```json
{
  "name": "Executive Summary",
  "system_prompt": "You are a business analyst. Summarize for executives who need quick, actionable insights.",
  "user_prompt_template": "Create an executive brief:\n\n{{ title }}\n\n{{ content }}\n\nFormat: Key point, business impact, recommended action.",
  "target_length": 100
}
```

---

## Report Template Object

Defines output formatting using Jinja2 templates.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Template name (1-255 chars) |
| `format` | string | Yes | One of: `markdown`, `html`, `text` |
| `template_content` | string | Yes | Jinja2 template |
| `description` | string | No | Template description |

### Template Variables

| Variable | Description |
|----------|-------------|
| `{{ feed }}` | Feed object with name, description |
| `{{ digests }}` | List of digest objects |
| `{{ run_info }}` | FeedRun object with stats |
| `{{ generated_at }}` | Generation timestamp |

### Example Report Templates

**Markdown Daily Digest:**
```json
{
  "name": "Daily Digest",
  "format": "markdown",
  "template_content": "# {{ feed.name }} - {{ generated_at.strftime('%Y-%m-%d') }}\n\n{% for digest in digests %}\n## {{ digest.title }}\n\n{{ digest.summary }}\n\n[Read more]({{ digest.url }})\n\n---\n\n{% endfor %}"
}
```

**Obsidian Note:**
```json
{
  "name": "Obsidian Note",
  "format": "markdown",
  "template_content": "---\ntags: [digest, {{ feed.name | lower | replace(' ', '-') }}]\ndate: {{ generated_at.strftime('%Y-%m-%d') }}\n---\n\n# {{ feed.name }}\n\n{% for digest in digests %}\n## {{ digest.title }}\n\n{{ digest.summary }}\n\n{% endfor %}"
}
```

---

## Schedule Object

Cron-based scheduling configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cron` | string | No | Cron expression (5 fields) |
| `description` | string | No | Human-readable description |

### Cron Format

`minute hour day month weekday`

| Expression | Description |
|------------|-------------|
| `0 8 * * *` | Daily at 8:00 AM |
| `0 8 * * 1-5` | Weekdays at 8:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 9 * * 1` | Mondays at 9:00 AM |
| `30 7 * * *` | Daily at 7:30 AM |

---

## Output Config Object

Configure where digests are delivered.

```json
{
  "output_config": {
    "db": true,
    "email": {
      "enabled": true,
      "recipients": ["user@example.com"]
    },
    "webhook_url": "https://example.com/webhook",
    "exports": {
      "obsidian": { "enabled": true, "path": "/vault/digests" },
      "json": { "enabled": true }
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `db` | boolean | Save to database (default: true) |
| `email` | object | Email delivery configuration |
| `webhook_url` | string | Webhook URL for notifications |
| `exports` | object | Export destinations |

---

## Digest Mode

Controls how content is consolidated.

| Mode | Description | Use Case |
|------|-------------|----------|
| `individual` | One digest per item | Detailed per-article summaries |
| `per_source` | One digest per source | Source-level briefings |
| `all_sources` | One digest per feed run | Cross-source synthesis ("Daily Briefing") |

---

## Compatibility Object

Specify version requirements.

```json
{
  "compatibility": {
    "min_reconly_version": "1.0.0",
    "required_features": ["ollama", "email"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `min_reconly_version` | string | Minimum Reconly version (semver) |
| `required_features` | array | Required features (e.g., `ollama`, `email`, `webhook`) |

---

## Metadata Object

Additional bundle metadata.

```json
{
  "metadata": {
    "license": "MIT",
    "homepage": "https://example.com/my-bundle",
    "repository": "https://github.com/user/my-bundle"
  }
}
```

---

## Author Object

Bundle author information.

```json
{
  "author": {
    "name": "John Doe",
    "github": "johndoe",
    "email": "john@example.com"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Author name |
| `github` | string | No | GitHub username |
| `email` | string | No | Contact email |

---

## Content Filtering

Filter content before summarization using keywords.

```json
{
  "name": "Filtered Tech News",
  "type": "rss",
  "url": "https://news.ycombinator.com/rss",
  "include_keywords": ["AI", "GPT", "LLM", "machine learning", "neural"],
  "exclude_keywords": ["crypto", "blockchain", "NFT"],
  "filter_mode": "both",
  "use_regex": false
}
```

### Filter Behavior

1. **Include filter** (if set): Item must match **at least one** keyword
2. **Exclude filter** (if set): Item must **not match any** keyword
3. Both filters can be combined (include is applied first)
4. Keywords are case-insensitive
5. With `use_regex: true`, keywords are interpreted as regex patterns

### Filter Mode

| Mode | Description |
|------|-------------|
| `title_only` | Search only in title |
| `content` | Search only in content body |
| `both` | Search in title and content (default) |

---

## Validation

Bundles are validated on import. Common validation errors:

| Error | Cause |
|-------|-------|
| `Invalid schema_version` | Must be exactly `"1.0"` |
| `Missing required field: sources` | At least one source required |
| `Invalid source type` | Must be: rss, youtube, website, blog, podcast |
| `Invalid URL format` | URL must be valid |
| `Invalid cron expression` | Must be valid 5-field cron |
| `Invalid version format` | Must be semver (X.Y.Z) |

---

## Complete Example

```json
{
  "schema_version": "1.0",
  "bundle": {
    "id": "sap-analyst-brief",
    "name": "SAP Analyst Brief",
    "version": "1.0.0",
    "description": "Daily intelligence on SAP ecosystem, competitors, and enterprise tech trends",
    "author": {
      "name": "Enterprise Tech Team",
      "github": "enterprise-team"
    },
    "category": "business",
    "tags": ["sap", "enterprise", "erp", "business-intelligence"],
    "language": "en",
    "sources": [
      {
        "name": "SAP News",
        "type": "rss",
        "url": "https://news.sap.com/feed/",
        "config": { "max_items": 10 }
      },
      {
        "name": "Diginomica",
        "type": "rss",
        "url": "https://diginomica.com/feed",
        "include_keywords": ["SAP", "S/4HANA", "ERP"],
        "filter_mode": "both"
      },
      {
        "name": "SAP Community",
        "type": "rss",
        "url": "https://blogs.sap.com/feed/"
      }
    ],
    "prompt_template": {
      "name": "SAP Analyst Summary",
      "system_prompt": "You are an enterprise technology analyst specializing in SAP and ERP systems. Summarize content with focus on: strategic implications, competitive positioning, and actionable insights for IT leaders.",
      "user_prompt_template": "Analyze this article for enterprise IT decision-makers:\n\nTitle: {title}\n\nContent:\n{content}\n\nProvide:\n1. Key announcement/finding\n2. Strategic implication\n3. Action item (if applicable)",
      "language": "en",
      "target_length": 150
    },
    "report_template": {
      "name": "Executive Brief",
      "format": "markdown",
      "template_content": "# SAP Intelligence Brief - {{ generated_at.strftime('%B %d, %Y') }}\n\n**Sources analyzed:** {{ digests | length }}\n\n---\n\n{% for digest in digests %}\n## {{ digest.title }}\n\n{{ digest.summary }}\n\n*Source: {{ digest.source_name }}* | [Read full article]({{ digest.url }})\n\n---\n\n{% endfor %}\n\n*Generated by Reconly*"
    },
    "schedule": {
      "cron": "0 7 * * 1-5",
      "description": "Weekdays at 7:00 AM"
    },
    "output_config": {
      "db": true,
      "email": {
        "enabled": true,
        "recipients": ["team@example.com"]
      }
    },
    "digest_mode": "individual"
  },
  "compatibility": {
    "min_reconly_version": "1.0.0"
  },
  "metadata": {
    "license": "MIT",
    "repository": "https://github.com/example/sap-analyst-bundle"
  }
}
```

---

## See Also

- [BUNDLE_CREATOR_PROMPT.md](BUNDLE_CREATOR_PROMPT.md) - AI-assisted bundle creation guide
- [API Documentation](../api.md#feed-bundles) - Bundle API endpoints
