# Adding New Export Formats

This guide shows you how to add a new export format to Reconly. The self-registering exporter architecture makes this straightforward.

## Overview

Reconly uses an **exporter registry pattern** that allows new export formats to be added without modifying core factory code. Contributors can:

1. Create a new exporter class inheriting from `BaseExporter`
2. Decorate it with `@register_exporter('format-name')`
3. Define the `metadata` class variable
4. Implement required abstract methods

The exporter becomes automatically discoverable and the UI renders it dynamically from metadata.

## Step-by-Step Guide

### 1. Create Your Exporter Class

Create a new file in `packages/core/reconly_core/exporters/`:

```python
"""My Custom Format exporter implementation."""
from typing import Any, Dict, List

from reconly_core.exporters.base import BaseExporter, ExportResult
from reconly_core.exporters.metadata import ExporterMetadata
from reconly_core.exporters.registry import register_exporter


@register_exporter('my-format')  # <-- Register your exporter
class MyFormatExporter(BaseExporter):
    """Export digests in My Custom Format."""

    # Exporter metadata (required)
    metadata = ExporterMetadata(
        name='my-format',
        display_name='My Format',
        description='Export digests to My Custom Format',
        icon='mdi:file-document-outline',  # Iconify format
        file_extension='.txt',
        mime_type='text/plain',
        path_setting_key='export_path',
        ui_color='#3B82F6',
    )

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to My Custom Format.

        Args:
            digests: List of Digest model instances
            config: Optional configuration (format-specific options)

        Returns:
            ExportResult with content and metadata
        """
        config = config or {}

        # Your export logic here
        content = self._generate_content(digests, config)

        return ExportResult(
            content=content,
            filename='digests.myformat',
            content_type=self.get_content_type(),
            digest_count=len(digests)
        )

    def _generate_content(self, digests, config):
        """Generate the export content."""
        # Your format-specific logic
        output = []
        for digest in digests:
            digest_dict = digest.to_dict()
            output.append(f"Title: {digest_dict['title']}")
            output.append(f"Summary: {digest_dict.get('summary', '')}")
            output.append("---")
        return '\n'.join(output)

    def get_format_name(self) -> str:
        return 'my-format'

    def get_content_type(self) -> str:
        return 'text/plain'  # Or appropriate MIME type

    def get_file_extension(self) -> str:
        return 'txt'  # File extension without dot

    def get_description(self) -> str:
        return 'My Custom Format with structured output'
```

### 2. Implement Required Abstract Methods

Your exporter **must** implement these abstract methods:

#### `export(digests: List[Any], config: Dict[str, Any] = None) -> ExportResult`

Main method that generates the export output:

```python
def export(self, digests: List[Any], config: Dict[str, Any] = None) -> ExportResult:
    """Export digests to this format."""
    config = config or {}

    # Generate content from digests
    content = self._generate_content(digests, config)

    return ExportResult(
        content=content,  # str or bytes
        filename='digests.ext',  # Suggested filename
        content_type='application/octet-stream',  # MIME type
        digest_count=len(digests)
    )
```

#### `get_format_name() -> str`

Return a unique format identifier:

```python
def get_format_name(self) -> str:
    return 'my-format'
```

#### `get_content_type() -> str`

Return the MIME type for HTTP responses:

```python
def get_content_type(self) -> str:
    return 'application/json'  # or 'text/csv', 'text/markdown', etc.
```

#### `get_file_extension() -> str`

Return the file extension (without dot) for downloads:

```python
def get_file_extension(self) -> str:
    return 'json'  # or 'csv', 'md', etc.
```

### 3. Define Exporter Metadata

Every exporter **must** define a `metadata` class variable of type `ExporterMetadata`. This metadata enables:

- **Dynamic UI rendering** - Frontend displays exporter names, icons, and colors from API
- **File handling** - System uses metadata for file extensions and MIME types
- **Zero-code extensions** - New exporters work without frontend changes

