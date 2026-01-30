# Developing Reconly Extensions

This guide shows how to create distributable extension packages for Reconly. Extensions allow you to add new exporters, fetchers, or providers that can be shared with other users.

## Overview

Reconly extensions are Python packages that use **entry points** to register themselves with the core system. When users install your extension via `pip`, it automatically becomes available in Reconly without any code changes.

**Extension Types:**
- **Exporter** - Export digests to new formats (Notion, Roam, etc.)
- **Fetcher** - Fetch content from new sources (Reddit, HackerNews, etc.)
- **Provider** - LLM providers (coming soon)

## Quick Start

### 1. Create Package Structure

```
reconly-ext-myformat/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── reconly_ext_myformat/
│       ├── __init__.py
│       └── exporter.py      # or fetcher.py
└── tests/
    └── test_myformat.py
```

### 2. Configure pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "reconly-ext-myformat"
version = "1.0.0"
description = "MyFormat exporter extension for Reconly"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
keywords = ["reconly", "extension", "exporter", "myformat"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "reconly-core>=0.5.0",  # Required
]

[project.urls]
Homepage = "https://github.com/you/reconly-ext-myformat"
Repository = "https://github.com/you/reconly-ext-myformat"

# Entry point registration - this is the key part
[project.entry-points."reconly.exporters"]
myformat = "reconly_ext_myformat:MyFormatExporter"

[tool.hatch.build.targets.wheel]
packages = ["src/reconly_ext_myformat"]
```

### 3. Create the Extension Class

In `src/reconly_ext_myformat/__init__.py`:

```python
from reconly_ext_myformat.exporter import MyFormatExporter

__all__ = ["MyFormatExporter"]
```

In `src/reconly_ext_myformat/exporter.py`:

```python
"""MyFormat exporter for Reconly."""
from typing import Any, Dict, List

from reconly_core.exporters.base import (
    BaseExporter,
    ExportResult,
    ExporterConfigSchema,
    ConfigField,
)


class MyFormatExporter(BaseExporter):
    """Export digests in MyFormat."""

    # Extension metadata - REQUIRED for Reconly
    __extension_name__ = "MyFormat Exporter"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"
    __extension_description__ = "Export digests to MyFormat"
    __extension_homepage__ = "https://github.com/you/reconly-ext-myformat"

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """Export digests to MyFormat."""
        config = config or {}

        # Your export logic here
        content = self._generate_content(digests, config)

        return ExportResult(
            content=content,
            filename="digests.myformat",
            content_type=self.get_content_type(),
            digest_count=len(digests)
        )

    def _generate_content(self, digests, config):
        """Generate export content."""
        lines = []
        for digest in digests:
            lines.append(f"# {digest.title}")
            lines.append(digest.summary or "")
            lines.append("")
        return "\n".join(lines)

    def get_format_name(self) -> str:
        return "myformat"

    def get_content_type(self) -> str:
        return "text/plain"

    def get_file_extension(self) -> str:
        return "myf"

    def get_description(self) -> str:
        return "MyFormat custom export"
```

### 4. Install and Test

```bash
# Install in development mode
cd reconly-ext-myformat
pip install -e .

# Restart Reconly
# Your extension should appear in Settings > Extensions
```

---

## Entry Point Groups

Register your extension in the appropriate entry point group:

| Extension Type | Entry Point Group |
|---------------|-------------------|
| Exporter | `reconly.exporters` |
| Fetcher | `reconly.fetchers` |
| Provider (LLM) | `reconly.providers` |
| Embedding Provider | `reconly.embedding_providers` |

**Example for each type:**

```toml
# Exporter
[project.entry-points."reconly.exporters"]
notion = "reconly_ext_notion:NotionExporter"

# Fetcher
[project.entry-points."reconly.fetchers"]
reddit = "reconly_ext_reddit:RedditFetcher"

# LLM Provider
[project.entry-points."reconly.providers"]
groq = "reconly_ext_groq:GroqProvider"

