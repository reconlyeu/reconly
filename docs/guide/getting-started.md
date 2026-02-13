# Getting Started

This guide picks up where the setup wizard left off and walks you through daily use of Reconly.

## After the Wizard

The getting started wizard helps you create your first source and feed. Once complete, you'll land on the **Dashboard** showing your feeds and recent activity.

If you want to replay the wizard later, click the **?** icon in the sidebar footer and select **Replay Getting Started**.

## Your First Feed Run

Your feed may already have run if you set up a schedule. If not, trigger it manually:

1. Go to **Feeds** in the sidebar
2. Click the **Run now** button (play icon) on your feed
3. Watch the progress in **Feed Runs**

Once complete, your first digests will appear on the **Digests** page.

## Reading Digests

Navigate to **Digests** to see your summarized content:

- **Card view** shows rich previews with summaries
- **Table view** gives a compact list for scanning many items
- Click any digest to read the full summary and access the original source link

## Adding More Sources

Go to **Sources** and click **Add Source**:

1. Choose a source type (RSS, YouTube, Website, Email, or Agent)
2. Enter the URL or configuration
3. Save — the source is now available to add to feeds

**Tip:** Start with a few RSS feeds to get familiar with the system before exploring AI agents or email sources.

## Creating Feeds

Go to **Feeds** and click **Create Feed**:

1. **Name** your feed (e.g. "Morning Tech News")
2. **Select sources** to include
3. **Choose a schedule** — pick a preset or write a custom cron expression
4. **Pick a digest mode**:
   - *Individual* — one summary per article (best for scanning)
   - *Combined* — everything in one summary (best for newsletters)
   - *Grouped* — summaries grouped by source
5. **Select templates** for summarization style and output format
6. Save and optionally run immediately

## Using Chat

Press `Ctrl+K` anywhere to open the quick chat panel, or navigate to **Chat** in the sidebar for full-page conversations.

Chat searches across all your digests using semantic search (requires RAG to be enabled — see the [RAG setup guide](../admin/rag-setup.md)).

## Exploring the Knowledge Graph

If entity extraction is enabled, visit **Knowledge Graph** to see a visual map of people, organizations, and topics mentioned across your digests. Click nodes to see related articles.

## Keyboard Shortcuts

Press `?` (when not typing in a text field) to see all available keyboard shortcuts.

## Next Steps

- [Managing Sources](managing-sources.md) — advanced source configuration
- [Managing Feeds](managing-feeds.md) — schedules, filters, and digest modes
- [Reading Digests](reading-digests.md) — filtering, tagging, and exporting
- [Troubleshooting](troubleshooting.md) — common issues and fixes
