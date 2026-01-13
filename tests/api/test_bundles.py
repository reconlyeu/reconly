"""Tests for Bundle API routes (export/import)."""
import pytest


@pytest.mark.api
class TestBundleExportAPI:
    """Test suite for /api/v1/feeds/{id}/export endpoint."""

    def test_export_feed_success(self, client, sample_feed):
        """Test successful feed export."""
        response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "bundle" in data
        assert "filename" in data

        bundle = data["bundle"]
        assert bundle["schema_version"] == "1.0"
        assert bundle["bundle"]["name"] == "Test Feed"
        assert bundle["bundle"]["version"] == "1.0.0"
        assert len(bundle["bundle"]["sources"]) == 1

    def test_export_feed_with_options(self, client, sample_feed):
        """Test export with optional parameters."""
        response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={
                "version": "2.0.0",
                "category": "tech",
                "tags": ["ai", "news"],
                "min_reconly_version": "0.2.0",
                "license": "MIT",
            },
        )
        assert response.status_code == 200
        data = response.json()

        bundle = data["bundle"]
        assert bundle["bundle"]["version"] == "2.0.0"
        assert bundle["bundle"]["category"] == "tech"
        assert bundle["bundle"]["tags"] == ["ai", "news"]
        assert bundle["compatibility"]["min_reconly_version"] == "0.2.0"
        assert bundle["metadata"]["license"] == "MIT"

    def test_export_feed_includes_templates(self, client, sample_feed):
        """Test that export includes prompt and report templates."""
        response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 200
        data = response.json()

        bundle = data["bundle"]["bundle"]
        assert "prompt_template" in bundle
        assert bundle["prompt_template"]["name"] == "Test Prompt Template"
        assert "report_template" in bundle
        assert bundle["report_template"]["name"] == "Test Report Template"

    def test_export_feed_includes_schedule(self, client, sample_feed):
        """Test that export includes schedule."""
        response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 200
        data = response.json()

        bundle = data["bundle"]["bundle"]
        assert "schedule" in bundle
        assert bundle["schedule"]["cron"] == "0 9 * * *"

    def test_export_feed_not_found(self, client):
        """Test export of non-existent feed."""
        response = client.post(
            "/api/v1/feeds/99999/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 404

    def test_export_feed_generates_filename(self, client, sample_feed):
        """Test that export generates appropriate filename."""
        response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 200
        data = response.json()

        # Filename should be slug-version.json
        assert data["filename"] == "test-feed-1.0.0.json"

    def test_export_feed_without_sources_fails(self, client, test_db):
        """Test that export fails if feed has no sources."""
        from reconly_core.database.models import Feed

        # Create feed without sources
        feed = Feed(name="Empty Feed", description="No sources")
        test_db.add(feed)
        test_db.commit()

        response = client.post(
            f"/api/v1/feeds/{feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert response.status_code == 400
        assert "no sources" in response.json()["detail"].lower()


@pytest.mark.api
class TestBundleValidateAPI:
    """Test suite for /api/v1/bundles/validate endpoint."""

    @pytest.fixture
    def valid_bundle(self):
        """Create a valid minimal bundle."""
        return {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Test", "type": "rss", "url": "https://example.com/feed"},
                ],
            },
        }

    def test_validate_valid_bundle(self, client, valid_bundle):
        """Test validation of valid bundle."""
        response = client.post(
            "/api/v1/bundles/validate",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_invalid_bundle(self, client):
        """Test validation of invalid bundle."""
        invalid_bundle = {
            "schema_version": "1.0",
            "bundle": {
                "id": "test",
                # Missing required fields
            },
        }

        response = client.post(
            "/api/v1/bundles/validate",
            json={"bundle": invalid_bundle},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_returns_warnings(self, client):
        """Test that validation returns warnings."""
        bundle_with_warnings = {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Test", "type": "rss", "url": "ftp://example.com/feed"},  # Warning: not http
                ],
            },
        }

        response = client.post(
            "/api/v1/bundles/validate",
            json={"bundle": bundle_with_warnings},
        )
        assert response.status_code == 200
        data = response.json()

        # Should be valid but with warnings
        assert data["is_valid"] is True
        assert len(data["warnings"]) > 0


