"""Tests for base component metadata."""
from reconly_core.metadata import ComponentMetadata


class TestComponentMetadata:
    """Test cases for ComponentMetadata dataclass."""

    def test_required_fields(self):
        """Test creating metadata with required fields only."""
        metadata = ComponentMetadata(
            name="test_component",
            display_name="Test Component",
            description="A test component for unit tests",
        )

        assert metadata.name == "test_component"
        assert metadata.display_name == "Test Component"
        assert metadata.description == "A test component for unit tests"
        assert metadata.icon is None

    def test_all_fields(self):
        """Test creating metadata with all fields including optional."""
        metadata = ComponentMetadata(
            name="my_exporter",
            display_name="My Exporter",
            description="Exports data to my format",
            icon="mdi:file-export",
        )

        assert metadata.name == "my_exporter"
        assert metadata.display_name == "My Exporter"
        assert metadata.description == "Exports data to my format"
        assert metadata.icon == "mdi:file-export"

    def test_to_dict_minimal(self):
        """Test to_dict() with minimal fields."""
        metadata = ComponentMetadata(
            name="test",
            display_name="Test",
            description="Test description",
        )

        result = metadata.to_dict()

        assert result == {
            "name": "test",
            "display_name": "Test",
            "description": "Test description",
            "icon": None,
        }

    def test_to_dict_with_icon(self):
        """Test to_dict() with icon set."""
        metadata = ComponentMetadata(
            name="rss",
            display_name="RSS Feed",
            description="Fetches RSS and Atom feeds",
            icon="mdi:rss",
        )

        result = metadata.to_dict()

        assert result == {
            "name": "rss",
            "display_name": "RSS Feed",
            "description": "Fetches RSS and Atom feeds",
            "icon": "mdi:rss",
        }

    def test_realistic_fetcher_metadata(self):
        """Test with realistic fetcher-like metadata."""
        metadata = ComponentMetadata(
            name="youtube",
            display_name="YouTube",
            description="Fetches video transcripts from YouTube",
            icon="mdi:youtube",
        )

        assert metadata.name == "youtube"
        assert metadata.display_name == "YouTube"
        assert "transcript" in metadata.description.lower()
        assert metadata.icon == "mdi:youtube"

    def test_realistic_exporter_metadata(self):
        """Test with realistic exporter-like metadata."""
        metadata = ComponentMetadata(
            name="obsidian",
            display_name="Obsidian",
            description="Export to Obsidian vault as Markdown notes",
            icon="simple-icons:obsidian",
        )

        result = metadata.to_dict()

        assert result["name"] == "obsidian"
        assert result["display_name"] == "Obsidian"
        assert "obsidian" in result["description"].lower()

    def test_empty_strings_allowed(self):
        """Test that empty strings are allowed (though not recommended)."""
        metadata = ComponentMetadata(
            name="",
            display_name="",
            description="",
        )

        assert metadata.name == ""
        assert metadata.display_name == ""
        assert metadata.description == ""

    def test_unicode_in_fields(self):
        """Test that unicode characters are handled correctly."""
        metadata = ComponentMetadata(
            name="german_provider",
            display_name="Deutscher Anbieter",
            description="Unterst\u00fctzt deutsche Umlaute: \u00e4\u00f6\u00fc\u00df",
            icon="mdi:flag-de",
        )

        result = metadata.to_dict()

        assert result["display_name"] == "Deutscher Anbieter"
        assert "\u00e4" in result["description"]
        assert "\u00f6" in result["description"]
        assert "\u00fc" in result["description"]
        assert "\u00df" in result["description"]
