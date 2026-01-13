"""Tests for built-in exporters."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime

from reconly_core.exporters import get_exporter, list_exporters
from reconly_core.exporters.base import (
    ExportResult,
    ConfigField,
    ExporterConfigSchema,
    ExportToPathResult,
)


def create_mock_digest(
    id=1,
    title="Test Article",
    url="https://example.com/article",
    summary="This is a test summary.",
    content="Full content here.",
    source_type="rss",
    author="Test Author",
    published_at=None,
    created_at=None,
    provider="test-provider",
    language="en",
    tags=None
):
    """Create a mock digest object for testing."""
    digest = MagicMock()
    digest.id = id
    digest.title = title
    digest.url = url
    digest.summary = summary
    digest.content = content
    digest.source_type = source_type
    digest.author = author
    digest.published_at = published_at or datetime(2024, 1, 15, 10, 30)
    digest.created_at = created_at or datetime(2024, 1, 15, 12, 0)
    digest.provider = provider
    digest.language = language
    digest.tags = tags or []

    digest.to_dict.return_value = {
        'id': id,
        'title': title,
        'url': url,
        'summary': summary,
        'content': content,
        'source_type': source_type,
        'author': author,
        'published_at': digest.published_at.isoformat() if digest.published_at else None,
        'created_at': digest.created_at.isoformat() if digest.created_at else None,
        'provider': provider,
        'language': language,
    }

    return digest


class TestBuiltInExportersRegistered:
    """Test that built-in exporters are properly registered."""

    def test_json_exporter_registered(self):
        """Test that JSON exporter is registered."""
        assert 'json' in list_exporters()

    def test_csv_exporter_registered(self):
        """Test that CSV exporter is registered."""
        assert 'csv' in list_exporters()

    def test_obsidian_exporter_registered(self):
        """Test that Obsidian/Markdown exporter is registered."""
        assert 'obsidian' in list_exporters()


class TestJSONExporter:
    """Tests for JSONExporter."""

    def test_export_empty_list(self):
        """Test exporting empty digest list."""
        exporter = get_exporter('json')
        result = exporter.export([])

        assert isinstance(result, ExportResult)
        assert result.content == '[]'
        assert result.filename == 'digests.json'
        assert result.content_type == 'application/json'
        assert result.digest_count == 0

    def test_export_single_digest(self):
        """Test exporting a single digest."""
        digest = create_mock_digest()
        exporter = get_exporter('json')
        result = exporter.export([digest])

        assert result.digest_count == 1
        assert result.content_type == 'application/json'

        # Verify JSON is valid
        parsed = json.loads(result.content)
        assert len(parsed) == 1
        assert parsed[0]['title'] == 'Test Article'

    def test_export_multiple_digests(self):
        """Test exporting multiple digests."""
        digests = [
            create_mock_digest(id=1, title="Article 1"),
            create_mock_digest(id=2, title="Article 2"),
            create_mock_digest(id=3, title="Article 3"),
        ]
        exporter = get_exporter('json')
        result = exporter.export(digests)

        assert result.digest_count == 3
        parsed = json.loads(result.content)
        assert len(parsed) == 3

    def test_format_name(self):
        """Test get_format_name returns correct value."""
        exporter = get_exporter('json')
        assert exporter.get_format_name() == 'json'

    def test_content_type(self):
        """Test get_content_type returns correct value."""
        exporter = get_exporter('json')
        assert exporter.get_content_type() == 'application/json'

    def test_file_extension(self):
        """Test get_file_extension returns correct value."""
        exporter = get_exporter('json')
        assert exporter.get_file_extension() == 'json'


class TestCSVExporter:
    """Tests for CSVExporter."""

    def test_export_empty_list(self):
        """Test exporting empty digest list."""
        exporter = get_exporter('csv')
        result = exporter.export([])

        assert isinstance(result, ExportResult)
        assert result.content == ''
        assert result.filename == 'digests.csv'
        assert result.content_type == 'text/csv'
        assert result.digest_count == 0

    def test_export_single_digest(self):
        """Test exporting a single digest."""
        digest = create_mock_digest()
        exporter = get_exporter('csv')
        result = exporter.export([digest])

        assert result.digest_count == 1
        assert result.content_type == 'text/csv'

        # Verify CSV structure
        lines = result.content.strip().split('\n')
        assert len(lines) == 2  # Header + 1 data row
        assert 'title' in lines[0].lower()
        assert 'url' in lines[0].lower()

    def test_export_has_expected_headers(self):
        """Test that CSV has expected headers."""
        digest = create_mock_digest()
        exporter = get_exporter('csv')
        result = exporter.export([digest])

        header_line = result.content.split('\n')[0]
        expected_headers = ['id', 'title', 'url', 'summary', 'source_type']
        for header in expected_headers:
            assert header in header_line

    def test_format_name(self):
        """Test get_format_name returns correct value."""
        exporter = get_exporter('csv')
        assert exporter.get_format_name() == 'csv'

    def test_content_type(self):
        """Test get_content_type returns correct value."""
        exporter = get_exporter('csv')
        assert exporter.get_content_type() == 'text/csv'

    def test_file_extension(self):
        """Test get_file_extension returns correct value."""
        exporter = get_exporter('csv')
        assert exporter.get_file_extension() == 'csv'


class TestMarkdownExporter:
    """Tests for MarkdownExporter (Obsidian format)."""

    def test_export_empty_list(self):
        """Test exporting empty digest list."""
        exporter = get_exporter('obsidian')
        result = exporter.export([])

        assert isinstance(result, ExportResult)
        assert result.content == ''
        assert result.filename == 'digests.md'
        assert result.content_type == 'text/markdown'
        assert result.digest_count == 0

    def test_export_single_digest(self):
        """Test exporting a single digest."""
        digest = create_mock_digest()
        exporter = get_exporter('obsidian')
        result = exporter.export([digest])

        assert result.digest_count == 1
        assert result.content_type == 'text/markdown'

        # Verify frontmatter structure
        assert result.content.startswith('---\n')
        assert 'title: Test Article' in result.content
        assert 'url: https://example.com/article' in result.content

    def test_export_has_frontmatter(self):
        """Test that markdown has YAML frontmatter."""
        digest = create_mock_digest()
        exporter = get_exporter('obsidian')
        result = exporter.export([digest])

        # YAML frontmatter should be between --- markers
        parts = result.content.split('---')
        assert len(parts) >= 3  # Before, frontmatter, after

    def test_export_has_summary_section(self):
        """Test that markdown has summary section."""
        digest = create_mock_digest(summary="Test summary content")
        exporter = get_exporter('obsidian')
        result = exporter.export([digest])

        assert '## Summary' in result.content
        assert 'Test summary content' in result.content

    def test_export_has_content_section(self):
        """Test that markdown has full content section."""
        digest = create_mock_digest(content="Full content text here")
        exporter = get_exporter('obsidian')
        result = exporter.export([digest])

        assert '## Full Content' in result.content
        assert 'Full content text here' in result.content

    def test_format_name(self):
        """Test get_format_name returns correct value."""
        exporter = get_exporter('obsidian')
        assert exporter.get_format_name() == 'obsidian'

    def test_content_type(self):
        """Test get_content_type returns correct value."""
        exporter = get_exporter('obsidian')
        assert exporter.get_content_type() == 'text/markdown'

    def test_file_extension(self):
        """Test get_file_extension returns correct value."""
        exporter = get_exporter('obsidian')
        assert exporter.get_file_extension() == 'md'


class TestExporterFactory:
    """Tests for exporter factory functions."""

    def test_get_exporter_returns_instance(self):
        """Test that get_exporter returns an exporter instance."""
        exporter = get_exporter('json')
        assert hasattr(exporter, 'export')
        assert hasattr(exporter, 'get_format_name')

    def test_get_exporter_unknown_format_raises(self):
        """Test that get_exporter raises for unknown format."""
        with pytest.raises(ValueError) as exc_info:
            get_exporter('unknown-format')

        assert 'unknown-format' in str(exc_info.value).lower()

    def test_list_exporters_returns_all_formats(self):
        """Test that list_exporters returns all registered formats."""
        formats = list_exporters()

        assert isinstance(formats, list)
        assert 'json' in formats
        assert 'csv' in formats
        assert 'obsidian' in formats


class TestConfigSchemaDataclasses:
    """Tests for config schema dataclasses."""

    def test_config_field_creation(self):
        """Test ConfigField dataclass creation with all fields."""
        field = ConfigField(
            key="vault_path",
            type="path",
            label="Vault Path",
            description="Path to your Obsidian vault",
            default="/default/path",
            required=True,
            placeholder="/path/to/vault"
        )

        assert field.key == "vault_path"
        assert field.type == "path"
        assert field.label == "Vault Path"
        assert field.description == "Path to your Obsidian vault"
        assert field.default == "/default/path"
        assert field.required is True
        assert field.placeholder == "/path/to/vault"

    def test_config_field_defaults(self):
        """Test ConfigField uses correct defaults."""
        field = ConfigField(
            key="test",
            type="string",
            label="Test",
            description="Test field"
        )

        assert field.default is None
        assert field.required is False
        assert field.placeholder == ""

    def test_exporter_config_schema_creation(self):
        """Test ExporterConfigSchema dataclass creation."""
        fields = [
            ConfigField(key="path", type="path", label="Path", description="The path"),
            ConfigField(key="enabled", type="boolean", label="Enabled", description="Is enabled"),
        ]
        schema = ExporterConfigSchema(
            fields=fields,
            supports_direct_export=True
        )

        assert len(schema.fields) == 2
        assert schema.supports_direct_export is True
        assert schema.fields[0].key == "path"
        assert schema.fields[1].key == "enabled"

    def test_exporter_config_schema_defaults(self):
        """Test ExporterConfigSchema uses correct defaults."""
        schema = ExporterConfigSchema()

        assert schema.fields == []
        assert schema.supports_direct_export is False

    def test_export_to_path_result_creation(self):
        """Test ExportToPathResult dataclass creation."""
        result = ExportToPathResult(
            success=True,
            files_written=5,
            target_path="/path/to/vault",
            filenames=["file1.md", "file2.md"],
            errors=[]
        )

        assert result.success is True
        assert result.files_written == 5
        assert result.target_path == "/path/to/vault"
        assert result.filenames == ["file1.md", "file2.md"]
        assert result.errors == []

    def test_export_to_path_result_with_errors(self):
        """Test ExportToPathResult with errors."""
        result = ExportToPathResult(
            success=False,
            files_written=2,
            target_path="/path/to/vault",
            filenames=["file1.md", "file2.md"],
            errors=[{"file": "file3.md", "error": "Permission denied"}]
        )

        assert result.success is False
        assert result.files_written == 2
        assert len(result.errors) == 1
        assert result.errors[0]["file"] == "file3.md"

    def test_export_to_path_result_defaults(self):
        """Test ExportToPathResult uses correct defaults."""
        result = ExportToPathResult(
            success=True,
            files_written=0,
            target_path="/path"
        )

        assert result.filenames == []
        assert result.errors == []


class TestBaseExporterConfigMethods:
    """Tests for BaseExporter config schema methods."""

    def test_json_exporter_has_config_schema(self):
        """Test that JSON exporter returns config schema with fields."""
        exporter = get_exporter('json')
        schema = exporter.get_config_schema()

        assert isinstance(schema, ExporterConfigSchema)
        assert len(schema.fields) == 3
        assert schema.supports_direct_export is True

        field_keys = [f.key for f in schema.fields]
        assert "export_path" in field_keys
        assert "include_content" in field_keys
        assert "one_file_per_digest" in field_keys

    def test_csv_exporter_has_config_schema(self):
        """Test that CSV exporter returns config schema with fields."""
        exporter = get_exporter('csv')
        schema = exporter.get_config_schema()

        assert isinstance(schema, ExporterConfigSchema)
        assert len(schema.fields) == 3
        assert schema.supports_direct_export is True

        field_keys = [f.key for f in schema.fields]
        assert "export_path" in field_keys
        assert "include_content" in field_keys
        assert "one_file_per_digest" in field_keys

    def test_all_exporters_support_direct_export(self):
        """Test that all exporters support direct file export."""
        for format_name in ['json', 'csv', 'obsidian']:
            exporter = get_exporter(format_name)
            schema = exporter.get_config_schema()
            assert schema.supports_direct_export is True, f"{format_name} should support direct export"


class TestObsidianExporterConfigSchema:
    """Tests for Obsidian exporter configuration schema."""

    def test_obsidian_has_config_schema(self):
        """Test that Obsidian exporter returns config schema."""
        exporter = get_exporter('obsidian')
        schema = exporter.get_config_schema()

        assert isinstance(schema, ExporterConfigSchema)
        assert schema.supports_direct_export is True
        assert len(schema.fields) == 4

    def test_obsidian_config_fields(self):
        """Test Obsidian config schema has expected fields."""
        exporter = get_exporter('obsidian')
        schema = exporter.get_config_schema()

        field_keys = [f.key for f in schema.fields]
        assert "vault_path" in field_keys
        assert "subfolder" in field_keys
        assert "filename_pattern" in field_keys
        assert "one_file_per_digest" in field_keys

    def test_vault_path_field_properties(self):
        """Test vault_path field has correct properties."""
        exporter = get_exporter('obsidian')
        schema = exporter.get_config_schema()

        vault_field = next(f for f in schema.fields if f.key == "vault_path")
        assert vault_field.type == "path"
        assert vault_field.required is True
        assert vault_field.label == "Vault Path"

    def test_subfolder_field_default(self):
        """Test subfolder field has no default (user chooses)."""
        exporter = get_exporter('obsidian')
        schema = exporter.get_config_schema()

        subfolder_field = next(f for f in schema.fields if f.key == "subfolder")
        assert subfolder_field.default == ""
        assert subfolder_field.required is False


class TestObsidianFilenameGeneration:
    """Tests for Obsidian filename generation and sanitization."""

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        exporter = get_exporter('obsidian')

        assert exporter._sanitize_filename("Hello World") == "hello-world"
        assert exporter._sanitize_filename("Test Article!") == "test-article"
        assert exporter._sanitize_filename("A/B/C") == "abc"

    def test_sanitize_filename_special_chars(self):
        """Test sanitization removes special characters."""
        exporter = get_exporter('obsidian')

        result = exporter._sanitize_filename("Test: A 'Special' Article?")
        assert ":" not in result
        assert "'" not in result
        assert "?" not in result
        assert result == "test-a-special-article"

    def test_sanitize_filename_unicode(self):
        """Test sanitization handles unicode characters."""
        exporter = get_exporter('obsidian')

        # German umlauts
        assert exporter._sanitize_filename("Über") == "uber"
        # Accented characters
        assert exporter._sanitize_filename("café") == "cafe"

    def test_sanitize_filename_max_length(self):
        """Test sanitization respects max length."""
        exporter = get_exporter('obsidian')

        long_name = "a" * 200
        result = exporter._sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_sanitize_filename_empty(self):
        """Test sanitization returns 'untitled' for empty input."""
        exporter = get_exporter('obsidian')

        assert exporter._sanitize_filename("") == "untitled"
        assert exporter._sanitize_filename("   ") == "untitled"
        assert exporter._sanitize_filename("!!!") == "untitled"

    def test_generate_filename_with_pattern(self):
        """Test filename generation with pattern."""
        exporter = get_exporter('obsidian')
        digest = create_mock_digest(title="Test Article", source_type="rss")

        filename = exporter._generate_filename(digest, "{title}")
        assert filename == "test-article.md"

    def test_generate_filename_with_date(self):
        """Test filename includes date placeholder."""
        exporter = get_exporter('obsidian')
        digest = create_mock_digest(title="Test")

        filename = exporter._generate_filename(digest, "{date}-{title}")
        # Should start with date in YYYY-MM-DD format
        assert filename.startswith("20")
        assert "-test.md" in filename

    def test_generate_filename_with_source(self):
        """Test filename includes source placeholder."""
        exporter = get_exporter('obsidian')
        digest = create_mock_digest(title="Test", source_type="youtube")

        filename = exporter._generate_filename(digest, "{source}-{title}")
        assert filename == "youtube-test.md"


class TestObsidianExportToPath:
    """Integration tests for Obsidian export_to_path."""

    def test_export_to_path_single_digest(self):
        """Test exporting single digest to path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')
            digest = create_mock_digest(title="Test Article")

            result = exporter.export_to_path(
                [digest],
                tmpdir,
                {"subfolder": "Notes", "one_file_per_digest": True}
            )

            assert result.success is True
            assert result.files_written == 1
            assert len(result.filenames) == 1
            assert result.errors == []

            # Check file exists
            notes_dir = Path(tmpdir) / "Notes"
            assert notes_dir.exists()
            files = list(notes_dir.glob("*.md"))
            assert len(files) == 1

    def test_export_to_path_multiple_digests(self):
        """Test exporting multiple digests to path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')
            digests = [
                create_mock_digest(id=1, title="Article One"),
                create_mock_digest(id=2, title="Article Two"),
                create_mock_digest(id=3, title="Article Three"),
            ]

            result = exporter.export_to_path(
                digests,
                tmpdir,
                {"subfolder": "Digests", "one_file_per_digest": True}
            )

            assert result.success is True
            assert result.files_written == 3
            assert len(result.filenames) == 3

    def test_export_to_path_combined_file(self):
        """Test exporting to combined file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')
            digests = [
                create_mock_digest(id=1, title="Article One"),
                create_mock_digest(id=2, title="Article Two"),
            ]

            result = exporter.export_to_path(
                digests,
                tmpdir,
                {"subfolder": "", "one_file_per_digest": False}
            )

            assert result.success is True
            assert result.files_written == 1
            assert "digests-" in result.filenames[0]

    def test_export_to_path_creates_subfolder(self):
        """Test that subfolder is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')
            digest = create_mock_digest()

            result = exporter.export_to_path(
                [digest],
                tmpdir,
                {"subfolder": "Deep/Nested/Folder"}
            )

            assert result.success is True
            nested_dir = Path(tmpdir) / "Deep" / "Nested" / "Folder"
            assert nested_dir.exists()

    def test_export_to_path_invalid_base_path(self):
        """Test export fails gracefully for invalid path."""
        exporter = get_exporter('obsidian')
        digest = create_mock_digest()

        result = exporter.export_to_path(
            [digest],
            "/nonexistent/path/that/does/not/exist",
            {}
        )

        assert result.success is False
        assert result.files_written == 0
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]["error"]

    def test_export_to_path_filename_conflict(self):
        """Test filename conflict skips duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')

            # Create two digests with same title
            digests = [
                create_mock_digest(id=1, title="Same Title"),
                create_mock_digest(id=2, title="Same Title"),
            ]

            result = exporter.export_to_path(
                digests,
                tmpdir,
                {"subfolder": "", "filename_pattern": "{title}"}
            )

            assert result.success is True
            assert result.files_written == 1
            assert result.files_skipped == 1
            # Only first file should be written, duplicate skipped
            assert "same-title.md" in result.filenames

    def test_export_to_path_file_content(self):
        """Test exported file has correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = get_exporter('obsidian')
            digest = create_mock_digest(
                title="Test Article",
                summary="Test summary content",
                url="https://example.com"
            )

            result = exporter.export_to_path(
                [digest],
                tmpdir,
                {"subfolder": ""}
            )

            assert result.success is True

            # Read the file
            filepath = Path(tmpdir) / result.filenames[0]
            content = filepath.read_text()

            # Check frontmatter
            assert "---" in content
            assert "title: Test Article" in content
            assert "url: https://example.com" in content

            # Check content sections
            assert "## Summary" in content
            assert "Test summary content" in content
