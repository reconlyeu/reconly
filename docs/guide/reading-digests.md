# Reading Digests

Digests are the primary output of Reconly — summarized, structured versions of the content your feeds collect.

## Browsing Digests

Navigate to **Digests** in the sidebar. You can switch between two views:

- **Card view** — rich previews with summaries, tags, and source info
- **Table view** — compact rows for scanning many items quickly

Use the view toggle in the top right to switch.

## Filtering

Narrow down digests using the filter options:

- **Feed** — show digests from a specific feed
- **Source** — show digests from a specific source
- **Tags** — filter by tag
- **Date range** — filter by publish date
- **Search** — text search across titles and summaries

Filters combine with AND logic — selecting a feed and a tag shows only digests matching both.

## Reading a Digest

Click any digest card or row to expand it. Each digest shows:

- **Title** — original or LLM-generated
- **Summary** — the AI-generated summary based on your prompt template
- **Original link** — click to visit the source content
- **Source and feed** — which source and feed produced this digest
- **Date** — when the content was originally published
- **Tags** — auto-generated and manually added labels

## Tagging

Tags help you organize and find digests later:

- Tags may be **auto-generated** by the LLM during summarization
- You can **add tags manually** using the tag input on any digest
- Tags are searchable and appear as filter options

## Exporting

### Individual Export

Click the export button on any digest to save it in your configured format (Markdown, HTML, etc.).

### Bulk Actions

Select multiple digests using the checkboxes and use bulk actions to:

- **Export selected** — save multiple digests at once
- **Tag selected** — add a tag to all selected items
- **Delete selected** — remove digest entries

### Auto-Export

Configure auto-export on your feeds to automatically send digests to your PKM (Obsidian, Logseq) or other destinations after each feed run. See [Managing Feeds](managing-feeds.md) for details.

## Pagination

Large digest collections are paginated. Use the page controls at the bottom to navigate. The current page size and total count are shown.

## Tips

- **Use table view** when scanning many digests quickly — card view is better for reading summaries in detail
- **Star important digests** to find them later
- **Combine filters** to create focused views (e.g. "AI" tag + last 7 days)
- **Check Feed Runs** if expected digests are missing — the run history shows whether content was fetched successfully