```python
from reconly_core.exporters.metadata import ExporterMetadata

class MyFormatExporter(BaseExporter):
    metadata = ExporterMetadata(
        name='my-format',             # Must match @register_exporter name
        display_name='My Format',     # Human-readable name for UI
        description='Export digests to My Custom Format',
        icon='mdi:file-document-outline',  # Iconify format

        # File handling
        file_extension='.txt',        # File extension (with dot)
        mime_type='text/plain',       # MIME type for HTTP responses

        # Configuration
        path_setting_key='export_path',  # Setting key for export path

        # UI theming
        ui_color='#3B82F6',           # Hex color for UI elements
    )
```

#### Metadata Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Internal identifier, must match `@register_exporter` name |
| `display_name` | `str` | Human-readable name for UI display |
| `description` | `str` | Short description for tooltips/help |
| `icon` | `str \| None` | Iconify icon identifier (e.g., `mdi:code-json`) |
| `file_extension` | `str` | File extension including dot (e.g., `.json`, `.md`) |
| `mime_type` | `str` | MIME type for HTTP responses |
| `path_setting_key` | `str` | Setting key for export path (default: `'export_path'`) |
| `ui_color` | `str \| None` | Hex color for UI theming (e.g., `'#7C3AED'`) |

#### Special Export Path Handling

The `path_setting_key` field is used to identify which configuration field contains the export destination. For example:

- Standard exporters use `'export_path'`
- Obsidian exporter uses `'vault_path'`

This enables the backend to use the correct setting when exporting files:

```python
# In export logic
exporter = get_exporter('obsidian')
path_key = exporter.metadata.path_setting_key  # 'vault_path'
export_path = settings.get(f'export.obsidian.{path_key}')
```

For more details on the metadata system, see [Component Metadata Architecture](architecture/component-metadata.md).

### 4. Optional: Override get_description()

Provide a human-readable description:

```python
def get_description(self) -> str:
    return 'JSON format with pretty printing'
```

### 4. Create Tests

Create `tests/core/exporters/test_my_format.py`:

```python
"""Tests for My Format exporter."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from reconly_core.exporters import get_exporter, list_exporters
from reconly_core.exporters.base import ExportResult


def create_mock_digest(**kwargs):
    """Create a mock digest for testing."""
    digest = MagicMock()
    digest.id = kwargs.get('id', 1)
    digest.title = kwargs.get('title', 'Test Title')
    digest.url = kwargs.get('url', 'https://example.com')
    digest.summary = kwargs.get('summary', 'Test summary')
    digest.content = kwargs.get('content', 'Test content')
    digest.source_type = kwargs.get('source_type', 'rss')
    digest.created_at = kwargs.get('created_at', datetime.now())

    digest.to_dict.return_value = {
        'id': digest.id,
        'title': digest.title,
        'url': digest.url,
        'summary': digest.summary,
        'content': digest.content,
        'source_type': digest.source_type,
    }

    return digest


class TestMyFormatExporter:
    """Tests for MyFormatExporter."""

    def test_registered(self):
        """Test that exporter is registered."""
        assert 'my-format' in list_exporters()

    def test_export_empty_list(self):
        """Test exporting empty digest list."""
        exporter = get_exporter('my-format')
        result = exporter.export([])

        assert isinstance(result, ExportResult)
        assert result.digest_count == 0

    def test_export_single_digest(self):
        """Test exporting a single digest."""
        digest = create_mock_digest()
        exporter = get_exporter('my-format')
        result = exporter.export([digest])

        assert result.digest_count == 1
        assert 'Test Title' in result.content

    def test_format_name(self):
        """Test get_format_name returns correct value."""
        exporter = get_exporter('my-format')
        assert exporter.get_format_name() == 'my-format'

    def test_content_type(self):
        """Test get_content_type returns correct value."""
        exporter = get_exporter('my-format')
        assert exporter.get_content_type() == 'text/plain'

    def test_file_extension(self):
        """Test get_file_extension returns correct value."""
        exporter = get_exporter('my-format')
        assert exporter.get_file_extension() == 'txt'
```

### 5. Register Your Exporter

Your exporter is **automatically registered** when the module is imported thanks to the `@register_exporter` decorator.

To ensure it's loaded, import it in `factory.py`:

```python
# In factory.py
from reconly_core.exporters import my_format
```

### 6. Use Your Exporter

