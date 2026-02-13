# Troubleshooting

Common issues and how to resolve them.

## Feed Runs

### Feed run fails with fetch errors

**Symptom:** Feed run shows errors for one or more sources.

**Causes and fixes:**
- **Source URL changed or is down** — Check the source URL is still valid. Edit the source and update the URL if needed.
- **Rate limiting** — Some sites throttle frequent requests. Space out your feed schedules.
- **Network issues** — Verify Reconly can reach the internet (especially in Docker setups, check DNS and proxy settings).

### Source circuit breaker tripped

**Symptom:** Source shows a warning icon and stops fetching.

A circuit breaker opens after repeated failures to protect against wasting resources on broken sources.

**Fix:**
1. Check that the source URL is still valid
2. Fix the underlying issue (URL, credentials, network)
3. Click the **Reset circuit breaker** button on the source, or use the API:
   ```
   POST /api/v1/sources/{source_id}/reset-circuit-breaker
   ```

### Schedule not triggering

**Symptom:** Feed has a schedule but runs don't appear at the expected time.

**Checks:**
- Verify the schedule is **enabled** (toggle on the feed)
- Check the cron expression is correct — Reconly uses standard 5-field cron (`minute hour day month weekday`)
- Confirm the timezone setting matches your expectations (set via `SCHEDULER_TIMEZONE` environment variable)
- The API server must be running for schedules to fire

## Empty Digests

### No new content in digest

**Symptom:** Feed run succeeds but produces no digest entries.

**Causes:**
- **No new content** — Sources had no new articles since the last run. This is normal.
- **Filters too restrictive** — Check your include/exclude keyword filters. Try running without filters temporarily.
- **Deduplication** — Reconly skips articles it has already processed. If you changed the source URL slightly, old articles may be treated as new.

### Summaries are low quality

**Symptom:** Digest summaries are generic, truncated, or miss key points.

**Fixes:**
- **Use a better model** — Larger models (14B+ parameters locally, or cloud providers) produce significantly better summaries
- **Adjust the prompt template** — Edit your prompt template to be more specific about what you want (language, length, focus areas)
- **Check content length** — Very short source articles produce thin summaries. This is expected.

## Chat

### Chat returns no results

**Symptom:** Chat says it couldn't find relevant content.

**Checks:**
- **RAG must be enabled** — Chat requires embeddings. See the [RAG setup guide](../admin/rag-setup.md).
- **Embeddings must exist** — After enabling RAG, run your feeds again so new content gets embedded. Existing digests are not retroactively embedded.
- **Try broader queries** — Semantic search works best with natural language questions, not single keywords.

### Chat responses are slow

**Causes:**
- **Local LLM performance** — Smaller machines may take 10-30 seconds for responses. Consider a cloud provider for chat if latency matters.
- **Large context** — When many relevant documents are found, the LLM processes more text. This is normal.

## Email

### Email digest not received

**Checks:**
- Verify SMTP settings in configuration (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`)
- Check the feed has email export enabled with valid recipient addresses
- Check server logs for SMTP errors
- Verify the email isn't in your spam folder

## Knowledge Graph

### Graph is empty

**Causes:**
- **Entity extraction not enabled** — Enable it in settings
- **No feed runs since enabling** — Entity extraction only processes new content
- **Too few digests** — The graph needs enough content to find meaningful connections

## Performance

### UI is slow to load

**Fixes:**
- Check that the API server is running and responsive (`GET /health`)
- Large digest lists may be slow — use filters and pagination
- If using Docker, ensure adequate memory allocation (2GB+ recommended)

### High memory usage

**Causes:**
- Embedding models consume significant memory (1-4GB depending on model)
- Running both LLM and embedding models locally requires substantial RAM
- **Fix:** Consider using a cloud provider for one or both, or use smaller models

## Getting Help

If your issue isn't covered here:

1. Check the [configuration reference](../admin/configuration.md) for environment variables
2. Review server logs for error details (structured JSON logs with trace IDs)
3. Open an issue at [GitHub Issues](https://github.com/reconlyeu/reconly/issues)
4. Join the discussion at [GitHub Discussions](https://github.com/reconlyeu/reconly/discussions)