# Embedding Provider
[project.entry-points."reconly.embedding_providers"]
cohere = "reconly_ext_cohere:CohereEmbedding"
```

---

## Extension Metadata

Define these class attributes for your extension to be properly displayed in the UI:

| Attribute | Required | Description |
|-----------|----------|-------------|
| `__extension_name__` | Yes | Human-readable name shown in UI |
| `__extension_version__` | Yes | Extension version (semver recommended) |
| `__extension_author__` | Yes | Your name or organization |
| `__extension_min_reconly__` | Yes | Minimum Reconly version required |
| `__extension_description__` | Yes | Brief description of functionality |
| `__extension_homepage__` | No | URL to docs or repository |

**Example:**

```python
class MyExporter(BaseExporter):
    __extension_name__ = "My Exporter"
    __extension_version__ = "1.2.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"
    __extension_description__ = "Export digests to My Service"
    __extension_homepage__ = "https://github.com/you/reconly-ext-my"
```

---

## Configuration Schema

Extensions can define configuration fields that appear in the Settings UI.

### Exporter Config Schema

```python
from reconly_core.exporters.base import (
    BaseExporter,
    ExporterConfigSchema,
    ConfigField,
)

class MyExporter(BaseExporter):
    def get_config_schema(self) -> ExporterConfigSchema:
        return ExporterConfigSchema(
            supports_direct_export=True,  # Can write directly to filesystem
            fields=[
                ConfigField(
                    key="output_path",
                    type="path",
                    label="Output Path",
                    description="Where to save exported files",
                    required=True,
                    placeholder="/path/to/output",
                ),
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="Your service API key",
                    required=True,
                    secret=True,  # Will be masked in UI
                ),
                ConfigField(
                    key="include_tags",
                    type="boolean",
                    label="Include Tags",
                    description="Include tags in export",
                    default=True,
                    required=False,
                ),
            ],
        )
```

### Fetcher Config Schema

```python
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema
from reconly_core.config_types import ConfigField

class MyFetcher(BaseFetcher):
    def get_config_schema(self) -> FetcherConfigSchema:
        return FetcherConfigSchema(
            supports_incremental_fetch=True,
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="API key for the service",
                    required=True,
                    env_var="MY_SERVICE_API_KEY",  # Can be set via env var
                    editable=False,  # Only via env var, not UI
                    secret=True,
                ),
                ConfigField(
                    key="max_items",
                    type="integer",
                    label="Max Items",
                    description="Maximum items per fetch",
                    default=50,
                    required=False,
                ),
            ],
        )
```

### ConfigField Properties

| Property | Type | Description |
|----------|------|-------------|
| `key` | str | Unique identifier for setting |
| `type` | str | `"string"`, `"boolean"`, `"integer"`, `"path"`, or `"connection"` |
| `label` | str | Human-readable label for UI |
| `description` | str | Help text |
| `required` | bool | Whether field is required for activation |
| `default` | Any | Default value |
| `placeholder` | str | Placeholder text for input |
| `secret` | bool | Mask value in UI (for API keys) |
| `env_var` | str | Environment variable name |
| `editable` | bool | Whether editable in UI (False = env var only) |
| `connection_type` | str | For `type="connection"`, filter connections by type |

### Activation Behavior

- Extensions with **no required fields**: Auto-enabled on install
- Extensions with **required fields**: Disabled until all required fields are configured
- Users configure via Settings > Extensions > Configure

---

## Using Connections for Authentication

Extensions can use the Connections system for reusable credential management. This is useful for per-user credentials that vary by installation.

### When to Use Connections

**Use Connections for:**
- Per-user credentials (IMAP passwords, personal API keys)
- Reusable credentials across multiple sources/exporters
- Credentials that need health tracking and testing

**Use ConfigField with env_var for:**
- System-wide API keys shared across all users
- Infrastructure configuration (database URLs, service endpoints)
- Settings that don't vary per user

### Declaring Connection Requirements

Add connection metadata to your component:

**For fetchers:**
```python
from reconly_core.fetchers.base import BaseFetcher, FetcherMetadata