```python
from reconly_core.exporters import get_exporter

# Get exporter instance
exporter = get_exporter('my-format')

# Export digests
result = exporter.export(digests)
print(result.content)
print(f"Exported {result.digest_count} digests")

# Use in API response
from fastapi.responses import Response
return Response(
    content=result.content,
    media_type=result.content_type,
    headers={"Content-Disposition": f"attachment; filename={result.filename}"}
)
```

## ExportResult Dataclass

The `ExportResult` dataclass contains:

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str \| bytes` | The exported content |
| `filename` | `str` | Suggested filename for downloads |
| `content_type` | `str` | MIME type for HTTP response |
| `digest_count` | `int` | Number of digests exported |

## Binary Formats

For binary formats (ZIP, PDF, etc.), return `bytes` instead of `str`:

```python
def export(self, digests, config=None):
    # Create ZIP archive
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for digest in digests:
            content = self._format_digest(digest)
            filename = f"{digest.id}.md"
            zf.writestr(filename, content)

    return ExportResult(
        content=buffer.getvalue(),  # bytes
        filename='digests.zip',
        content_type='application/zip',
        digest_count=len(digests)
    )
```

## Configuration Options

Accept configuration via the `config` parameter:

```python
def export(self, digests, config=None):
    config = config or {}

    # Config options with defaults
    include_content = config.get('include_content', True)
    date_format = config.get('date_format', '%Y-%m-%d')
    max_summary_length = config.get('max_summary_length', 500)

    # Use in export logic
    ...
```

## Built-in Exporters

Look at existing exporters for examples:

- `json_exporter.py` - JSON with pretty printing
- `csv_exporter.py` - CSV with configurable fields
- `markdown.py` - Markdown with Obsidian YAML frontmatter

## Exporter Architecture

```
┌─────────────────────────────────────────────────┐
│ BaseExporter (Abstract)                         │
│ - export()                                      │
│ - get_format_name()                             │
│ - get_content_type()                            │
│ - get_file_extension()                          │
│ - get_description() [optional]                  │
└─────────────────────────────────────────────────┘
                     ▲
                     │ inherits
        ┌────────────┴────────────┐
        │                         │
┌───────────────┐         ┌───────────────┐
│ @register_exporter('json')  @register_exporter('csv')
│ JSONExporter  │         │ CSVExporter   │
└───────────────┘         └───────────────┘
        │                         │
        └────────────┬────────────┘
                     │ registered in
           ┌─────────────────────┐
           │ _EXPORTER_REGISTRY  │
           │ {                   │
           │   'json': JSONClass │
           │   'csv': CSVClass   │
           │ }                   │
           └─────────────────────┘
                     │
                     │ used by
              ┌──────────────┐
              │ get_exporter │
              └──────────────┘
```

## Configuration Schema (UI Integration)

Exporters can define a configuration schema that enables the UI to dynamically render configuration fields. This allows users to configure exporter settings through the Settings page.

### Adding Config Schema

Override the `get_config_schema()` method to define your exporter's configuration:

```python
from reconly_core.exporters.base import BaseExporter, ExportResult, ConfigSchema, ConfigField

@register_exporter('my-format')
class MyFormatExporter(BaseExporter):
    """Export with configurable options."""

    def get_config_schema(self) -> ConfigSchema:
        return ConfigSchema(
            supports_direct_export=True,  # Can export directly to filesystem
            fields=[
                ConfigField(
                    key='output_path',
                    type='path',
                    label='Output Path',
                    description='Directory where files will be exported',
                    required=True,
                    placeholder='/path/to/output',
                ),
                ConfigField(
                    key='include_frontmatter',
                    type='boolean',
                    label='Include Frontmatter',
                    description='Add YAML frontmatter to exported files',
                    required=False,
                    default=True,
                ),
                ConfigField(
                    key='filename_pattern',
                    type='string',
                    label='Filename Pattern',
                    description='Pattern for generating filenames. Use {title}, {date}, {id}',
                    required=False,
                    placeholder='{date}-{title}',
                    default='{date}-{title}',
                ),
            ],
        )