@pytest.mark.api
class TestBundlePreviewAPI:
    """Test suite for /api/v1/bundles/preview endpoint."""

    @pytest.fixture
    def valid_bundle(self):
        """Create a valid bundle for preview."""
        return {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "description": "A test feed",
                "sources": [
                    {"name": "Test RSS", "type": "rss", "url": "https://example.com/feed.xml"},
                ],
                "prompt_template": {
                    "name": "Test Prompt",
                    "system_prompt": "Test",
                    "user_prompt_template": "Test",
                },
                "schedule": {
                    "cron": "0 9 * * *",
                },
            },
        }

    def test_preview_valid_bundle(self, client, valid_bundle):
        """Test preview of valid bundle."""
        response = client.post(
            "/api/v1/bundles/preview",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["feed"]["name"] == "Test Feed"
        assert data["feed"]["already_exists"] is False
        assert data["sources"]["total"] == 1
        assert len(data["sources"]["new"]) == 1
        assert data["prompt_template"]["included"] is True
        assert data["schedule"]["included"] is True
        assert data["schedule"]["cron"] == "0 9 * * *"

    def test_preview_invalid_bundle(self, client):
        """Test preview of invalid bundle."""
        response = client.post(
            "/api/v1/bundles/preview",
            json={"bundle": {"schema_version": "1.0", "bundle": {}}},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_preview_shows_existing_feed(self, client, sample_feed, valid_bundle):
        """Test preview shows when feed already exists."""
        # Update bundle to match existing feed name
        valid_bundle["bundle"]["name"] = sample_feed.name

        response = client.post(
            "/api/v1/bundles/preview",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["feed"]["already_exists"] is True

    def test_preview_shows_existing_sources(self, client, sample_source, valid_bundle):
        """Test preview shows when sources already exist."""
        # Update bundle to use existing source URL
        valid_bundle["bundle"]["sources"][0]["url"] = sample_source.url

        response = client.post(
            "/api/v1/bundles/preview",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert len(data["sources"]["existing"]) == 1
        assert len(data["sources"]["new"]) == 0
        assert data["sources"]["existing"][0]["existing_id"] == sample_source.id


@pytest.mark.api
class TestBundleImportAPI:
    """Test suite for /api/v1/bundles/import endpoint."""

    @pytest.fixture
    def valid_bundle(self):
        """Create a valid bundle for import."""
        return {
            "schema_version": "1.0",
            "bundle": {
                "id": "imported-feed",
                "name": "Imported Feed",
                "version": "1.0.0",
                "description": "A feed imported via API",
                "sources": [
                    {"name": "Import Source", "type": "rss", "url": "https://import.example.com/feed.xml"},
                ],
                "prompt_template": {
                    "name": "Import Prompt",
                    "system_prompt": "You are helpful.",
                    "user_prompt_template": "Summarize: {content}",
                    "target_length": 150,
                },
                "report_template": {
                    "name": "Import Report",
                    "format": "markdown",
                    "template_content": "# Report\n\n{content}",
                },
                "schedule": {
                    "cron": "0 8 * * *",
                },
            },
        }

    def test_import_bundle_success(self, client, valid_bundle):
        """Test successful bundle import."""
        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["feed_id"] is not None
        assert data["feed_name"] == "Imported Feed"
        assert data["sources_created"] == 1
        assert data["prompt_template_id"] is not None
        assert data["report_template_id"] is not None

    def test_import_bundle_creates_feed(self, client, test_db, valid_bundle):
        """Test that import creates feed in database."""
        from reconly_core.database.models import Feed

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 201
        feed_id = response.json()["feed_id"]

        # Verify in database
        feed = test_db.query(Feed).filter(Feed.id == feed_id).first()
        assert feed is not None
        assert feed.name == "Imported Feed"
        assert feed.schedule_cron == "0 8 * * *"
        assert feed.schedule_enabled is True

    def test_import_bundle_creates_templates_with_origin(self, client, test_db, valid_bundle):
        """Test that imported templates have correct origin."""
        from reconly_core.database.models import PromptTemplate, ReportTemplate

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 201
        data = response.json()

        prompt = test_db.query(PromptTemplate).filter(
            PromptTemplate.id == data["prompt_template_id"]
        ).first()
        assert prompt.origin == "imported"
        assert prompt.imported_from_bundle == "imported-feed@1.0.0"

        report = test_db.query(ReportTemplate).filter(
            ReportTemplate.id == data["report_template_id"]
        ).first()
        assert report.origin == "imported"
        assert report.imported_from_bundle == "imported-feed@1.0.0"

    def test_import_bundle_validation_error(self, client):
        """Test import with invalid bundle returns error."""
        invalid_bundle = {
            "schema_version": "1.0",
            "bundle": {
                "id": "test",
                # Missing required fields
            },
        }

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": invalid_bundle},
        )
        assert response.status_code == 400
        data = response.json()["detail"]

        assert "errors" in data
        assert len(data["errors"]) > 0

    def test_import_bundle_duplicate_feed_error(self, client, sample_feed, valid_bundle):
        """Test import fails when feed name already exists."""
        valid_bundle["bundle"]["name"] = sample_feed.name

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": valid_bundle},
        )
        assert response.status_code == 400
        data = response.json()["detail"]

        assert any("already exists" in e for e in data["errors"])

    def test_import_bundle_reuses_existing_sources(self, client, sample_source, valid_bundle):
        """Test import reuses existing sources with same URL."""
        valid_bundle["bundle"]["sources"][0]["url"] = sample_source.url

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": valid_bundle, "skip_duplicate_sources": True},
        )
        assert response.status_code == 201
        data = response.json()

        # Should still succeed with warning
        assert data["success"] is True
        assert any("Reusing" in w for w in data["warnings"])

    def test_import_bundle_without_templates(self, client):
        """Test import without templates."""
        simple_bundle = {
            "schema_version": "1.0",
            "bundle": {
                "id": "simple-feed",
                "name": "Simple Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Simple", "type": "rss", "url": "https://simple.example.com/feed"},
                ],
            },
        }

        response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": simple_bundle},
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["prompt_template_id"] is None
        assert data["report_template_id"] is None