class MyFetcher(BaseFetcher):
    # Extension metadata
    __extension_name__ = "My Service Fetcher"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"

    # Component metadata with connection requirements
    metadata = FetcherMetadata(
        name='my-service',
        display_name='My Service',
        description='Fetch from My Service',
        icon='mdi:cloud',

        # Connection requirements
        requires_connection=True,
        connection_types=['api_key', 'http_basic'],  # Supported types
    )

    def get_config_schema(self):
        return FetcherConfigSchema(
            fields=[
                ConfigField(
                    key='connection_id',
                    type='connection',
                    label='Connection',
                    description='Authentication credentials',
                    required=True,
                    connection_type='api_key',  # Filter to this type
                ),
                # Other source-specific fields...
            ]
        )
```

**For exporters:**
```python
from reconly_core.exporters.base import BaseExporter, ExporterMetadata

class MyExporter(BaseExporter):
    # Extension metadata
    __extension_name__ = "My Service Exporter"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"

    # Component metadata with connection requirements
    metadata = ExporterMetadata(
        name='my-service',
        display_name='My Service',
        description='Export to My Service',
        icon='mdi:upload',
        file_extension='.json',
        mime_type='application/json',

        # Connection requirements
        requires_connection=True,
        connection_types=['api_key'],
    )

    def get_config_schema(self):
        return ExporterConfigSchema(
            fields=[
                ConfigField(
                    key='connection_id',
                    type='connection',
                    label='Connection',
                    description='Authentication credentials',
                    required=True,
                    connection_type='api_key',
                ),
                # Other exporter-specific fields...
            ]
        )
```

### Accessing Injected Credentials

The backend automatically injects decrypted credentials with a `_connection_` prefix:

**For fetchers:**
```python
def fetch(self, url, since=None, max_items=None, **kwargs):
    # Credentials automatically injected by backend
    api_key = kwargs.get('_connection_api_key')
    endpoint = kwargs.get('_connection_endpoint', 'https://api.example.com')

    # Use for API calls
    headers = {'Authorization': f'Bearer {api_key}'}
    response = requests.get(f'{endpoint}/items', headers=headers)
    # ... process response
```

**For exporters:**
```python
def export(self, digests, config=None):
    config = config or {}

    # Credentials automatically injected by backend
    api_key = config.get('_connection_api_key')
    endpoint = config.get('_connection_endpoint', 'https://api.example.com')

    # Use for API calls
    headers = {'Authorization': f'Bearer {api_key}'}
    # ... export digests