```

### ConfigField Types

| Type | UI Component | Description |
|------|--------------|-------------|
| `path` | Path input with folder icon | For filesystem paths |
| `boolean` | Toggle switch | For on/off settings |
| `string` | Text input | For general text values |

### ConfigField Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `key` | str | Yes | Unique identifier for the setting |
| `type` | str | Yes | Field type: 'path', 'boolean', 'string' |
| `label` | str | Yes | Human-readable label for UI |
| `description` | str | Yes | Help text explaining the setting |
| `required` | bool | No | Whether the field must have a value |
| `placeholder` | str | No | Placeholder text for input fields |
| `default` | Any | No | Default value when not configured |

### Settings Storage

When users save configuration in the UI, settings are stored with keys in the format:
```
export.{exporter_name}.{field_key}
```

For example:
- `export.obsidian.vault_path`
- `export.obsidian.subfolder`
- `export.my-format.output_path`

### Accessing Configuration

In your `export()` method, access stored settings via the `config` parameter or settings service:

```python
def export(self, digests, config=None):
    config = config or {}

    # Config may come from UI settings or API request
    output_path = config.get('output_path', '/default/path')
    include_frontmatter = config.get('include_frontmatter', True)

    # Your export logic...
```

## Direct Export to Filesystem

Exporters can support exporting directly to a filesystem path (e.g., Obsidian vault, local folder). This enables the "Export to Vault" button in the UI.

### Enabling Direct Export

1. Set `supports_direct_export=True` in your config schema
2. Implement the `export_to_path()` method:

```python
from pathlib import Path
from reconly_core.exporters.base import DirectExportResult

@register_exporter('my-format')
class MyFormatExporter(BaseExporter):
    """Exporter with direct filesystem export support."""

    def get_config_schema(self) -> ConfigSchema:
        return ConfigSchema(
            supports_direct_export=True,
            fields=[
                ConfigField(
                    key='output_path',
                    type='path',
                    label='Output Path',
                    description='Directory where files will be saved',
                    required=True,
                ),
            ],
        )

    def export_to_path(
        self,
        digests: List[Any],
        path: str,
        config: Dict[str, Any] = None
    ) -> DirectExportResult:
        """
        Export digests directly to filesystem.

        Args:
            digests: List of Digest model instances
            path: Target directory path
            config: Optional configuration

        Returns:
            DirectExportResult with success status and file list
        """
        config = config or {}
        target_path = Path(path)
        filenames = []
        errors = []

        # Ensure target directory exists
        target_path.mkdir(parents=True, exist_ok=True)

        for digest in digests:
            try:
                filename = self._generate_filename(digest, config)
                filepath = target_path / filename
                content = self._format_digest(digest, config)

                filepath.write_text(content, encoding='utf-8')
                filenames.append(filename)

            except Exception as e:
                errors.append(f"Failed to export {digest.title}: {str(e)}")

        return DirectExportResult(
            success=len(errors) == 0,
            files_written=len(filenames),
            target_path=str(target_path),
            filenames=filenames,
            errors=errors,
        )

    def _generate_filename(self, digest, config):
        """Generate filename for a digest."""
        pattern = config.get('filename_pattern', '{title}')
        date_str = digest.created_at.strftime('%Y-%m-%d')
        safe_title = self._sanitize_filename(digest.title)

        return pattern.format(
            title=safe_title,
            date=date_str,
            id=digest.id,
        ) + f'.{self.get_file_extension()}'

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:100]  # Limit length
```

### DirectExportResult

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether export completed without errors |
| `files_written` | int | Number of files successfully written |
| `target_path` | str | Actual path where files were written |
| `filenames` | List[str] | List of created filenames |
| `errors` | List[str] | List of error messages (if any) |

## Exporter Activation

Exporters have an activation state that controls whether they appear in feed configuration and can be used for auto-export. This prevents users from selecting unconfigured exporters.

### Activation States

Each exporter has three state fields returned by the API:

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Whether the exporter is currently active |
| `is_configured` | bool | Whether all required config fields have values |
| `can_enable` | bool | Whether the exporter can be toggled on |

### Default Activation Behavior

The activation behavior depends on whether your exporter has required configuration fields:

**Non-configurable exporters** (no required fields in config schema):
- Enabled by default
- `can_enable` is always `true`
- Users can freely toggle on/off
- Examples: JSON, CSV exporters

**Configurable exporters** (one or more required fields):
- Disabled by default
- `can_enable` is `false` until all required fields have values
- Users must complete configuration before enabling
- Examples: Obsidian (requires `vault_path`)

### How Required Fields Affect Activation

When defining your config schema, the `required` property on fields directly impacts activation:

```python
def get_config_schema(self) -> ConfigSchema:
    return ConfigSchema(
        supports_direct_export=True,
        fields=[
            ConfigField(
                key='output_path',
                type='path',
                label='Output Path',
                required=True,  # <-- Exporter disabled until this is set
            ),
            ConfigField(
                key='include_metadata',
                type='boolean',
                label='Include Metadata',
                required=False,  # <-- Does not affect activation
                default=True,
            ),
        ],
    )
