"""Markdown exporter for digests (Obsidian-compatible).

Exports digests to Markdown format with YAML frontmatter,
compatible with Obsidian and other Markdown-based tools.
"""
import re
import unicodedata
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from reconly_core.exporters.base import (
    BaseExporter,
    ConfigField,
    ExporterConfigSchema,
    ExportResult,
    ExportToPathResult,
)
from reconly_core.exporters.metadata import ExporterMetadata
from reconly_core.exporters.registry import register_exporter
from reconly_core.exporters.yaml_utils import yaml_escape


@register_exporter('obsidian')
class MarkdownExporter(BaseExporter):
    """Export digests as Markdown with Obsidian frontmatter.

    Exports digests to Markdown format with YAML frontmatter,
    designed for use with Obsidian and other note-taking apps.
    All digests are combined into a single Markdown file.
    """

    metadata = ExporterMetadata(
        name='obsidian',
        display_name='Obsidian',
        description='Export digests to Obsidian vault with frontmatter',
        icon='simple-icons:obsidian',
        file_extension='.md',
        mime_type='text/markdown',
        path_setting_key='vault_path',  # Different setting key for Obsidian
        ui_color='#7C3AED',  # Obsidian purple
    )

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to Obsidian-compatible Markdown format.

        Args:
            digests: List of Digest model instances
            config: Optional config with:
                - 'include_content': Whether to include full content (default: True)
                - 'separate_files': If True, would create separate files (not implemented)

        Returns:
            ExportResult with Markdown content
        """
        config = config or {}
        include_content = config.get('include_content', True)

        output = StringIO()

        for digest in digests:
            self._write_digest(output, digest, include_content)

        return ExportResult(
            content=output.getvalue(),
            filename='digests.md',
            content_type=self.get_content_type(),
            digest_count=len(digests)
        )

    def _write_digest(
        self,
        output: StringIO,
        digest: Any,
        include_content: bool
    ) -> None:
        """Write a single digest to the output stream."""
        # YAML frontmatter
        output.write("---\n")
        output.write(f"title: {yaml_escape(digest.title or 'Untitled')}\n")
        output.write(f"url: {digest.url}\n")
        output.write(f"source_type: {digest.source_type or 'unknown'}\n")

        if digest.author:
            output.write(f"author: {yaml_escape(digest.author)}\n")
        if digest.published_at:
            output.write(f"published: {digest.published_at.isoformat()}\n")

        output.write(f"created: {digest.created_at.isoformat() if digest.created_at else ''}\n")
        output.write(f"provider: {digest.provider or ''}\n")
        output.write(f"language: {digest.language or ''}\n")

        # Add tags if available (YAML array format for Obsidian)
        tags_list = [tag.tag.name for tag in digest.tags] if digest.tags else []
        if tags_list:
            # Format as YAML array: tags: [tag1, tag2]
            escaped_tags = [yaml_escape(tag) for tag in tags_list]
            output.write(f"tags: [{', '.join(escaped_tags)}]\n")

        output.write("---\n\n")

        # Content
        output.write(f"# {digest.title or 'Untitled'}\n\n")

        if digest.summary:
            output.write("## Summary\n\n")
            output.write(f"{digest.summary}\n\n")

        if include_content and digest.content:
            output.write("## Full Content\n\n")
            output.write(f"{digest.content}\n\n")

        output.write("---\n\n")

    def get_format_name(self) -> str:
        return 'obsidian'

    def get_content_type(self) -> str:
        return 'text/markdown'

    def get_file_extension(self) -> str:
        return 'md'

    def get_description(self) -> str:
        return 'Markdown with Obsidian YAML frontmatter'

    def get_config_schema(self) -> ExporterConfigSchema:
        """Return configuration schema for Obsidian export."""
        return ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="vault_path",
                    type="path",
                    label="Vault Path",
                    description="Path to your Obsidian vault",
                    default=None,
                    required=True,
                    placeholder="/path/to/obsidian/vault"
                ),
                ConfigField(
                    key="subfolder",
                    type="string",
                    label="Subfolder",
                    description="Optional subfolder within vault for exported digests",
                    default="",
                    required=False,
                    placeholder="Digests"
                ),
                ConfigField(
                    key="filename_pattern",
                    type="string",
                    label="Filename Pattern",
                    description="Pattern for filenames: {date}, {title}, {source}",
                    default="{date}-{title}",
                    required=False,
                    placeholder="{date}-{title}"
                ),
                ConfigField(
                    key="one_file_per_digest",
                    type="boolean",
                    label="One File Per Digest",
                    description="Create separate file per digest (vs combined file)",
                    default=True,
                    required=False
                ),
            ],
            supports_direct_export=True
        )

    def export_to_path(
        self,
        digests: List[Any],
        base_path: str,
        config: Optional[Dict[str, Any]] = None
    ) -> ExportToPathResult:
        """
        Export digests directly to the filesystem (Obsidian vault).

        Args:
            digests: List of Digest model instances
            base_path: Base directory path (vault path)
            config: Configuration with subfolder, filename_pattern, one_file_per_digest

        Returns:
            ExportToPathResult with written files and any errors
        """
        config = config or {}
        subfolder = config.get("subfolder", "")
        pattern = config.get("filename_pattern") or "{date}-{title}"
        # Handle None explicitly - .get() returns None if key exists with None value
        one_per_file = config.get("one_file_per_digest")
        if one_per_file is None:
            one_per_file = True
        include_content = config.get("include_content")
        if include_content is None:
            include_content = True

        # Determine target directory
        base = Path(base_path)
        if not base.exists():
            return ExportToPathResult(
                success=False,
                files_written=0,
                target_path=str(base),
                filenames=[],
                errors=[{"file": "", "error": f"Base path does not exist: {base_path}"}]
            )

        target_dir = base / subfolder if subfolder else base
        target_dir.mkdir(parents=True, exist_ok=True)

        written = []
        skipped = 0
        errors = []

        if one_per_file:
            # Create separate file for each digest
            for digest in digests:
                filename = self._generate_filename(digest, pattern)
                filepath = target_dir / filename
                # Skip if file already exists
                if filepath.exists():
                    skipped += 1
                    continue
                try:
                    content = self._render_single_digest(digest, include_content)
                    filepath.write_text(content, encoding="utf-8")
                    written.append(filepath.name)
                except Exception as e:
                    errors.append({"file": filename, "error": str(e)})
        else:
            # Create combined file
            filename = f"digests-{date.today().isoformat()}.md"
            filepath = target_dir / filename
            try:
                result = self.export(digests, {"include_content": include_content})
                filepath.write_text(result.content, encoding="utf-8")
                written.append(filename)
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return ExportToPathResult(
            success=len(errors) == 0,
            files_written=len(written),
            target_path=str(target_dir),
            filenames=written,
            files_skipped=skipped,
            errors=errors
        )

    def _generate_filename(self, digest: Any, pattern: str) -> str:
        """
        Generate filename from pattern and digest data.

        Supported placeholders:
        - {date}: Today's date (YYYY-MM-DD)
        - {title}: Sanitized digest title
        - {source}: Source type (rss, youtube, etc.)

        Args:
            digest: Digest model instance
            pattern: Filename pattern with placeholders

        Returns:
            Sanitized filename with .md extension
        """
        today = date.today().isoformat()
        title = self._sanitize_filename(digest.title or "untitled")
        source = digest.source_type or "unknown"

        filename = pattern.format(
            date=today,
            title=title,
            source=source
        )

        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"

        return filename

    def _sanitize_filename(self, name: str, max_length: int = 100) -> str:
        """
        Sanitize a string for use as a filename.

        - Normalizes unicode characters
        - Replaces spaces with hyphens
        - Removes special characters
        - Converts to lowercase
        - Truncates to max_length

        Args:
            name: Original string
            max_length: Maximum filename length (default 100)

        Returns:
            Sanitized filename-safe string
        """
        # Normalize unicode
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")

        # Convert to lowercase and replace spaces
        name = name.lower().strip()
        name = re.sub(r"\s+", "-", name)

        # Remove special characters (keep alphanumeric and hyphens)
        name = re.sub(r"[^a-z0-9\-]", "", name)

        # Remove multiple consecutive hyphens
        name = re.sub(r"-+", "-", name)

        # Remove leading/trailing hyphens
        name = name.strip("-")

        # Truncate
        if len(name) > max_length:
            name = name[:max_length].rstrip("-")

        return name or "untitled"

    def _render_single_digest(self, digest: Any, include_content: bool = True) -> str:
        """
        Render a single digest to markdown string.

        Args:
            digest: Digest model instance
            include_content: Whether to include full content

        Returns:
            Markdown string with frontmatter
        """
        output = StringIO()
        self._write_digest(output, digest, include_content)
        return output.getvalue()
