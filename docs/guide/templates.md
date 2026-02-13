# Templates

Templates control how Reconly processes and formats content. There are two types: **prompt templates** that instruct the LLM, and **report templates** that format the output.

## Prompt Templates

Prompt templates are the instructions sent to the LLM when summarizing content. They control:

- **Language** — which language the summary is written in
- **Length** — how detailed the summary should be
- **Style** — formal analysis, quick brief, bullet points, etc.
- **Focus** — what aspects to emphasize (key findings, action items, opinions)

### Built-in Prompt Templates

Reconly ships with several system templates:

| Template | Language | Length | Best For |
|----------|----------|--------|----------|
| Standard Summary | EN | ~150 words | Daily digests |
| Quick Brief | EN | ~50 words | Fast scanning |
| Deep Analysis | EN | ~300 words | Research |

System templates cannot be edited, but you can create your own based on them.

### Creating Prompt Templates

1. Go to **Templates** in the sidebar
2. Click **Create Template** and select **Prompt Template**
3. Write your prompt — this is the instruction the LLM receives along with the article content
4. Save and assign it to a feed

**Example prompt:**
```
Summarize the following article in 3-4 bullet points.
Focus on practical implications and action items.
Write in English. Be concise.
```

## Report Templates

Report templates control the output format of digests — how summaries are structured and laid out.

### Built-in Report Templates

| Template | Format | Best For |
|----------|--------|----------|
| Daily Digest | Markdown | Notes, documentation |
| Daily Digest | HTML | Email newsletters |
| Simple List | Markdown | Quick reference |
| Obsidian Note | Markdown | PKM with frontmatter |
| JSON Export | JSON | API integrations |

### Creating Report Templates

1. Go to **Templates** in the sidebar
2. Click **Create Template** and select **Report Template**
3. Define the output structure using template variables
4. Save and assign it to a feed

## Template Origins

Templates have three possible origins:

- **Built-in** — shipped with Reconly, cannot be edited
- **User** — created by you, fully editable
- **Imported** — loaded from a feed bundle, editable after import

## Using Templates with Feeds

When creating or editing a feed, you select both a prompt template and a report template:

- **Prompt Template** controls summarization (what the LLM writes)
- **Report Template** controls formatting (how the output looks)

Different feeds can use different templates. For example:
- A "Morning Brief" feed might use a Quick Brief prompt + Simple List report
- A "Weekly Research" feed might use a Deep Analysis prompt + Obsidian Note report

## Tips

- **Start with built-in templates** to understand what works before creating custom ones
- **Be explicit in prompts** — tell the LLM exactly what you want (language, length, format, focus)
- **Test templates** by running a feed manually after changing the template
- **Use report templates** that match your export target (Markdown for PKM, HTML for email)
