# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-XX

Initial public release.

### Added

#### Core Features
- **Multi-source aggregation** - RSS/Atom feeds, YouTube channels, websites, email/IMAP, AI research agents
- **AI-powered summarization** - Configurable summarization with multiple LLM providers
- **Research agents** - Autonomous topic investigation with web search and content fetching
- **GPT Researcher integration** - Comprehensive and deep research strategies for thorough analysis

#### Knowledge Management
- **RAG knowledge system** - Semantic search with vector embeddings and citations
- **Knowledge graph** - Entity extraction and relationship visualization
- **Digest management** - Organize content into feeds with tagging and filtering

#### LLM Support
- **Ollama** - Local LLM inference (default, privacy-first)
- **OpenAI** - GPT-4, GPT-4o, GPT-4o-mini
- **Anthropic** - Claude 3.5 Sonnet, Claude 3 Haiku
- **HuggingFace** - Open-weight models via Inference API

#### Search Providers
- **SearXNG** - Self-hosted meta-search (recommended)
- **Tavily** - AI-optimized search API
- **DuckDuckGo** - Free, no API key required

#### Export & Integration
- **PKM export** - Obsidian, Logseq, and markdown formats
- **Email digests** - Scheduled email reports
- **Webhooks** - Integration with n8n, Zapier, and automation tools
- **REST API** - Full API access for all features

#### Deployment
- **Docker support** - Single command setup with docker-compose
- **SQLite or PostgreSQL** - Flexible database options
- **Optional authentication** - Password protection for public deployments

### Infrastructure
- FastAPI backend with async support
- Vue 3 + Astro frontend
- Structured logging with trace IDs
- Circuit breaker pattern for resilient fetching

[Unreleased]: https://github.com/reconlyeu/reconly/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/reconlyeu/reconly/releases/tag/v0.1.0
