# AI Agent Research Source

> **Status:** Available in v1.5+
> **Source Type:** `agent`
> **Requires:** GPT Researcher package, search provider, LLM provider

This guide explains how to use Reconly's AI Agent source for autonomous web research.

---

## Table of Contents

1. [Overview](#overview)
2. [Research Strategies](#research-strategies)
3. [Setup](#setup)
4. [Configuration Options](#configuration-options)
5. [Cost Expectations](#cost-expectations)
6. [Troubleshooting](#troubleshooting)

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

Reconly uses [GPT Researcher](https://github.com/assafelovic/gpt-researcher) to power autonomous research. Three strategies with different depth/speed tradeoffs:

| Strategy | Duration | Sources | Best For |
|----------|----------|---------|----------|
| **Simple** | ~30 seconds | 2-5 | Quick lookups, time-sensitive queries |
| **Comprehensive** | ~3 minutes | 20+ | Deep research, competitive intel |
| **Deep** | ~5 minutes | 50+ | Exhaustive analysis, due diligence |

GPT Researcher is a battle-tested open-source framework that:

- Employs multi-agent architecture (planner → parallel executors → publisher)
- Aggregates 20-50+ sources per query
- Produces 2000+ word reports with proper citations
- Includes source curation to filter low-quality results

---

## Setup

### Step 1: Install GPT Researcher

GPT Researcher powers the research engine. Install it first:

```bash
# Option A: Install with research extras
pip install -e "packages/core[research]"

# Option B: Install directly
pip install gpt-researcher>=0.9.0
```

Verify installation:

```bash
curl http://localhost:8000/api/v1/agent-runs/capabilities
# Should show "gpt_researcher_installed": true
```

### Step 2: Configure a Search Provider

| Provider | Setup | Notes |
|----------|-------|-------|
| **SearXNG** | Set `SEARXNG_URL` | Self-hosted, unlimited, **recommended** |
| **Tavily** | Set `TAVILY_API_KEY` | Best results, 1000 free searches/month |
| **DuckDuckGo** | No setup needed | Free, but aggressive rate limits |

**SearXNG setup:**
```bash
docker run -d --name searxng \
  -p 8888:8080 \
  -e SEARXNG_BASE_URL=http://localhost:8888 \
  searxng/searxng
```

Add to `.env`:
```bash
SEARXNG_URL=http://localhost:8888
```

### Step 3: Create an Agent Source

1. Go to **Sources** → **Add Source**
2. Select **AI Agent** as the source type
3. Enter your research topic/prompt
4. Choose strategy (Simple, Comprehensive, or Deep)
5. Save and add to a feed

### Example Prompts

```
Research the latest developments in AI language models, focusing on
open-source alternatives to GPT-4 released in the last 3 months.
```

```
Analyze the competitive landscape of cloud-native database solutions,
comparing pricing, features, and market positioning.
```

### LLM Provider Mapping

GPT Researcher automatically uses your configured LLM provider:

| Reconly Provider | GPT Researcher Config |
|------------------|----------------------|
| Ollama | Uses `OLLAMA_BASE_URL`, model as `SMART_LLM` |
| OpenAI | Uses `OPENAI_API_KEY`, model as `SMART_LLM` |
| Anthropic | Uses `ANTHROPIC_API_KEY`, model as `SMART_LLM` |
| LM Studio | Uses `OPENAI_BASE_URL` (OpenAI-compatible API) |

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

1. Use **Ollama** or **LM Studio** with local models for unlimited free research
2. Start with **Simple** strategy and upgrade only when needed
3. Use **SearXNG** instead of Tavily to avoid API costs
4. Set lower `max_subtopics` for comprehensive strategies

---

## Troubleshooting

### "GPT Researcher not installed"

GPT Researcher is required. Install it:
```bash
pip install -e "packages/core[research]"
# or
pip install gpt-researcher>=0.9.0
```

### "Search provider not configured"

Set a search provider in `.env`:
```bash
# Recommended: SearXNG
SEARXNG_URL=http://localhost:8888

# Or: Tavily
TAVILY_API_KEY=tvly-xxxxx
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

### Local models produce poor results

GPT Researcher works best with capable models. For Ollama or LM Studio:
- Use `llama3.1:70b` or larger for best results
- `llama3.2` or `qwen2.5:7b` work for simpler research but may miss nuances
- Ensure adequate RAM/VRAM for the model (8GB+ for 7B models, 16GB+ for larger)

---

## See Also

- [Search Framework Configuration](../configuration.md#agent-settings)
- [LLM Provider Setup](../setup.md#llm-providers)
- [GPT Researcher Documentation](https://docs.gptr.dev/)
