# Managing Sources

Sources define what content Reconly monitors. Each source points to a content endpoint and can be shared across multiple feeds.

## Source Types

| Type | Description | Example |
|------|-------------|---------|
| **RSS** | Standard RSS/Atom feeds | `https://example.com/feed.xml` |
| **YouTube** | Channel or video transcripts | `https://youtube.com/@channel` |
| **Website** | Scraped web pages | `https://example.com/blog` |
| **Blog** | Blog-specific scraping | `https://example.com/blog` |
| **Email (IMAP)** | Email inbox messages | Gmail, Outlook, or custom IMAP |
| **AI Agent** | Autonomous research on a topic | "Latest developments in AI safety" |

## Adding a Source

1. Go to **Sources** in the sidebar
2. Click **Add Source**
3. Select a source type
4. Fill in the required fields:
   - **Name** — a label for your reference
   - **URL** — the content endpoint (not needed for Agent sources)
   - **Enabled** — toggle to activate/deactivate
5. Click **Save**

### RSS Sources

Enter the feed URL directly. Reconly auto-detects RSS 2.0, Atom, and JSON Feed formats.

### YouTube Sources

Supports two formats:
- **Video URL** — `youtube.com/watch?v=...` to fetch a single video transcript
- **Channel URL** — `youtube.com/@channel` or `youtube.com/channel/UC...` to fetch transcripts from recent videos

Enable **Fetch Transcript** to include video transcripts in the content sent to the LLM.

### Website Sources

Enter the page URL. Reconly fetches and extracts the main content. Enable **Fetch Full Content** if the source provides only excerpts.

### Email (IMAP) Sources

Connect to an email inbox to monitor newsletters and automated reports:

1. Choose a **provider** (Gmail, Outlook, or generic IMAP)
2. For Gmail/Outlook, follow the OAuth flow to authorize securely
3. For generic IMAP, enter server details (host, port, SSL, credentials)
4. Optionally configure:
   - **Folders** — comma-separated list (default: INBOX)
   - **Sender Filter** — only process emails from matching senders
   - **Subject Filter** — only process emails with matching subjects

### AI Agent Sources

Agent sources use AI to autonomously research topics:

1. Enter a **Research Topic** — be specific for better results
2. Choose a **Research Strategy**:
   - **Simple** — quick lookup using search and summarization
   - **Comprehensive** — multi-step research with subtopic exploration
   - **Deep** — exhaustive analysis with a detailed research plan
3. Optionally configure:
   - **Search Provider** — DuckDuckGo, SearXNG, or Tavily
   - **Max Iterations** — how many search cycles to perform
   - **Max Subtopics** — breadth of exploration (1-10)

> Comprehensive and Deep strategies require the `gpt-researcher` package. See the [feature setup guide](../admin/feature-setup-guide.md) for installation.

## Filters

Sources support keyword-based content filtering:

- **Include Keywords** — articles must match at least one keyword to be processed
- **Exclude Keywords** — articles matching any keyword are skipped
- **Search In** — apply filters to title only, content only, or both
- **Regex** — enable for regular expression matching
- **Max Items per Run** — limit the number of items fetched (newest first)

Filters are applied before content reaches the LLM, saving processing time and tokens.

## Circuit Breakers

If a source fails repeatedly (network errors, invalid feed, etc.), its circuit breaker trips and the source is temporarily disabled. This prevents wasting resources on broken sources.

When a circuit breaker is tripped:
- The source shows a warning indicator
- It is skipped during feed runs
- You can **reset** it after fixing the underlying issue by clicking the reset button on the source card

## Editing and Deleting

- Click the **edit** (pencil) icon on any source card to modify it
- Click the **delete** (trash) icon to remove it
- Sources used by feeds show a "Used by N feeds" indicator — deleting a source removes it from all feeds

## Tips

- **Name sources descriptively** — you'll select them by name when creating feeds
- **Start with RSS** — it's the simplest source type and works with most news sites
- **Use filters on high-volume sources** to reduce noise before summarization
- **Disable sources temporarily** instead of deleting them if you want to pause monitoring
