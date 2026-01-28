"""Plain Markdown exporter for digests.

Exports digests to plain Markdown format without frontmatter,
suitable for general-purpose markdown viewing and sharing.
"""
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


@register_exporter('markdown')
class MarkdownExporter(BaseExporter):
    """Export digests as plain Markdown.

    Exports digests to clean Markdown format without YAML frontmatter.
    Suitable for general-purpose use, sharing, and viewing.
    """

    metadata = ExporterMetadata(
        name='markdown',
        display_name='Markdown',
        description='Export digests as plain Markdown files',
        icon='mdi:language-markdown',
        file_extension='.md',
        mime_type='text/markdown',
        path_setting_key='export_path',
        ui_color='#083FA1',  # Markdown blue
    )

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to plain Markdown format.

        Args:
            digests: List of Digest model instances
            config: Optional config with:
                - 'include_content': Whether to include full content (default: True)

        Returns:
            ExportResult with Markdown content
        """
        config = config or {}
        include_content = config.get('include_content', True)

        output = StringIO()

        for i, digest in enumerate(digests):
            if i > 0:
                output.write("\n---\n\n")
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
        # Title
        output.write(f"# {digest.title or 'Untitled'}\n\n")

        # Metadata as a clean list
        if digest.url:
            output.write(f"**Source:** [{digest.url}]({digest.url})\n")
        if digest.author:
            output.write(f"**Author:** {digest.author}\n")
        if digest.published_at:
            output.write(f"**Published:** {digest.published_at.strftime('%Y-%m-%d %H:%M')}\n")
        if digest.source_type:
            output.write(f"**Type:** {digest.source_type}\n")

        # Tags
        tags_list = [tag.tag.name for tag in digest.tags] if digest.tags else []
        if tags_list:
            output.write(f"**Tags:** {', '.join(tags_list)}\n")

        output.write("\n")

        # Summary
        if digest.summary:
            output.write("## Summary\n\n")
            output.write(f"{digest.summary}\n\n")

        # Full content
        if include_content and digest.content:
            output.write("## Content\n\n")
            output.write(f"{digest.content}\n\n")

    def get_format_name(self) -> str:
        return 'markdown'

    def get_content_type(self) -> str:
        return 'text/markdown'

    def get_file_extension(self) -> str:
        return 'md'

    def get_description(self) -> str:
        return 'Plain Markdown format'

    def get_config_schema(self) -> ExporterConfigSchema:
        """Return configuration schema for Markdown export."""
        return ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="export_path",
                    type="path",
                    label="Export Path",
                    description="Directory to save exported Markdown files",
                    default=None,
                    required=False,
                    placeholder="/path/to/export/folder"
                ),
                ConfigField(
                    key="include_content",
                    type="boolean",
                    label="Include Full Content",
                    description="Include full article content (can be large)",
                    default=True,
                    required=False
                ),
                ConfigField(
                    key="one_file_per_digest",
                    type="boolean",
                    label="One File Per Digest",
                    description="Create separate file per digest (vs combined file)",
                    default=False,
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
        Export digests directly to the filesystem as Markdown.

        Args:
            digests: List of Digest model instances
            base_path: Base directory path to write files to
            config: Configuration with include_content, one_file_per_digest

        Returns:
            ExportToPathResult with written files and any errors
        """
        config = config or {}
        include_content = config.get("include_content", True)
        one_per_file = config.get("one_file_per_digest", False)

        base = Path(base_path)
        if not base.exists():
            return ExportToPathResult(
                success=False,
                files_written=0,
                target_path=str(base),
                filenames=[],
                errors=[{"file": "", "error": f"Base path does not exist: {base_path}"}]
            )

        base.mkdir(parents=True, exist_ok=True)

        written = []
        skipped = 0
        errors = []

        if one_per_file:
            # Create separate file for each digest
            for digest in digests:
                filename = self._generate_filename(digest)
                filepath = base / filename
                # Skip if file already exists
                if filepath.exists():
                    skipped += 1
                    continue
                try:
                    content = self._render_single_digest(digest, include_content)
                    filepath.write_text(content, encoding="utf-8")
                    written.append(filename)
                except Exception as e:
                    errors.append({"file": filename, "error": str(e)})
        else:
            # Create combined file
            filename = f"digests-{date.today().isoformat()}.md"
            filepath = base / filename
            try:
                result = self.export(digests, {"include_content": include_content})
                filepath.write_text(result.content, encoding="utf-8")
                written.append(filename)
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        return ExportToPathResult(
            success=len(errors) == 0,
            files_written=len(written),
            target_path=str(base),
            filenames=written,
            files_skipped=skipped,
            errors=errors
        )

    def _generate_filename(self, digest: Any) -> str:
        """Generate filename for a single digest."""
        today = date.today().isoformat()
        digest_id = getattr(digest, 'id', 'unknown')
        title_slug = self._sanitize_filename(digest.title or "untitled")
        return f"{today}-{title_slug}-{digest_id}.md"

    def _sanitize_filename(self, name: str, max_length: int = 50) -> str:
        """Sanitize a string for use as a filename."""
        import re
        import unicodedata

        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = name.lower().strip()
        name = re.sub(r"\s+", "-", name)
        name = re.sub(r"[^a-z0-9\-]", "", name)
        name = re.sub(r"-+", "-", name)
        name = name.strip("-")

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
            Markdown string
        """
        output = StringIO()
        self._write_digest(output, digest, include_content)
        return output.getvalue()