```

### Connection Types

| Type | Use Case | Injected Fields |
|------|----------|-----------------|
| `email_imap` | IMAP mailboxes | `_connection_host`, `_connection_port`, `_connection_username`, `_connection_password`, `_connection_use_ssl` |
| `email_oauth` | OAuth providers | `_connection_provider`, `_connection_access_token`, `_connection_refresh_token` |
| `http_basic` | HTTP Basic Auth | `_connection_username`, `_connection_password` |
| `api_key` | API key auth | `_connection_api_key`, `_connection_endpoint` (optional) |

### Example: Reddit Fetcher with Connections

```python
"""Reddit fetcher with connection-based authentication."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from reconly_core.fetchers.base import BaseFetcher, FetcherMetadata, FetcherConfigSchema
from reconly_core.config_types import ConfigField


class RedditFetcher(BaseFetcher):
    """Fetch posts from Reddit subreddits."""

    __extension_name__ = "Reddit Fetcher"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"

    metadata = FetcherMetadata(
        name='reddit',
        display_name='Reddit',
        description='Fetch posts from Reddit',
        icon='mdi:reddit',
        requires_connection=True,
        connection_types=['api_key'],  # Reddit uses app credentials
    )

    def get_config_schema(self):
        return FetcherConfigSchema(
            supports_incremental_fetch=True,
            fields=[
                ConfigField(
                    key='connection_id',
                    type='connection',
                    label='Reddit API Connection',
                    description='Reddit app credentials',
                    required=True,
                    connection_type='api_key',
                ),
                ConfigField(
                    key='max_posts',
                    type='integer',
                    label='Max Posts',
                    description='Maximum posts to fetch per run',
                    default=50,
                    required=False,
                ),
            ],
        )

    def fetch(self, url, since=None, max_items=None, **kwargs):
        # Access injected credentials
        api_key = kwargs.get('_connection_api_key')
        if not api_key:
            raise ValueError("Reddit API key not configured")

        # Access source-specific config
        max_posts = kwargs.get('max_posts', 50)

        # Use credentials for API calls
        headers = {'Authorization': f'Bearer {api_key}'}
        # ... fetch from Reddit API
```

---

## Direct Export (Filesystem)

Exporters can support writing directly to the filesystem (e.g., Obsidian vault).

```python
from pathlib import Path
from reconly_core.exporters.base import ExportToPathResult

class MyExporter(BaseExporter):
    def get_config_schema(self) -> ExporterConfigSchema:
        return ExporterConfigSchema(
            supports_direct_export=True,  # Enable this
            fields=[...]
        )

    def export_to_path(
        self,
        digests: List[Any],
        base_path: str,
        config: Dict[str, Any] = None
    ) -> ExportToPathResult:
        """Export directly to filesystem."""
        config = config or {}
        target = Path(base_path)
        target.mkdir(parents=True, exist_ok=True)

        written = []
        errors = []

        for digest in digests:
            try:
                filename = f"{digest.id}.txt"
                filepath = target / filename
                content = self._format_digest(digest)
                filepath.write_text(content, encoding="utf-8")
                written.append(filename)
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return ExportToPathResult(
            success=len(errors) == 0,
            files_written=len(written),
            target_path=str(target),
            filenames=written,
            errors=errors,
        )
```

---

## Creating a Fetcher Extension

Fetchers follow a similar pattern but implement different abstract methods.

### Package Structure

```
reconly-ext-reddit/
├── pyproject.toml
├── src/
│   └── reconly_ext_reddit/
│       ├── __init__.py
│       └── fetcher.py
└── tests/
```

### pyproject.toml

```toml
[project.entry-points."reconly.fetchers"]
reddit = "reconly_ext_reddit:RedditFetcher"
```

### Fetcher Implementation

```python
"""Reddit fetcher for Reconly."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema
from reconly_core.config_types import ConfigField


class RedditFetcher(BaseFetcher):
    """Fetch content from Reddit."""

    __extension_name__ = "Reddit Fetcher"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"
    __extension_description__ = "Fetch posts from Reddit subreddits"
    __extension_homepage__ = "https://github.com/you/reconly-ext-reddit"

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Fetch posts from a subreddit."""
        # Your fetch logic here
        items = self._fetch_subreddit(url, since, max_items)
        return items

    def _fetch_subreddit(self, url, since, max_items):
        """Fetch from Reddit API."""
        # Implementation
        return [{
            "url": "https://reddit.com/...",
            "title": "Post Title",
            "content": "Post content...",
            "source_type": "reddit",
            "published": datetime.now().isoformat(),
            "author": "username",
        }]

    def get_source_type(self) -> str:
        return "reddit"

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the URL."""
        return "reddit.com" in url.lower() or "r/" in url.lower()

    def get_description(self) -> str:
        return "Fetch posts from Reddit subreddits"

    def get_config_schema(self) -> FetcherConfigSchema:
        return FetcherConfigSchema(
            supports_incremental_fetch=True,
            fields=[
                ConfigField(
                    key="client_id",
                    type="string",
                    label="Reddit Client ID",
                    description="Your Reddit API client ID",
                    required=True,
                    env_var="REDDIT_CLIENT_ID",
                    editable=False,
                    secret=True,
                ),
                ConfigField(
                    key="client_secret",
                    type="string",
                    label="Reddit Client Secret",
                    description="Your Reddit API client secret",
                    required=True,
                    env_var="REDDIT_CLIENT_SECRET",
                    editable=False,
                    secret=True,
                ),
            ],
        )