```

With this schema:
- The exporter starts disabled (`enabled=false`, `can_enable=false`)
- Once `output_path` is configured, `can_enable` becomes `true`
- User can then toggle `enabled` to `true` via the UI
- `include_metadata` has no effect on `can_enable` since it's optional

### Settings Storage for Activation

Activation state is stored in the settings system:
```
export.{exporter_name}.enabled = true|false
```

For example:
- `export.obsidian.enabled`
- `export.json.enabled`
- `export.my-format.enabled`

### UI Behavior

The UI displays status badges based on activation state:

| State | Badge | When |
|-------|-------|------|
| Active | Green | `enabled=true` and `is_configured=true` |
| Misconfigured | Amber | `enabled=true` but `is_configured=false` |
| Disabled | Gray | `enabled=false` and `is_configured=true` |
| Not Configured | Red | `enabled=false` and `is_configured=false` |

The toggle switch in the exporter card is disabled when `can_enable=false`, with a tooltip explaining that configuration is required.

### Feed Config Modal Filtering

Only enabled exporters (`enabled=true`) appear in the feed configuration modal's auto-export section. This prevents users from selecting exporters that aren't ready for use.

If no exporters are enabled, the UI shows a message directing users to the Export Settings page.

## Example: Obsidian Exporter with Full Configuration

Here's a complete example showing config schema and direct export:

```python
"""Obsidian Markdown exporter with YAML frontmatter."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from reconly_core.exporters.base import (
    BaseExporter, ExportResult, DirectExportResult,
    ConfigSchema, ConfigField
)
from reconly_core.exporters.registry import register_exporter


@register_exporter('obsidian')
class ObsidianExporter(BaseExporter):
    """Export digests as Obsidian-compatible Markdown with YAML frontmatter."""

    def get_format_name(self) -> str:
        return 'obsidian'

    def get_content_type(self) -> str:
        return 'text/markdown'

    def get_file_extension(self) -> str:
        return 'md'

    def get_description(self) -> str:
        return 'Markdown files with YAML frontmatter for Obsidian'

    def get_config_schema(self) -> ConfigSchema:
        return ConfigSchema(
            supports_direct_export=True,
            fields=[
                ConfigField(
                    key='vault_path',
                    type='path',
                    label='Vault Path',
                    description='Path to your Obsidian vault',
                    required=True,
                    placeholder='/Users/you/Documents/ObsidianVault',
                ),
                ConfigField(
                    key='subfolder',
                    type='string',
                    label='Subfolder',
                    description='Subfolder within the vault for digests',
                    required=False,
                    placeholder='Reconly',
                    default='Reconly',
                ),
                ConfigField(
                    key='filename_pattern',
                    type='string',
                    label='Filename Pattern',
                    description='Pattern for filenames. Variables: {title}, {date}, {id}',
                    required=False,
                    placeholder='{date} {title}',
                    default='{date} {title}',
                ),
                ConfigField(
                    key='one_file_per_digest',
                    type='boolean',
                    label='One File Per Digest',
                    description='Create separate files for each digest',
                    required=False,
                    default=True,
                ),
            ],
        )

    def export(self, digests: List[Any], config: Dict[str, Any] = None) -> ExportResult:
        """Export digests as Obsidian Markdown."""
        config = config or {}
        content = self._generate_content(digests, config)

        return ExportResult(
            content=content,
            filename='digests.md',
            content_type=self.get_content_type(),
            digest_count=len(digests),
        )

    def export_to_path(
        self,
        digests: List[Any],
        path: str,
        config: Dict[str, Any] = None
    ) -> DirectExportResult:
        """Export digests directly to Obsidian vault."""
        config = config or {}
        subfolder = config.get('subfolder', 'Reconly')
        target_path = Path(path) / subfolder

        target_path.mkdir(parents=True, exist_ok=True)

        filenames = []
        errors = []

        for digest in digests:
            try:
                filename = self._generate_filename(digest, config)
                filepath = target_path / filename
                content = self._format_single_digest(digest)

                filepath.write_text(content, encoding='utf-8')
                filenames.append(filename)

            except Exception as e:
                errors.append(f"Failed: {digest.title}: {e}")

        return DirectExportResult(
            success=len(errors) == 0,
            files_written=len(filenames),
            target_path=str(target_path),
            filenames=filenames,
            errors=errors,
        )

    def _format_single_digest(self, digest) -> str:
        """Format a single digest with YAML frontmatter."""
        d = digest.to_dict() if hasattr(digest, 'to_dict') else digest

        frontmatter = [
            '---',
            f'title: "{d.get("title", "Untitled")}"',
            f'url: {d.get("url", "")}',
            f'source_type: {d.get("source_type", "unknown")}',
            f'created: {d.get("created_at", datetime.now().isoformat())}',
            f'tags: [reconly]',
            '---',
            '',
        ]

        body = [
            f'# {d.get("title", "Untitled")}',
            '',
            d.get('summary', d.get('content', '')),
            '',
            f'[Original Source]({d.get("url", "")})',
        ]

        return '\n'.join(frontmatter + body)
```

## Best Practices

1. **Use `digest.to_dict()`** to get a serializable representation
2. **Handle empty lists** gracefully
3. **Provide sensible defaults** for config options
4. **Use appropriate MIME types** for HTTP responses
5. **Test with various digest counts** (0, 1, many)
6. **Document config options** in docstrings
7. **Validate paths** before writing files in `export_to_path()`
8. **Sanitize filenames** to remove invalid characters
9. **Handle encoding** properly (use UTF-8)
10. **Return meaningful errors** in DirectExportResult

## Testing Checklist

Before submitting your exporter:

- [ ] All abstract methods implemented
- [ ] Tests for empty list, single digest, multiple digests
- [ ] `pytest tests/core/exporters/test_my_format.py` passes
- [ ] Content type is correct for format
- [ ] File extension matches format
- [ ] Config schema returns valid ConfigSchema (if applicable)
- [ ] Direct export creates files correctly (if `supports_direct_export=True`)
- [ ] Invalid paths handled gracefully in `export_to_path()`
- [ ] Filenames are sanitized to remove invalid characters
- [ ] Activation behavior is correct:
  - [ ] Non-configurable exporters: enabled by default, `can_enable=true`
  - [ ] Configurable exporters: disabled until required fields are set
  - [ ] Toggle correctly enables/disables via settings

## Packaging as an Extension

Want to distribute your exporter as an installable package? See the [Extension Development Guide](./EXTENSION_DEVELOPMENT.md) for full details. Here's a quick overview:

### 1. Create Package Structure

```
reconly-ext-myformat/
├── pyproject.toml
├── README.md
├── src/
│   └── reconly_ext_myformat/
│       ├── __init__.py
│       └── exporter.py
└── tests/
```

### 2. Add Extension Metadata

Add these class attributes to your exporter:

```python
class MyFormatExporter(BaseExporter):
    # Extension metadata
    __extension_name__ = "MyFormat Exporter"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"
    __extension_description__ = "Export digests to MyFormat"
    __extension_homepage__ = "https://github.com/you/reconly-ext-myformat"

    # ... rest of implementation
```

### 3. Configure Entry Points

In `pyproject.toml`:

```toml
[project]
name = "reconly-ext-myformat"
version = "1.0.0"
dependencies = ["reconly-core>=0.5.0"]

[project.entry-points."reconly.exporters"]
myformat = "reconly_ext_myformat:MyFormatExporter"
```

### 4. Install and Test

```bash
pip install -e .
# Restart Reconly - extension appears in Settings > Extensions
```

---

## Questions?

- Check existing exporters in `packages/core/reconly_core/exporters/`
- Review test examples in `tests/core/exporters/`
- See [Extension Development Guide](./EXTENSION_DEVELOPMENT.md) for packaging details
- Open an issue on GitHub if stuck
