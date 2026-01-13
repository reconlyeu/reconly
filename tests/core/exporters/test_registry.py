"""Tests for exporter registry."""
import pytest
from reconly_core.exporters.registry import (
    register_exporter,
    get_exporter_class,
    list_exporters,
    is_exporter_registered,
    _EXPORTER_REGISTRY
)
from reconly_core.exporters.base import (
    BaseExporter,
    ConfigField,
    ExporterConfigSchema,
    ExportResult,
)
from reconly_core.services.settings_registry import SETTINGS_REGISTRY


class TestExporterRegistry:
    """Test cases for exporter registry functionality."""

    def setup_method(self):
        """Store original registry and clear it before each test."""
        self._original_registry = _EXPORTER_REGISTRY.copy()
        self._original_settings = set(SETTINGS_REGISTRY.keys())
        _EXPORTER_REGISTRY.clear()

    def teardown_method(self):
        """Restore original registry after each test."""
        _EXPORTER_REGISTRY.clear()
        _EXPORTER_REGISTRY.update(self._original_registry)
        # Clean up any settings added during tests
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - self._original_settings
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    def test_register_exporter_decorator(self):
        """Test that @register_exporter decorator registers an exporter."""
        @register_exporter('test-format')
        class TestExporter(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult(
                    content='test',
                    filename='test.txt',
                    content_type='text/plain',
                    digest_count=0
                )

            def get_format_name(self):
                return 'test-format'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        assert is_exporter_registered('test-format')
        assert get_exporter_class('test-format') == TestExporter

    def test_register_exporter_appears_in_list(self):
        """Test that registered exporter appears in list_exporters()."""
        @register_exporter('test-format')
        class TestExporter(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult(
                    content='test',
                    filename='test.txt',
                    content_type='text/plain',
                    digest_count=0
                )

            def get_format_name(self):
                return 'test-format'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        formats = list_exporters()
        assert 'test-format' in formats

    def test_get_exporter_class_raises_on_unknown(self):
        """Test that get_exporter_class raises ValueError for unknown format."""
        with pytest.raises(ValueError) as exc_info:
            get_exporter_class('nonexistent-format')

        error_msg = str(exc_info.value)
        assert 'nonexistent-format' in error_msg
        assert 'Available formats' in error_msg
        assert 'ADDING_EXPORTERS.md' in error_msg

    def test_register_non_baseexporter_raises(self):
        """Test that registering a non-BaseExporter class raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            @register_exporter('invalid')
            class NotAnExporter:
                pass

        assert 'must inherit from BaseExporter' in str(exc_info.value)

    def test_register_exporter_override_warns(self, caplog):
        """Test that overriding an exporter logs a warning."""
        @register_exporter('foo')
        class ExporterOne(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('a', 'a.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'foo'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        @register_exporter('foo')
        class ExporterTwo(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('b', 'b.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'foo'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        # Check that warning was logged
        assert any('already registered' in record.message.lower() for record in caplog.records)

        # Check that new exporter replaced the old one
        assert get_exporter_class('foo') == ExporterTwo

    def test_is_exporter_registered(self):
        """Test is_exporter_registered helper function."""
        assert not is_exporter_registered('test-format')

        @register_exporter('test-format')
        class TestExporter(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('', 'test.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'test-format'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        assert is_exporter_registered('test-format')

    def test_list_exporters_empty(self):
        """Test that list_exporters returns empty list when no exporters registered."""
        assert list_exporters() == []

    def test_multiple_exporters_registration(self):
        """Test registering multiple exporters."""
        @register_exporter('format-1')
        class Exporter1(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('', '1.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'format-1'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        @register_exporter('format-2')
        class Exporter2(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('', '2.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'format-2'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

        formats = list_exporters()
        assert len(formats) == 2
        assert 'format-1' in formats
        assert 'format-2' in formats

    def test_register_exporter_auto_registers_settings(self):
        """Test that @register_exporter automatically registers settings from config schema."""
        @register_exporter('auto-settings')
        class AutoSettingsExporter(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('', 'test.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'auto-settings'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

            def get_config_schema(self):
                return ExporterConfigSchema(
                    fields=[
                        ConfigField(
                            key="output_path",
                            type="path",
                            label="Output Path",
                            description="Directory for exported files",
                            default=None,
                            required=True,
                        ),
                        ConfigField(
                            key="include_metadata",
                            type="boolean",
                            label="Include Metadata",
                            description="Include metadata in export",
                            default=True,
                            required=False,
                        ),
                    ],
                    supports_direct_export=True,
                )

        # Verify exporter is registered
        assert is_exporter_registered('auto-settings')

        # Verify settings were auto-registered
        assert "export.auto-settings.enabled" in SETTINGS_REGISTRY
        assert "export.auto-settings.output_path" in SETTINGS_REGISTRY
        assert "export.auto-settings.include_metadata" in SETTINGS_REGISTRY

        # Verify setting properties
        enabled_setting = SETTINGS_REGISTRY["export.auto-settings.enabled"]
        assert enabled_setting.type is bool
        assert enabled_setting.default is False  # Has required field

        path_setting = SETTINGS_REGISTRY["export.auto-settings.output_path"]
        assert path_setting.type is str
        assert path_setting.description == "Directory for exported files"

        metadata_setting = SETTINGS_REGISTRY["export.auto-settings.include_metadata"]
        assert metadata_setting.type is bool
        assert metadata_setting.default is True

    def test_register_exporter_no_settings_for_empty_schema(self):
        """Test that exporter with empty schema doesn't register extra settings."""
        @register_exporter('no-schema')
        class NoSchemaExporter(BaseExporter):
            def export(self, digests, config=None):
                return ExportResult('', 'test.txt', 'text/plain', 0)

            def get_format_name(self):
                return 'no-schema'

            def get_content_type(self):
                return 'text/plain'

            def get_file_extension(self):
                return 'txt'

            # Uses default get_config_schema() which returns empty schema

        # Exporter should be registered
        assert is_exporter_registered('no-schema')

        # No settings should be registered (empty schema has no fields)
        assert "export.no-schema.enabled" not in SETTINGS_REGISTRY
        assert "export.no-schema.output_path" not in SETTINGS_REGISTRY
