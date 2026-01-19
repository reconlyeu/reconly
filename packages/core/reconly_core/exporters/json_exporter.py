"""JSON exporter for digests."""
import json
from datetime import date
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


@register_exporter('json')
class JSONExporter(BaseExporter):
    """Export digests as JSON.

    Exports digests to a JSON array format with pretty printing.
    Supports direct export to filesystem.
    """

    metadata = ExporterMetadata(
        name='json',
        display_name='JSON',
        description='Export digests as JSON files',
        icon='mdi:code-json',
        file_extension='.json',
        mime_type='application/json',
        path_setting_key='export_path',
        ui_color='#F7DF1E',  # JSON yellow
    )

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to JSON format.

        Args:
            digests: List of Digest model instances
            config: Optional config with 'indent' key (default: 2)

        Returns:
            ExportResult with JSON content
        """
        config = config or {}
        indent = config.get('indent', 2)
        include_content = config.get('include_content', True)

        digest_dicts = []
        for digest in digests:
            d = digest.to_dict()
            if not include_content:
                d.pop('content', None)
            digest_dicts.append(d)

        content = json.dumps(digest_dicts, indent=indent, ensure_ascii=False)

        return ExportResult(
            content=content,
            filename='digests.json',
            content_type=self.get_content_type(),
            digest_count=len(digests)
        )

    def get_format_name(self) -> str:
        return 'json'

    def get_content_type(self) -> str:
        return 'application/json'

    def get_file_extension(self) -> str:
        return 'json'

    def get_description(self) -> str:
        return 'JSON format with pretty printing'

    def get_config_schema(self) -> ExporterConfigSchema:
        """Return configuration schema for JSON export."""
        return ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="export_path",
                    type="path",
                    label="Export Path",
                    description="Directory to save exported JSON files",
                    default=None,
                    required=True,
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
        Export digests directly to the filesystem as JSON.

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
        indent = config.get("indent", 2)

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
                    d = digest.to_dict()
                    if not include_content:
                        d.pop('content', None)
                    content = json.dumps(d, indent=indent, ensure_ascii=False)
                    filepath.write_text(content, encoding="utf-8")
                    written.append(filename)
                except Exception as e:
                    errors.append({"file": filename, "error": str(e)})
        else:
            # Create combined file
            filename = f"digests-{date.today().isoformat()}.json"
            filepath = base / filename
            try:
                result = self.export(digests, {"include_content": include_content, "indent": indent})
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
        # Use digest ID for uniqueness
        digest_id = getattr(digest, 'id', 'unknown')
        title_slug = self._sanitize_filename(digest.title or "untitled")
        return f"{today}-{title_slug}-{digest_id}.json"

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
