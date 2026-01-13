"""Tests for extension loader functionality."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from reconly_core.extensions.loader import (
    parse_version,
    validate_extension_compatibility,
    extract_extension_metadata,
    get_reconly_version,
    ExtensionLoader,
    ENTRY_POINT_GROUPS,
)
from reconly_core.extensions.types import (
    ExtensionType,
    ExtensionMetadata,
    LoadedExtension,
)
from reconly_core.exporters.base import BaseExporter, ExportResult


class TestParseVersion:
    """Tests for parse_version function."""

    def test_simple_version(self):
        """Test parsing simple version string."""
        assert parse_version("1.0.0") == (1, 0, 0)

    def test_two_part_version(self):
        """Test parsing two-part version string."""
        assert parse_version("1.0") == (1, 0)

    def test_single_part_version(self):
        """Test parsing single-part version string."""
        assert parse_version("1") == (1,)

    def test_version_with_prerelease(self):
        """Test parsing version with pre-release suffix."""
        assert parse_version("1.0.0-beta") == (1, 0, 0)
        assert parse_version("2.1.0-alpha.1") == (2, 1, 0)

    def test_version_with_build_metadata(self):
        """Test parsing version with build metadata."""
        assert parse_version("1.0.0+build123") == (1, 0, 0)

    def test_version_with_both_suffixes(self):
        """Test parsing version with both pre-release and build."""
        assert parse_version("1.0.0-beta+build") == (1, 0, 0)

    def test_invalid_version(self):
        """Test parsing invalid version string returns zeros."""
        assert parse_version("invalid") == (0, 0, 0)
        assert parse_version("a.b.c") == (0, 0, 0)

    def test_empty_version(self):
        """Test parsing empty version string."""
        assert parse_version("") == (0, 0, 0)


class TestValidateExtensionCompatibility:
    """Tests for validate_extension_compatibility function."""

    def test_compatible_same_version(self):
        """Test extension is compatible when versions match."""
        assert validate_extension_compatibility("1.0.0", "1.0.0") is True

    def test_compatible_higher_version(self):
        """Test extension is compatible when current version is higher."""
        assert validate_extension_compatibility("1.0.0", "2.0.0") is True
        assert validate_extension_compatibility("1.0.0", "1.1.0") is True
        assert validate_extension_compatibility("1.0.0", "1.0.1") is True

    def test_incompatible_lower_version(self):
        """Test extension is incompatible when current version is lower."""
        assert validate_extension_compatibility("2.0.0", "1.0.0") is False
        assert validate_extension_compatibility("1.1.0", "1.0.0") is False
        assert validate_extension_compatibility("1.0.1", "1.0.0") is False

    def test_compatible_with_prerelease(self):
        """Test compatibility check with pre-release versions."""
        # Pre-release suffix is stripped, so 1.0.0-beta compares as 1.0.0
        assert validate_extension_compatibility("1.0.0-beta", "1.0.0") is True

    def test_uses_current_version_when_not_provided(self):
        """Test that current_version defaults to get_reconly_version()."""
        # Should not raise and should return a boolean
        result = validate_extension_compatibility("0.0.1")
        assert isinstance(result, bool)


class TestExtractExtensionMetadata:
    """Tests for extract_extension_metadata function."""

    def test_extracts_all_attributes(self):
        """Test extraction of all extension metadata attributes."""
        class TestExtension:
            __extension_name__ = "Test Extension"
            __extension_version__ = "1.2.3"
            __extension_author__ = "Test Author"
            __extension_min_reconly__ = "0.5.0"
            __extension_description__ = "A test extension"
            __extension_homepage__ = "https://example.com"

        metadata = extract_extension_metadata(
            TestExtension,
            ExtensionType.EXPORTER,
            "test"
        )

        assert metadata.name == "Test Extension"
        assert metadata.version == "1.2.3"
        assert metadata.author == "Test Author"
        assert metadata.min_reconly == "0.5.0"
        assert metadata.description == "A test extension"
        assert metadata.homepage == "https://example.com"
        assert metadata.extension_type == ExtensionType.EXPORTER
        assert metadata.registry_name == "test"

    def test_uses_defaults_for_missing_attributes(self):
        """Test that missing attributes get default values."""
        class MinimalExtension:
            pass

        metadata = extract_extension_metadata(
            MinimalExtension,
            ExtensionType.FETCHER,
            "minimal"
        )

        assert metadata.name == "MinimalExtension"  # Falls back to class name
        assert metadata.version == "0.0.0"
        assert metadata.author == "Unknown"
        assert metadata.min_reconly == "0.0.0"
        assert "Fetcher extension" in metadata.description
        assert metadata.homepage is None
        assert metadata.extension_type == ExtensionType.FETCHER
        assert metadata.registry_name == "minimal"

    def test_partial_attributes(self):
        """Test extraction with only some attributes defined."""
        class PartialExtension:
            __extension_name__ = "Partial"
            __extension_version__ = "1.0.0"
            # Other attributes missing

        metadata = extract_extension_metadata(
            PartialExtension,
            ExtensionType.PROVIDER,
            "partial"
        )

        assert metadata.name == "Partial"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Unknown"
        assert metadata.homepage is None


class TestExtensionLoader:
    """Tests for ExtensionLoader class."""

    def setup_method(self):
        """Create fresh loader for each test."""
        self.loader = ExtensionLoader()

    def test_init(self):
        """Test ExtensionLoader initialization."""
        assert self.loader._loaded_extensions == {}
        assert self.loader._load_errors == {}

    def test_discover_extensions_unknown_type(self):
        """Test discover_extensions returns empty for unknown type."""
        # Create a mock type that's not in ENTRY_POINT_GROUPS
        mock_type = MagicMock()
        mock_type.value = "unknown"

        with patch.dict(ENTRY_POINT_GROUPS, {}, clear=True):
            result = self.loader.discover_extensions(mock_type)
            assert result == []

    @patch('reconly_core.extensions.loader.entry_points')
    def test_discover_extensions_finds_entry_points(self, mock_entry_points):
        """Test discover_extensions finds registered entry points."""
        # Create mock entry points
        mock_ep1 = MagicMock()
        mock_ep1.name = "ext1"
        mock_ep2 = MagicMock()
        mock_ep2.name = "ext2"

        mock_entry_points.return_value = [mock_ep1, mock_ep2]

        names = self.loader.discover_extensions(ExtensionType.EXPORTER)

        assert "ext1" in names
        assert "ext2" in names
        mock_entry_points.assert_called_once_with(group="reconly.exporters")

    @patch('reconly_core.extensions.loader.entry_points')
    def test_discover_extensions_handles_empty(self, mock_entry_points):
        """Test discover_extensions handles no entry points."""
        mock_entry_points.return_value = []

        names = self.loader.discover_extensions(ExtensionType.EXPORTER)

        assert names == []

    @patch('reconly_core.extensions.loader.entry_points')
    def test_load_extension_not_found(self, mock_entry_points):
        """Test load_extension handles missing entry point."""
        mock_entry_points.return_value = []

        result = self.loader.load_extension(ExtensionType.EXPORTER, "nonexistent")

        assert result is None
        assert "nonexistent" in self.loader._load_errors
        assert "not found" in self.loader._load_errors["nonexistent"]

    @patch('reconly_core.extensions.loader.entry_points')
    def test_load_extension_wrong_base_class(self, mock_entry_points):
        """Test load_extension rejects extensions with wrong base class."""
        # Create a mock entry point that loads a non-BaseExporter class
        class NotAnExporter:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "bad-ext"
        mock_ep.load.return_value = NotAnExporter

        mock_entry_points.return_value = [mock_ep]

        result = self.loader.load_extension(ExtensionType.EXPORTER, "bad-ext")

        assert result is None
        assert "bad-ext" in self.loader._load_errors
        assert "must inherit from BaseExporter" in self.loader._load_errors["bad-ext"]

    @patch('reconly_core.extensions.loader.entry_points')
    @patch('reconly_core.extensions.loader.validate_extension_compatibility')
    def test_load_extension_incompatible_version(
        self, mock_validate, mock_entry_points
    ):
        """Test load_extension rejects incompatible extensions."""
        # Create a valid exporter class
        class TestExporter(BaseExporter):
            __extension_min_reconly__ = "99.0.0"  # Too high

            def export(self, digests, config=None):
                return ExportResult("", "test.txt", "text/plain", 0)

            def get_format_name(self):
                return "test"

            def get_content_type(self):
                return "text/plain"

            def get_file_extension(self):
                return "txt"

        mock_ep = MagicMock()
        mock_ep.name = "incompatible"
        mock_ep.load.return_value = TestExporter

        mock_entry_points.return_value = [mock_ep]
        mock_validate.return_value = False

        result = self.loader.load_extension(ExtensionType.EXPORTER, "incompatible")

        assert result is None
        assert "incompatible" in self.loader._load_errors
        assert "Requires Reconly" in self.loader._load_errors["incompatible"]

    @patch('reconly_core.extensions.loader.entry_points')
    @patch('reconly_core.extensions.loader.validate_extension_compatibility')
    def test_load_extension_success(self, mock_validate, mock_entry_points):
        """Test successful extension loading."""
        class GoodExporter(BaseExporter):
            __extension_name__ = "Good Exporter"
            __extension_version__ = "1.0.0"
            __extension_author__ = "Test"
            __extension_min_reconly__ = "0.1.0"
            __extension_description__ = "A good exporter"

            def export(self, digests, config=None):
                return ExportResult("", "test.txt", "text/plain", 0)

            def get_format_name(self):
                return "good"

            def get_content_type(self):
                return "text/plain"

            def get_file_extension(self):
                return "txt"

        mock_ep = MagicMock()
        mock_ep.name = "good"
        mock_ep.load.return_value = GoodExporter

        mock_entry_points.return_value = [mock_ep]
        mock_validate.return_value = True

        result = self.loader.load_extension(ExtensionType.EXPORTER, "good")

        assert result is not None
        assert isinstance(result, LoadedExtension)
        assert result.cls == GoodExporter
        assert result.metadata.name == "Good Exporter"
        assert result.entry_point_name == "good"
        assert result.entry_point_group == "reconly.exporters"

    @patch('reconly_core.extensions.loader.entry_points')
    def test_load_extension_handles_load_error(self, mock_entry_points):
        """Test load_extension handles exceptions during loading."""
        mock_ep = MagicMock()
        mock_ep.name = "broken"
        mock_ep.load.side_effect = ImportError("Module not found")

        mock_entry_points.return_value = [mock_ep]

        result = self.loader.load_extension(ExtensionType.EXPORTER, "broken")

        assert result is None
        assert "broken" in self.loader._load_errors
        assert "Module not found" in self.loader._load_errors["broken"]

    def test_get_loaded_extensions_returns_copy(self):
        """Test get_loaded_extensions returns a copy of the dict."""
        loaded = self.loader.get_loaded_extensions()
        assert loaded == {}

        # Modifying returned dict shouldn't affect internal state
        loaded["test"] = "value"
        assert self.loader.get_loaded_extensions() == {}

    def test_get_load_errors_returns_copy(self):
        """Test get_load_errors returns a copy of the dict."""
        errors = self.loader.get_load_errors()
        assert errors == {}

        # Modifying returned dict shouldn't affect internal state
        errors["test"] = "error"
        assert self.loader.get_load_errors() == {}

    @patch('reconly_core.extensions.loader.entry_points')
    @patch('reconly_core.extensions.loader.validate_extension_compatibility')
    def test_load_extensions_for_type(self, mock_validate, mock_entry_points):
        """Test load_extensions_for_type loads all extensions of a type."""
        class Exporter1(BaseExporter):
            __extension_name__ = "Exporter 1"

            def export(self, digests, config=None):
                return ExportResult("", "1.txt", "text/plain", 0)

            def get_format_name(self):
                return "ext1"

            def get_content_type(self):
                return "text/plain"

            def get_file_extension(self):
                return "txt"

        class Exporter2(BaseExporter):
            __extension_name__ = "Exporter 2"

            def export(self, digests, config=None):
                return ExportResult("", "2.txt", "text/plain", 0)

            def get_format_name(self):
                return "ext2"

            def get_content_type(self):
                return "text/plain"

            def get_file_extension(self):
                return "txt"

        mock_ep1 = MagicMock()
        mock_ep1.name = "ext1"
        mock_ep1.load.return_value = Exporter1

        mock_ep2 = MagicMock()
        mock_ep2.name = "ext2"
        mock_ep2.load.return_value = Exporter2

        mock_entry_points.return_value = [mock_ep1, mock_ep2]
        mock_validate.return_value = True

        result = self.loader.load_extensions_for_type(ExtensionType.EXPORTER)

        assert len(result.loaded) == 2
        assert result.errors == {}

    @patch('reconly_core.extensions.loader.entry_points')
    def test_load_all_loads_all_types(self, mock_entry_points):
        """Test load_all attempts to load all extension types."""
        mock_entry_points.return_value = []

        result = self.loader.load_all()

        # Should have been called for each extension type
        assert mock_entry_points.call_count == len(ExtensionType)
        assert result.loaded == []
        assert result.errors == {}


class TestEntryPointGroups:
    """Tests for ENTRY_POINT_GROUPS configuration."""

    def test_all_types_have_groups(self):
        """Test all ExtensionTypes have entry point groups defined."""
        for ext_type in ExtensionType:
            assert ext_type in ENTRY_POINT_GROUPS
            assert isinstance(ENTRY_POINT_GROUPS[ext_type], str)

    def test_group_naming_convention(self):
        """Test entry point groups follow naming convention."""
        for ext_type, group in ENTRY_POINT_GROUPS.items():
            assert group.startswith("reconly.")
            assert ext_type.value in group