```

---

## Creating an Embedding Provider Extension

Embedding providers generate vector embeddings for RAG (Retrieval-Augmented Generation) and semantic search. Extensions can add support for new embedding services like Cohere, Voyage AI, or custom endpoints.

### Package Structure

```
reconly-ext-cohere-embed/
├── pyproject.toml
├── src/
│   └── reconly_ext_cohere_embed/
│       ├── __init__.py
│       └── provider.py
└── tests/
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "reconly-ext-cohere-embed"
version = "1.0.0"
description = "Cohere embedding provider for Reconly"
requires-python = ">=3.11"

[project.entry-points."reconly.embedding_providers"]
cohere = "reconly_ext_cohere_embed:CohereEmbedding"

[tool.hatch.build.targets.wheel]
packages = ["src/reconly_ext_cohere_embed"]
```

### Embedding Provider Implementation

```python
"""Cohere embedding provider for Reconly."""
import os
from typing import List, Optional

from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)
from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata
from reconly_core.config_types import ConfigField, ProviderConfigSchema


class CohereEmbedding(EmbeddingProvider):
    """Generate embeddings using Cohere's embedding API."""

    # Extension metadata - REQUIRED
    __extension_name__ = "Cohere Embeddings"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "1.0.0"
    __extension_description__ = "Generate embeddings via Cohere API"
    __extension_homepage__ = "https://github.com/you/reconly-ext-cohere-embed"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize the Cohere embedding provider."""
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('COHERE_API_KEY')
        self.model = model or 'embed-english-v3.0'
        self._dimension = 1024  # Cohere embed-v3 dimension

        if not self.api_key:
            raise ValueError(
                "Cohere API key required. Set COHERE_API_KEY environment variable."
            )

    @classmethod
    def get_metadata(cls) -> EmbeddingProviderMetadata:
        """Get provider metadata for registry and UI display."""
        return EmbeddingProviderMetadata(
            name='cohere',
            display_name='Cohere',
            description='Cohere embedding API (embed-v3)',
            icon='simple-icons:cohere',
            requires_api_key=True,
            supports_base_url=False,
            model_param_name='model',
            is_local=False,
            default_model='embed-english-v3.0',
        )

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            raise ValueError("Cannot embed empty list of texts")

        # Your embedding implementation here
        # Call Cohere API and return embeddings
        import cohere
        co = cohere.Client(self.api_key)
        response = co.embed(
            texts=texts,
            model=self.model,
            input_type="search_document"
        )
        return response.embeddings

    def get_dimension(self) -> int:
        """Get embedding vector dimension."""
        return self._dimension

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'cohere'

    @classmethod
    def get_capabilities(cls) -> EmbeddingProviderCapabilities:
        """Get provider capabilities."""
        return EmbeddingProviderCapabilities(
            is_local=False,
            requires_api_key=True,
            supports_batch=True,
            max_batch_size=96,
            max_tokens_per_text=512,
            dimension=1024,
        )

    def is_available(self) -> bool:
        """Check if provider is available."""
        return self.api_key is not None and len(self.api_key) > 0

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []
        if not self.api_key:
            errors.append("Cohere API key is required. Set COHERE_API_KEY.")
        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get configuration schema for settings UI."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="Cohere API key",
                    env_var="COHERE_API_KEY",
                    editable=False,
                    secret=True,
                    required=True,
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Model",
                    description="Embedding model (e.g., embed-english-v3.0)",
                    default="embed-english-v3.0",
                    editable=True,
                ),
            ],
            requires_api_key=True,
        )

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[EmbeddingModelInfo]:
        """List available embedding models."""
        return [
            EmbeddingModelInfo(
                id='embed-english-v3.0',
                name='Embed English v3',
                provider='cohere',
                dimension=1024,
                is_default=True,
            ),
            EmbeddingModelInfo(
                id='embed-multilingual-v3.0',
                name='Embed Multilingual v3',
                provider='cohere',
                dimension=1024,
                is_default=False,
            ),
        ]
```

### EmbeddingProviderMetadata Fields

The `get_metadata()` classmethod must return an `EmbeddingProviderMetadata` instance:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Internal identifier (e.g., 'cohere', 'voyage') |
| `display_name` | str | Yes | Human-readable name for UI |
| `description` | str | Yes | Short description |
| `icon` | str | No | Iconify icon identifier (e.g., 'simple-icons:cohere') |
| `requires_api_key` | bool | No | Whether provider needs an API key (default: True) |
| `supports_base_url` | bool | No | Whether provider supports custom base URL (default: False) |
| `model_param_name` | str | No | Parameter name for model selection: 'model' or 'model_id' (default: 'model') |
| `is_local` | bool | No | Whether provider runs locally (default: False) |
| `default_model` | str | No | Default model identifier |

### Required Methods

Your embedding provider must implement these methods:

| Method | Description |
|--------|-------------|
| `embed(texts: List[str]) -> List[List[float]]` | Generate embeddings (async) |
| `get_dimension() -> int` | Return embedding vector dimension |
| `get_provider_name() -> str` | Return provider identifier |
| `get_capabilities() -> EmbeddingProviderCapabilities` | Return provider capabilities (classmethod) |
| `get_metadata() -> EmbeddingProviderMetadata` | Return provider metadata (classmethod) |
| `is_available() -> bool` | Check if provider is available |
| `validate_config() -> List[str]` | Return list of config errors |

### Testing Embedding Providers

```python
"""Tests for Cohere embedding provider."""
import pytest
from unittest.mock import patch, MagicMock

from reconly_ext_cohere_embed import CohereEmbedding


class TestCohereEmbedding:
    """Tests for CohereEmbedding provider."""

    def test_metadata(self):
        """Test get_metadata returns correct values."""
        metadata = CohereEmbedding.get_metadata()
        assert metadata.name == 'cohere'
        assert metadata.requires_api_key is True
        assert metadata.is_local is False

    def test_capabilities(self):
        """Test get_capabilities returns valid capabilities."""
        caps = CohereEmbedding.get_capabilities()
        assert caps.requires_api_key is True
        assert caps.supports_batch is True
        assert caps.dimension > 0

    @patch.dict('os.environ', {'COHERE_API_KEY': 'test-key'})
    def test_initialization(self):
        """Test provider initialization."""
        provider = CohereEmbedding()
        assert provider.api_key == 'test-key'
        assert provider.get_provider_name() == 'cohere'

    def test_list_models(self):
        """Test list_models returns model info."""
        models = CohereEmbedding.list_models()
        assert len(models) > 0
        assert all(m.provider == 'cohere' for m in models)
```

---

## Naming Convention

**Package Name:** `reconly-ext-{name}`
- Examples: `reconly-ext-notion`, `reconly-ext-reddit`, `reconly-ext-txt`

**Entry Point Name:** Short lowercase identifier
- Examples: `notion`, `reddit`, `txt`

**Class Name:** `{Name}Exporter` or `{Name}Fetcher`
- Examples: `NotionExporter`, `RedditFetcher`, `TxtExporter`

---

## Version Compatibility

Set `__extension_min_reconly__` to the minimum Reconly version your extension supports.

```python
__extension_min_reconly__ = "0.5.0"
```

Reconly will:
- Refuse to load incompatible extensions
- Show a clear error message in the UI
- Log the version mismatch

**How to determine min version:**
- Use the version where the APIs you depend on were introduced
- Test with that version before publishing
- Document compatibility in your README

---

## Testing Your Extension

### Local Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install reconly-core (if not in a monorepo)
pip install reconly-core

# Install your extension in dev mode
pip install -e .

# Run tests
pytest tests/
```

### Unit Tests

```python
"""Tests for MyFormat exporter."""
import pytest
from unittest.mock import MagicMock

from reconly_ext_myformat import MyFormatExporter


def create_mock_digest(**kwargs):
    """Create a mock digest for testing."""
    digest = MagicMock()
    digest.id = kwargs.get("id", 1)
    digest.title = kwargs.get("title", "Test Title")
    digest.summary = kwargs.get("summary", "Test summary")
    digest.content = kwargs.get("content", "Test content")
    digest.source_name = kwargs.get("source_name", "Test Source")
    digest.source_url = kwargs.get("source_url", "https://example.com")
    digest.published_at = kwargs.get("published_at", None)
    digest.tags = kwargs.get("tags", [])
    return digest


class TestMyFormatExporter:
    """Tests for MyFormatExporter."""

    def test_metadata_attributes(self):
        """Test extension metadata is defined."""
        assert hasattr(MyFormatExporter, "__extension_name__")
        assert hasattr(MyFormatExporter, "__extension_version__")
        assert hasattr(MyFormatExporter, "__extension_min_reconly__")

    def test_export_empty_list(self):
        """Test exporting empty digest list."""
        exporter = MyFormatExporter()
        result = exporter.export([])
        assert result.digest_count == 0

    def test_export_single_digest(self):
        """Test exporting a single digest."""
        digest = create_mock_digest(title="Test Article")
        exporter = MyFormatExporter()
        result = exporter.export([digest])

        assert result.digest_count == 1
        assert "Test Article" in result.content

    def test_format_name(self):
        """Test get_format_name returns correct value."""
        exporter = MyFormatExporter()
        assert exporter.get_format_name() == "myformat"

    def test_content_type(self):
        """Test get_content_type returns correct value."""
        exporter = MyFormatExporter()
        assert "text/" in exporter.get_content_type()
```

### Integration Test with Reconly

```python
"""Integration tests requiring reconly-core."""
import pytest

# Skip if reconly-core not installed
pytest.importorskip("reconly_core")

from reconly_core.exporters import get_exporter, list_exporters


class TestIntegration:
    """Integration tests with Reconly registry."""

    def test_registered_in_exporters(self):
        """Test extension is registered."""
        exporters = list_exporters()
        assert "myformat" in exporters

    def test_get_exporter(self):
        """Test getting exporter from registry."""
        exporter = get_exporter("myformat")
        assert exporter is not None
        assert exporter.get_format_name() == "myformat"
```

---

## Publishing

You have two options for publishing your extension:

### Option 1: GitHub Marketplace (Recommended for Verified Extensions)

The official [reconly-extensions](https://github.com/reconlyeu/reconly-extensions) repository hosts verified extensions with one-click installation.

**Benefits:**
- One-click install from Reconly UI
- "Verified" badge in catalog
- Official community support
- No PyPI publishing required

**Steps:**

1. **Fork the repository**: Fork [reconly-extensions](https://github.com/reconlyeu/reconly-extensions)

2. **Add your extension** to `extensions/reconly-ext-{name}/`:
   ```
   extensions/
     reconly-ext-myformat/
       pyproject.toml
       README.md
       src/
         reconly_ext_myformat/
           __init__.py
           exporter.py  # or fetcher.py
   ```

3. **Update catalog.json** at repo root:
   ```json
   {
     "version": "2.0",
     "extensions": [
       {
         "package": "reconly-ext-myformat",
         "name": "MyFormat Exporter",
         "type": "exporter",
         "description": "Export digests to MyFormat",
         "author": "Your Name",
         "version": "1.0.0",
         "verified": true,
         "install_source": "github",
         "github_url": "git+https://github.com/reconlyeu/reconly-extensions.git#subdirectory=extensions/reconly-ext-myformat",
         "homepage": "https://github.com/reconlyeu/reconly-extensions/tree/main/extensions/reconly-ext-myformat",
         "min_reconly_version": "1.0.0"
       }
     ]
   }
   ```

4. **Submit Pull Request** with:
   - Clear description of functionality
   - Any special requirements
   - Testing instructions

5. **Review Process**:
   - Code review for security and quality
   - Testing by maintainers
   - Merge and automatic catalog update
   - "Verified" badge in UI

**Catalog Fields:**
- `package`: Package name (must start with `reconly-ext-`)
- `name`: Display name shown in UI
- `type`: `exporter`, `fetcher`, or `provider`
- `description`: Brief description
- `author`: Your name
- `version`: Extension version
- `verified`: true for verified extensions
- `install_source`: `"github"` for GitHub installations
- `github_url`: Full GitHub URL with subdirectory
- `homepage`: Link to extension documentation
- `min_reconly_version`: Minimum Reconly version required

### Option 2: Community Extensions (Your Own Repository)

You can also publish extensions in your own GitHub repository.

**Steps:**

1. **Create your repository**: `your-username/reconly-ext-myformat`

2. **Structure your extension**:
   ```
   reconly-ext-myformat/
     pyproject.toml
     README.md
     src/
       reconly_ext_myformat/
         __init__.py
         exporter.py
   ```

3. **Users install via GitHub URL**:
   ```bash
   pip install git+https://github.com/your-username/reconly-ext-myformat.git
   ```

4. **Optional: Submit to community catalog**:
   Submit a PR to add your extension to the catalog as a community extension:
   ```json
   {
     "package": "reconly-ext-myformat",
     "name": "MyFormat Exporter",
     "type": "exporter",
     "description": "Export digests to MyFormat",
     "author": "Your Name",
     "version": "1.0.0",
     "verified": false,
     "install_source": "github",
     "github_url": "git+https://github.com/your-username/reconly-ext-myformat.git",
     "homepage": "https://github.com/your-username/reconly-ext-myformat",
     "min_reconly_version": "1.0.0"
   }
   ```

### Option 3: PyPI (Traditional)

You can also publish to PyPI for traditional pip installation.

```bash
# Build
pip install build
python -m build

# Upload to PyPI
pip install twine
twine upload dist/*
```

Then add to catalog:
```json
{
  "package": "reconly-ext-myformat",
  "name": "MyFormat Exporter",
  "type": "exporter",
  "install_source": "pypi",
  "homepage": "https://pypi.org/project/reconly-ext-myformat/"
}
```

## Installation Sources

Extensions can be installed from three sources:

| Source | When to Use | Example |
|--------|-------------|---------|
| **GitHub (Verified)** | Official verified extensions in monorepo | Automatic via catalog |
| **GitHub (Community)** | Your own repository, community extensions | `pip install git+https://github.com/user/repo.git` |
| **PyPI** | Traditional package distribution | `pip install reconly-ext-myformat` |

Users can install from any source, but verified extensions get a badge in the UI and one-click installation.

---

## Best Practices

1. **Start with `reconly-ext-`** package name for discoverability
2. **Define all metadata attributes** for proper UI display
3. **Set realistic `min_reconly`** version
4. **Handle errors gracefully** - return empty results, don't crash
5. **Write tests** - both unit and integration
6. **Document configuration** in README
7. **Use `secret=True`** for API keys and sensitive data
8. **Provide sensible defaults** for optional config
9. **Sanitize filenames** when writing to filesystem
10. **Respect rate limits** when calling external APIs

---

## Example Extensions

- [reconly-ext-txt](https://github.com/reconly/reconly-ext-txt) - Plain text exporter (reference implementation)

---

## Questions?

- Check the [ADDING_EXPORTERS.md](./ADDING_EXPORTERS.md) for exporter API details
- Check the [ADDING_FETCHERS.md](./ADDING_FETCHERS.md) for fetcher API details
- Open an issue on GitHub if stuck
