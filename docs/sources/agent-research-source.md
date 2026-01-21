# AI Agent Research Source

> **Status:** Available in v1.5+
> **Source Type:** `agent`
> **Requires:** LLM provider configured (Ollama, OpenAI, or Anthropic)

This guide explains how to use Reconly's AI Agent source for autonomous web research.

---

## Table of Contents

1. [Overview](#overview)
2. [Research Strategies](#research-strategies)
3. [Basic Setup](#basic-setup)
4. [GPT Researcher Setup](#gpt-researcher-setup)
5. [Configuration Options](#configuration-options)
6. [Cost Expectations](#cost-expectations)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The Agent source type uses an LLM with web tools to autonomously research topics. Instead of fetching content from a URL, you provide a research prompt and the agent:

1. **Searches the web** for relevant information
2. **Fetches and reads** promising articles
3. **Synthesizes findings** into a structured research report
4. **Cites sources** for verification

### Use Cases

- Competitive intelligence monitoring
- Industry trend analysis
- Technology research
- News aggregation on specific topics
- Due diligence research

---

## Research Strategies

Reconly supports three research strategies with different depth/speed tradeoffs:

| Strategy | Duration | Sources | Best For |
|----------|----------|---------|----------|
| **Simple** | ~30 seconds | 2-5 | Quick lookups, time-sensitive queries |
| **Comprehensive** | ~3 minutes | 20+ | Deep research, competitive intel |
| **Deep** | ~5 minutes | 50+ | Exhaustive analysis, due diligence |

### Simple Strategy (Default)

Uses a basic ReAct loop with `web_search` and `web_fetch` tools. Fast and efficient for straightforward queries.

- No additional dependencies
- Works with any LLM provider
- Lower cost per research

### Comprehensive & Deep Strategies

Uses [GPT Researcher](https://github.com/assafelovic/gpt-researcher), a battle-tested open-source framework that:

- Employs multi-agent architecture (planner → parallel executors → publisher)
- Aggregates 20-50+ sources per query
- Produces 2000+ word reports with proper citations
- Includes source curation to filter low-quality results

**Requires:** `gpt-researcher` package (see [GPT Researcher Setup](#gpt-researcher-setup))

---

## Basic Setup

### 1. Configure a Search Provider

Agent sources require a search provider. Configure one in Settings → Agent:

| Provider | Setup | Notes |
|----------|-------|-------|
| **DuckDuckGo** | No setup needed | Free, no API key, rate limited |
| **SearXNG** | Set `SEARXNG_URL` | Self-hosted, unlimited, recommended |
| **Tavily** | Set `TAVILY_API_KEY` | Best results, 1000 free searches/month |

### 2. Create an Agent Source

1. Go to **Sources** → **Add Source**
2. Select **AI Agent** as the source type
3. Enter your research topic/prompt
4. (Optional) Adjust max iterations
5. Save the source

### Example Prompts

```
Research the latest developments in AI language models, focusing on
open-source alternatives to GPT-4 released in the last 3 months.
```

```
Analyze the competitive landscape of cloud-native database solutions,
comparing pricing, features, and market positioning.
```

---

## GPT Researcher Setup

To use **Comprehensive** or **Deep** strategies, install the GPT Researcher package:

```bash
# From the reconly directory
pip install -e ".[research]"

# Or install directly
pip install gpt-researcher>=0.9.0
```

### Verify Installation

After installation, the UI will show Comprehensive and Deep options in the strategy selector. You can also check via API:

```bash
curl http://localhost:8000/api/v1/agent-runs/capabilities
```

Response when installed:
```json
{
  "strategies": {
    "simple": {"available": true, "description": "Quick research (~30s)"},
    "comprehensive": {"available": true, "description": "Comprehensive research (~3min)"},
    "deep": {"available": true, "description": "Deep research (~5min)"}
  },
  "gpt_researcher_installed": true
}
```

### LLM Provider Mapping

GPT Researcher automatically uses your configured LLM provider:

| Reconly Provider | GPT Researcher Config |
|------------------|----------------------|
| OpenAI | Uses `OPENAI_API_KEY`, model as `SMART_LLM` |
| Anthropic | Uses `ANTHROPIC_API_KEY`, model as `SMART_LLM` |
| Ollama | Uses `OLLAMA_BASE_URL`, model as `SMART_LLM` |

---

## Configuration Options

### Strategy-Specific Options

When using Comprehensive or Deep strategies:

| Option | Description | Default |
|--------|-------------|---------|
| **Report Format** | Citation style (APA, MLA, CMS, Harvard, IEEE) | APA |
| **Max Subtopics** | Number of subtopics to explore (1-10) | 3 |

### Per-Source Overrides

Each agent source can override the global search provider:

```json
{
  "research_strategy": "comprehensive",
  "search_provider": "tavily",
  "report_format": "IEEE",
  "max_subtopics": 5
}
```

---

## Cost Expectations

Costs vary by strategy and LLM provider. Estimates using GPT-4o:

| Strategy | Estimated Cost | Token Usage |
|----------|---------------|-------------|
| Simple | $0.05 - $0.20 | ~10k tokens |
| Comprehensive | $0.30 - $0.80 | ~50k tokens |
| Deep | $0.50 - $1.50 | ~100k tokens |

**Cost-Saving Tips:**

1. Use **Ollama** with local models for unlimited free research
2. Start with **Simple** strategy and upgrade only when needed
3. Use **SearXNG** instead of Tavily to avoid API costs
4. Set lower `max_subtopics` for comprehensive strategies

---

## Troubleshooting

### "GPT Researcher not installed"

Install the research dependencies:
```bash
pip install -e ".[research]"
```

### "Search provider not configured"

Set the appropriate environment variable:
```bash
# For Tavily
export TAVILY_API_KEY=tvly-xxxxx

# For SearXNG
export SEARXNG_URL=http://localhost:8080
```

### Research times out

Increase the timeout or reduce scope:
- Use fewer `max_subtopics`
- Use `comprehensive` instead of `deep`
- Check your LLM provider latency

### Empty or poor results

1. Make your prompt more specific
2. Try a different search provider
3. Use a more capable LLM model
4. Check that web search is returning results (look at agent run logs)

### "Rate limited by search provider"

- DuckDuckGo has aggressive rate limits - switch to SearXNG or Tavily
- Wait a few minutes and try again
- Consider self-hosting SearXNG for unlimited searches

### Ollama models produce poor results

GPT Researcher works best with capable models. For Ollama:
- Use `llama3.1:70b` or larger for best results
- `llama3.1:8b` works but may miss nuances
- Ensure adequate RAM/VRAM for the model

---

## See Also

- [Search Framework Configuration](../configuration.md#agent-settings)
- [LLM Provider Setup](../setup.md#llm-providers)
- [GPT Researcher Documentation](https://docs.gptr.dev/)
