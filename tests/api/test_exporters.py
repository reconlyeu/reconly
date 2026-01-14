"""Tests for Exporters API routes."""
import pytest


@pytest.mark.api
class TestExportersAPI:
    """Test suite for /api/v1/exporters endpoints."""

    def test_list_exporters(self, client):
        """Test listing all available exporters."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        # Response should have exporters list
        assert "exporters" in data
        assert isinstance(data["exporters"], list)
        assert len(data["exporters"]) > 0  # At least one exporter should exist

    def test_exporters_have_required_fields(self, client):
        """Test that each exporter has all required fields."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "name",
            "description",
            "content_type",
            "file_extension",
            "supports_direct_export",
            "config_schema",
        ]

        for exporter in data["exporters"]:
            for field in required_fields:
                assert field in exporter, f"Exporter {exporter.get('name', 'unknown')} missing field: {field}"

    def test_exporter_config_schema_structure(self, client):
        """Test that config schema has the correct structure."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        for exporter in data["exporters"]:
            config_schema = exporter["config_schema"]
            assert "fields" in config_schema
            assert "supports_direct_export" in config_schema
            assert isinstance(config_schema["fields"], list)

    def test_obsidian_exporter_exists(self, client):
        """Test that the Obsidian exporter is available."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        exporter_names = [e["name"] for e in data["exporters"]]
        assert "obsidian" in exporter_names

    def test_obsidian_exporter_supports_direct_export(self, client):
        """Test that Obsidian exporter supports direct export."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        obsidian_exporter = next(
            (e for e in data["exporters"] if e["name"] == "obsidian"),
            None
        )
        assert obsidian_exporter is not None
        assert obsidian_exporter["supports_direct_export"] is True

    def test_obsidian_exporter_has_config_fields(self, client):
        """Test that Obsidian exporter has expected config fields."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        obsidian_exporter = next(
            (e for e in data["exporters"] if e["name"] == "obsidian"),
            None
        )
        assert obsidian_exporter is not None

        config_fields = obsidian_exporter["config_schema"]["fields"]
        field_keys = [f["key"] for f in config_fields]

        # Expected config fields for Obsidian exporter
        expected_fields = ["vault_path", "subfolder", "filename_pattern", "one_file_per_digest"]
        for expected in expected_fields:
            assert expected in field_keys, f"Missing config field: {expected}"

    def test_config_field_structure(self, client):
        """Test that config fields have the correct structure."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        # Find an exporter with config fields
        exporter_with_config = next(
            (e for e in data["exporters"] if len(e["config_schema"]["fields"]) > 0),
            None
        )

        if exporter_with_config:
            required_field_attrs = [
                "key",
                "type",
                "label",
                "description",
                "required",
                "placeholder",
            ]

            for field in exporter_with_config["config_schema"]["fields"]:
                for attr in required_field_attrs:
                    assert attr in field, f"Config field missing attribute: {attr}"

    def test_json_exporter_supports_direct_export(self, client):
        """Test that JSON exporter supports direct export."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        json_exporter = next(
            (e for e in data["exporters"] if e["name"] == "json"),
            None
        )
        assert json_exporter is not None
        assert json_exporter["supports_direct_export"] is True
        assert len(json_exporter["config_schema"]["fields"]) == 3

    def test_csv_exporter_supports_direct_export(self, client):
        """Test that CSV exporter supports direct export."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        csv_exporter = next(
            (e for e in data["exporters"] if e["name"] == "csv"),
            None
        )
        assert csv_exporter is not None
        assert csv_exporter["supports_direct_export"] is True
        assert len(csv_exporter["config_schema"]["fields"]) == 3

    def test_exporters_have_valid_content_types(self, client):
        """Test that exporters have valid content types."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        valid_content_types = [
            "application/json",
            "text/csv",
            "text/markdown",
            "text/plain",
        ]

        for exporter in data["exporters"]:
            assert exporter["content_type"] in valid_content_types, \
                f"Invalid content type: {exporter['content_type']}"

    def test_exporters_have_file_extensions(self, client):
        """Test that exporters have valid file extensions."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        for exporter in data["exporters"]:
            assert exporter["file_extension"], f"Exporter {exporter['name']} has no file extension"
            assert not exporter["file_extension"].startswith("."), \
                f"File extension should not start with dot: {exporter['file_extension']}"


@pytest.mark.api
class TestExportersFieldTypes:
    """Test suite for config field type validation."""

    def test_vault_path_field_is_path_type(self, client):
        """Test that vault_path field is of type 'path'."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        obsidian_exporter = next(
            (e for e in data["exporters"] if e["name"] == "obsidian"),
            None
        )
        assert obsidian_exporter is not None

        vault_path_field = next(
            (f for f in obsidian_exporter["config_schema"]["fields"] if f["key"] == "vault_path"),
            None
        )
        assert vault_path_field is not None
        assert vault_path_field["type"] == "path"
        assert vault_path_field["required"] is True

    def test_one_file_per_digest_is_boolean(self, client):
        """Test that one_file_per_digest field is of type 'boolean'."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        obsidian_exporter = next(
            (e for e in data["exporters"] if e["name"] == "obsidian"),
            None
        )
        assert obsidian_exporter is not None

        boolean_field = next(
            (f for f in obsidian_exporter["config_schema"]["fields"] if f["key"] == "one_file_per_digest"),
            None
        )
        assert boolean_field is not None
        assert boolean_field["type"] == "boolean"

    def test_filename_pattern_is_string(self, client):
        """Test that filename_pattern field is of type 'string'."""
        response = client.get("/api/v1/exporters")
        assert response.status_code == 200
        data = response.json()

        obsidian_exporter = next(
            (e for e in data["exporters"] if e["name"] == "obsidian"),
            None
        )
        assert obsidian_exporter is not None

        string_field = next(
            (f for f in obsidian_exporter["config_schema"]["fields"] if f["key"] == "filename_pattern"),
            None
        )
        assert string_field is not None
        assert string_field["type"] == "string"
