"""CSV exporter for digests."""
import csv
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


# Default fields to include in CSV export
DEFAULT_FIELDS = [
    'id', 'title', 'url', 'summary', 'source_type', 'author',
    'published_at', 'created_at', 'provider', 'language', 'tags'
]

# Extended fields including content
EXTENDED_FIELDS = DEFAULT_FIELDS + ['content']


@register_exporter('csv')
class CSVExporter(BaseExporter):
    """Export digests as CSV.

    Exports digests to comma-separated values format with headers.
    Supports direct export to filesystem.
    """

    metadata = ExporterMetadata(
        name='csv',
        display_name='CSV',
        description='Export digests as CSV spreadsheet',
        icon='mdi:file-delimited',
        file_extension='.csv',
        mime_type='text/csv',
        path_setting_key='export_path',
        ui_color='#22A74E',  # Spreadsheet green
    )

    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to CSV format.

        Args:
            digests: List of Digest model instances
            config: Optional config with 'fields' key (list of field names)
                    and 'include_content' key (bool)

        Returns:
            ExportResult with CSV content
        """
        config = config or {}
        include_content = config.get('include_content', False)
        fieldnames = config.get('fields', EXTENDED_FIELDS if include_content else DEFAULT_FIELDS)

        output = StringIO()

        if digests:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for digest in digests:
                digest_dict = digest.to_dict()
                row = {k: digest_dict.get(k, '') for k in fieldnames}
                # Format tags as comma-separated string for CSV
                if 'tags' in row and isinstance(row['tags'], list):
                    row['tags'] = ', '.join(row['tags'])
                writer.writerow(row)

        return ExportResult(
            content=output.getvalue(),
            filename='digests.csv',
            content_type=self.get_content_type(),
            digest_count=len(digests)
        )

    def get_format_name(self) -> str:
        return 'csv'

    def get_content_type(self) -> str:
        return 'text/csv'

    def get_file_extension(self) -> str:
        return 'csv'

    def get_description(self) -> str:
        return 'Comma-separated values with headers'

    def get_config_schema(self) -> ExporterConfigSchema:
        """Return configuration schema for CSV export."""
        return ExporterConfigSchema(
            fields=[
                ConfigField(
                    key="export_path",
                    type="path",
                    label="Export Path",
                    description="Directory to save exported CSV files",
                    default=None,
                    required=True,
                    placeholder="/path/to/export/folder"
                ),
                ConfigField(
                    key="include_content",
                    type="boolean",
                    label="Include Full Content",
                    description="Include full article content column (can make files large)",
                    default=False,
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
        Export digests directly to the filesystem as CSV.

        Args:
            digests: List of Digest model instances
            base_path: Base directory path to write files to
            config: Configuration with include_content, one_file_per_digest

        Returns:
            ExportToPathResult with written files and any errors
        """
        config = config or {}
        include_content = config.get("include_content", False)
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
            fieldnames = EXTENDED_FIELDS if include_content else DEFAULT_FIELDS
            for digest in digests:
                filename = self._generate_filename(digest)
                filepath = base / filename
                # Skip if file already exists
                if filepath.exists():
                    skipped += 1
                    continue
                try:
                    digest_dict = digest.to_dict()
                    row = {k: digest_dict.get(k, '') for k in fieldnames}
                    # Format tags as comma-separated string for CSV
                    if 'tags' in row and isinstance(row['tags'], list):
                        row['tags'] = ', '.join(row['tags'])

                    with open(filepath, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerow(row)

                    written.append(filename)
                except Exception as e:
                    errors.append({"file": filename, "error": str(e)})
        else:
            # Create combined file
            filename = f"digests-{date.today().isoformat()}.csv"
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
        return f"{today}-{title_slug}-{digest_id}.csv"

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