@pytest.mark.api
class TestBundleSchemaAPI:
    """Test suite for /api/v1/bundles/schema endpoint."""

    def test_get_schema(self, client):
        """Test getting bundle schema."""
        response = client.get("/api/v1/bundles/schema")
        assert response.status_code == 200
        data = response.json()

        # Should return the JSON schema
        assert "type" in data
        assert "properties" in data


@pytest.mark.api
class TestBundleRoundTrip:
    """Integration tests for export -> import round trip."""

    def test_export_import_roundtrip(self, client, sample_feed):
        """Test that exported bundle can be imported successfully."""
        # Export
        export_response = client.post(
            f"/api/v1/feeds/{sample_feed.id}/export",
            json={"version": "1.0.0"},
        )
        assert export_response.status_code == 200
        exported_bundle = export_response.json()["bundle"]

        # Change the name to avoid conflict
        exported_bundle["bundle"]["name"] = "Imported " + exported_bundle["bundle"]["name"]
        exported_bundle["bundle"]["id"] = "imported-" + exported_bundle["bundle"]["id"]

        # Import
        import_response = client.post(
            "/api/v1/bundles/import",
            json={"bundle": exported_bundle},
        )
        assert import_response.status_code == 201
        import_data = import_response.json()

        assert import_data["success"] is True
        assert import_data["feed_name"] == "Imported Test Feed"
        assert import_data["sources_created"] == 1
