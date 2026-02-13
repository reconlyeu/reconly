# Managing Feeds

Feeds are the heart of Reconly — they combine sources, schedules, and templates into an automated content pipeline.

## Creating a Feed

1. Go to **Feeds** in the sidebar
2. Click **Create Feed**
3. Fill in the sections:

### Basic Information

- **Name** — a descriptive label (e.g. "Morning Tech News", "Weekly AI Research")
- **Description** — optional notes for your reference

### Select Sources

Choose which sources to include. You can select multiple sources of any type. Disabled sources are shown with a warning — they'll be skipped during feed runs.

### Digest Mode

Controls how content is combined before summarization:

| Mode | Behavior | Best For |
|------|----------|----------|
| **Individual** | One digest entry per article | Scanning headlines, detailed per-article summaries |
| **Per Source** | One digest per source (articles consolidated) | Source-level overviews |
| **Single Briefing** | All articles merged into one unified digest | Daily newsletter, executive summary |

### Templates

- **Prompt Template** — controls how the LLM summarizes content (language, length, style, focus areas). System templates are provided; you can also create your own.
- **Report Template** — controls output formatting. Choose Markdown, HTML, or JSON depending on your needs.

### Schedule

Set when the feed runs automatically:

| Preset | Cron | Description |
|--------|------|-------------|
| Every hour | `0 * * * *` | Top of every hour |
| Daily at midnight | `0 0 * * *` | Once per day |
| Twice daily | `0 8,20 * * *` | 8 AM and 8 PM |
| Weekly on Sunday | `0 0 * * 0` | Once per week |
| Custom cron | (your expression) | 5-field cron: `minute hour day month weekday` |
| No schedule | — | Manual runs only |

**Examples:**
- `0 9 * * 1-5` — weekdays at 9 AM
- `30 7 * * *` — daily at 7:30 AM
- `0 */6 * * *` — every 6 hours

### Output Configuration

- **Save to Database** — always on; digests appear in the UI
- **Send via Email** — deliver digests as email newsletters (requires SMTP configuration)
- **Webhook** — POST digest data to a URL for automation
- **Auto-Export** — automatically export to configured exporters (Obsidian, Logseq, etc.)

## Running a Feed

### Manual Run

Click the **Run now** (play icon) button on any feed card. The run appears in **Feed Runs** with real-time status.

### Scheduled Runs

Feeds with a schedule run automatically. The scheduler:
- Uses your configured timezone (`SCHEDULER_TIMEZONE` environment variable)
- Shows the next run time on the feed card
- Syncs immediately when you create or update a feed

### Run All

From the **Dashboard**, use the **Run Feeds** quick action to trigger all enabled feeds at once.

## Feed Bundles

Feeds can be exported and imported as bundles — portable JSON packages containing the feed configuration, source definitions, and templates.

- **Export Bundle** — share your feed setup with others
- **Import Bundle** — load a pre-configured feed from a bundle file

Bundles make it easy to share curated feed setups for common topics.

## Editing and Deleting

- Click **Edit** on any feed to modify sources, schedule, templates, or outputs
- Click **Delete** to remove a feed (digests from past runs are preserved)
- Toggle the schedule on/off to pause automatic runs without deleting

## Tips

- **Start simple** — one source, individual digest mode, no schedule. Run manually to see results before automating.
- **Group related sources** — a "Security News" feed with 5 security RSS sources is more useful than 5 separate feeds
- **Use Single Briefing mode** for daily newsletter-style digests that cross-reference multiple sources
- **Stagger schedules** if you have many feeds to avoid overloading your LLM provider
