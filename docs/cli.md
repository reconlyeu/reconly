# CLI Reference

The Reconly CLI provides full control over sources, feeds, and content processing.

## Basic Usage

```bash
python -m reconly_core.cli.main [OPTIONS] [URL]
```

## Database Commands

### Initialize Database

```bash
# Initialize database with schema and templates
python -m reconly_core.cli.main --init

# Output:
# Initializing Reconly database...
# Database schema created
# Seeding default templates...
#    Prompt templates: 6 created
#    Report templates: 5 created
# Database initialization complete!
```

### Import Sources

```bash
# Import sources from YAML to database
python -m reconly_core.cli.main --import [--config PATH] [--create-feed] [--feed-name NAME] [--all-sources]

# Example: Import and create a feed
python -m reconly_core.cli.main --import --create-feed --feed-name "Tech News"

# Output:
# Importing sources from YAML...
# Import Summary:
#    Sources created: 2
#    Sources skipped: 0
# Created feed: 'Tech News' (ID: 1)
#    Contains 2 sources
# Import complete!
```

### List Sources & Feeds

```bash
# List sources in database
python -m reconly_core.cli.main --sources

# List feeds in database
python -m reconly_core.cli.main --feeds
```

### Run Feeds

```bash
# Run a specific feed
python -m reconly_core.cli.main --run-feed FEED_ID

# Example
python -m reconly_core.cli.main --run-feed 1
```

## Content Processing

### Process Single URL

```bash
# Process and display summary
python -m reconly_core.cli.main "https://example.com/article"

# Process and save to database
python -m reconly_core.cli.main "https://example.com/article" --save

# Process with specific language
python -m reconly_core.cli.main "https://example.com/article" --language en
```

### Batch Processing (Legacy)

```bash
# Process all sources from YAML
python -m reconly_core.cli.main --batch

# Process with specific config file
python -m reconly_core.cli.main --batch --config /path/to/sources.yaml

# Process only specific tags
python -m reconly_core.cli.main --batch --tags tech,news
```

## Search & Export

```bash
# Search digests
python -m reconly_core.cli.main --search "machine learning"

# List recent digests
python -m reconly_core.cli.main --list
python -m reconly_core.cli.main --list --limit 20

# Show statistics
python -m reconly_core.cli.main --stats

# Export digests to file
python -m reconly_core.cli.main --export digests.json
```

## Email Digests

```bash
# Send digest email to configured address
python -m reconly_core.cli.main --send-digest

# Send to specific email
python -m reconly_core.cli.main --send-digest --email user@example.com

# Limit number of items
python -m reconly_core.cli.main --send-digest --limit 10
```

## Common Options

| Option | Description | Default |
|--------|-------------|---------|
| `--language de\|en` | Summary language | `de` |
| `--provider NAME` | LLM provider (ollama, huggingface, openai, anthropic) | auto |
| `--model NAME` | Specific model to use | provider default |
| `--save` | Save to database | false |
| `--tags TAG1,TAG2` | Filter/assign tags | none |
| `--db-url URL` | Database URL | postgresql://user:pass@localhost/reconly |
| `--no-fallback` | Disable provider fallback | false |
| `--show-cost` | Show cost estimates | false |
| `--config PATH` | Path to config file | config/sources.yaml |

## Environment Variables

```bash
# Database (PostgreSQL required)
DATABASE_URL=postgresql://user:pass@localhost/reconly

# Default provider
DEFAULT_PROVIDER=ollama

# Provider API keys
OLLAMA_HOST=http://localhost:11434
HUGGINGFACE_API_KEY=hf_xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Email (for digests)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=xxx
DIGEST_EMAIL=recipient@example.com
```

## Examples

### Daily Workflow

```bash
# Morning: Run your tech feed
python -m reconly_core.cli.main --run-feed 1

# Check what was processed
python -m reconly_core.cli.main --list --limit 5

# Send digest email
python -m reconly_core.cli.main --send-digest
```

### Adding New Sources

```bash
# Edit your sources.yaml, then import
python -m reconly_core.cli.main --import

# Or add directly via the Web UI or API
```

### Quick Article Summary

```bash
# Summarize an article without saving
python -m reconly_core.cli.main "https://news.ycombinator.com/item?id=12345" --language en

# Summarize and save
python -m reconly_core.cli.main "https://news.ycombinator.com/item?id=12345" --save --tags hn,tech
```
