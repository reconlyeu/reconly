"""Tests for Export-to-Path API endpoint."""
import os
import pytest
import tempfile
from pathlib import Path
from reconly_core.database.models import Digest


@pytest.fixture
def sample_digests(test_db):
    """Create sample digests for export testing."""
    digests = []
    for i in range(3):
        digest = Digest(
            url=f"https://example.com/article-{i}",
            title=f"Test Article {i}",
            content=f"Content for article {i}.",
            summary=f"Summary of article {i}.",
            source_type="rss",
            feed_url="https://example.com/feed.xml",
            feed_title="Example Feed",
            author="Test Author",
            provider="ollama",
            language="en",
            estimated_cost=0.001,
            tags=[]
        )
        test_db.add(digest)
        digests.append(digest)
    test_db.commit()
    for d in digests:
        test_db.refresh(d)
    return digests


@pytest.fixture
def temp_export_dir():
    """Create a temporary directory for export testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.mark.api
class TestExportToPathAPI:
    """Test suite for POST /api/v1/digests/export-to-path/ endpoint."""

    def test_export_to_path_success(self, client, sample_digests, temp_export_dir):
        """Test successful export to filesystem."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["files_written"] == 3
        assert len(data["filenames"]) == 3
        assert data["errors"] == []

        # Verify files were actually created (no subfolder by default)
        export_dir = Path(temp_export_dir)
        md_files = list(export_dir.glob("*.md"))
        assert len(md_files) == 3

    def test_export_to_path_empty_digests(self, client, temp_export_dir):
        """Test export when no digests match filters."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["files_written"] == 0
        assert data["filenames"] == []
        assert data["errors"] == []

    def test_export_to_path_invalid_format(self, client, temp_export_dir):
        """Test export with unsupported format."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "invalid_format",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 400
        assert "Unsupported format" in response.json()["detail"]

    def test_export_to_path_json_works(self, client, temp_export_dir, sample_digests):
        """Test JSON format supports direct export."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "json",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_export_to_path_csv_works(self, client, temp_export_dir, sample_digests):
        """Test CSV format supports direct export."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "csv",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_export_to_path_nonexistent_path(self, client):
        """Test export to non-existent path."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": "/nonexistent/path/that/does/not/exist"
            }
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_export_to_path_file_not_directory(self, client, temp_export_dir):
        """Test export to a file instead of directory."""
        # Create a file, not a directory
        file_path = Path(temp_export_dir) / "test_file.txt"
        file_path.write_text("test")

        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": str(file_path)
            }
        )
        assert response.status_code == 400
        assert "not a directory" in response.json()["detail"]

    def test_export_to_path_no_path_no_config(self, client):
        """Test export without path and without configured default path."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian"
                # No path provided
            }
        )
        assert response.status_code == 400
        assert "No target path provided" in response.json()["detail"]


@pytest.mark.api
class TestExportToPathFilters:
    """Test suite for export-to-path filtering options."""

    def test_export_with_search_filter(self, client, sample_digests, temp_export_dir):
        """Test export with search filter."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir,
                "search": "Article 1"  # Should match only one digest
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["files_written"] == 1
        assert len(data["filenames"]) == 1

    def test_export_with_source_id_filter(self, client, test_db, sample_source, temp_export_dir):
        """Test export with source_id filter."""
        # Create a digest linked to the sample source
        digest = Digest(
            url="https://example.com/source-linked",
            title="Source Linked Article",
            content="Content",
            summary="Summary",
            source_type="rss",
            source_id=sample_source.id,
            provider="ollama",
            language="en",
            estimated_cost=0.001,
            tags=[]
        )
        test_db.add(digest)
        test_db.commit()

        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir,
                "source_id": sample_source.id
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["files_written"] == 1


@pytest.mark.api
class TestExportToPathResponseFormat:
    """Test suite for export-to-path response format."""

    def test_response_has_required_fields(self, client, sample_digests, temp_export_dir):
        """Test that response has all required fields."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        required_fields = ["success", "files_written", "target_path", "filenames", "errors"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_response_field_types(self, client, sample_digests, temp_export_dir):
        """Test that response fields have correct types."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["success"], bool)
        assert isinstance(data["files_written"], int)
        assert isinstance(data["target_path"], str)
        assert isinstance(data["filenames"], list)
        assert isinstance(data["errors"], list)

    def test_target_path_is_vault_path_by_default(self, client, sample_digests, temp_export_dir):
        """Test that target_path is the vault path when no subfolder configured."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        # No default subfolder - exports directly to vault path
        assert data["target_path"] == temp_export_dir


@pytest.mark.api
class TestExportToPathFileContent:
    """Test suite for exported file content validation."""

    def test_exported_files_are_markdown(self, client, sample_digests, temp_export_dir):
        """Test that exported files have .md extension."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200
        data = response.json()

        for filename in data["filenames"]:
            assert filename.endswith(".md"), f"File should have .md extension: {filename}"

    def test_exported_files_have_frontmatter(self, client, sample_digests, temp_export_dir):
        """Test that exported files have YAML frontmatter."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200

        # Read one of the exported files
        export_dir = Path(temp_export_dir)
        md_files = list(export_dir.glob("*.md"))
        assert len(md_files) > 0

        content = md_files[0].read_text(encoding="utf-8")
        # YAML frontmatter starts and ends with ---
        assert content.startswith("---"), "File should start with YAML frontmatter"
        assert "---" in content[3:], "File should have closing frontmatter delimiter"

    def test_exported_files_contain_digest_content(self, client, sample_digests, temp_export_dir):
        """Test that exported files contain the digest summary."""
        response = client.post(
            "/api/v1/digests/export-to-path/",
            json={
                "format": "obsidian",
                "path": temp_export_dir
            }
        )
        assert response.status_code == 200

        # Read exported files and check for digest content
        export_dir = Path(temp_export_dir)
        md_files = list(export_dir.glob("*.md"))

        # At least one file should contain "Summary of article"
        found_content = False
        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            if "Summary of article" in content:
                found_content = True
                break

        assert found_content, "Exported files should contain digest summary"
