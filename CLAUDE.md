# Claude Code Project Instructions

## Windows Compatibility

When editing files on Windows, always use relative paths (e.g., `.env.example`) instead of absolute paths (e.g., `C:\Users\...\file`). Absolute paths with backslashes cause "unexpectedly modified" errors due to path normalization issues.

## Project Overview

This is Reconly (formerly Reconly) - an AI-powered RSS aggregator and content summarization platform.

## Repository Structure

- `packages/core/` - reconly-core: CLI and content processing
- `packages/api/` - reconly-api: FastAPI server
- `packages/mcp/` - reconly-mcp: Model Context Protocol server
- `ui/` - Frontend (Astro)
- `tests/` - Test suite

## Key Commands

```bash
# Install packages
pip install -e packages/core
pip install -e packages/api
pip install -e packages/mcp

# Run API server
python -m uvicorn reconly_api.main:app --reload

# Run tests
pytest tests/

# CLI
reconly --help
```
