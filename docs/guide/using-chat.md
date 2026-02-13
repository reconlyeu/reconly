# Using Chat

Chat lets you ask questions across your entire digest archive using natural language. It uses RAG (Retrieval-Augmented Generation) to find relevant content and generate answers with citations.

## Requirements

Chat requires RAG to be enabled. If you haven't set it up yet, see the [RAG setup guide](../admin/rag-setup.md).

Once RAG is enabled and you've run your feeds, new digest content is automatically embedded for semantic search.

## Quick Panel

Press `Ctrl+K` from anywhere in Reconly to open the quick chat panel. This is a compact overlay for fast questions.

Type your question and press Enter. The LLM searches your embedded digests, finds relevant passages, and generates an answer with source citations.

Press `Escape` to close the panel.

## Full-Page Chat

Navigate to **Chat** in the sidebar for a full-page conversational interface. This is better for:

- Longer conversations with follow-up questions
- Reviewing multiple cited sources
- Complex research queries

## Writing Good Queries

Semantic search works best with **natural language questions** rather than keywords:

| Good | Less Effective |
|------|----------------|
| "What are the latest trends in AI safety research?" | "AI safety" |
| "Which companies announced new LLM products this week?" | "LLM products" |
| "How does the new EU regulation affect data privacy?" | "EU regulation" |

**Tips for better results:**
- Be specific about what you're looking for
- Mention time frames if relevant ("this week", "in January")
- Ask follow-up questions to drill deeper into a topic
- Try rephrasing if the first answer isn't what you expected

## Citations

Chat responses include citations linking to the digest entries used to generate the answer. Click a citation to view the full digest entry.

## Limitations

- **Only embedded content is searchable** — digests created before RAG was enabled are not included. Re-run feeds to embed existing sources.
- **Context window limits** — very broad queries may not include all relevant content. Be specific to get better results.
- **LLM quality** — answer quality depends on your configured LLM. Larger models produce better chat responses.
