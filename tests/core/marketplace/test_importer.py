"""Tests for feed bundle importer."""
import pytest
import json

from reconly_core.database.models import Feed, Source, PromptTemplate, ReportTemplate, FeedSource
from reconly_core.marketplace.importer import FeedBundleImporter, ImportResult


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_initial_state(self):
        """Test initial state is success with empty lists."""
        result = ImportResult(success=True)
        assert result.success is True
        assert result.feed_id is None
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        """Test adding an error marks result as failure."""
        result = ImportResult(success=True)
        result.add_error("Test error")
        assert result.success is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding a warning does not affect success."""
        result = ImportResult(success=True)
        result.add_warning("Test warning")
        assert result.success is True
        assert "Test warning" in result.warnings


@pytest.mark.integration
class TestFeedBundleImporter:
    """Integration tests for FeedBundleImporter using database fixtures."""

    @pytest.fixture
    def valid_bundle_data(self):
        """Create valid bundle data for import."""
        return {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "description": "A test feed",
                "sources": [
                    {
                        "name": "Test RSS",
                        "type": "rss",
                        "url": "https://example.com/feed.xml",
                        "config": {"max_items": 10},
                    },
                ],
                "prompt_template": {
                    "name": "Test Prompt",
                    "system_prompt": "You are helpful.",
                    "user_prompt_template": "Summarize: {content}",
                    "target_length": 150,
                },
                "report_template": {
                    "name": "Test Report",
                    "format": "markdown",
                    "template_content": "# Report\n\n{content}",
                },
                "schedule": {
                    "cron": "0 9 * * *",
                },
            },
        }

    def test_import_bundle_success(self, db_session, valid_bundle_data):
        """Test successful bundle import."""
        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data)

        assert result.success is True
        assert result.feed_id is not None
        assert result.feed_name == "Test Feed"
        assert result.sources_created == 1
        assert result.prompt_template_id is not None
        assert result.report_template_id is not None
        assert len(result.errors) == 0

        # Verify feed was created
        feed = db_session.query(Feed).filter(Feed.id == result.feed_id).first()
        assert feed is not None
        assert feed.name == "Test Feed"
        assert feed.schedule_cron == "0 9 * * *"

    def test_import_bundle_creates_sources(self, db_session, valid_bundle_data):
        """Test that sources are created correctly."""
        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data)

        # Find the source
        source = db_session.query(Source).filter(Source.url == "https://example.com/feed.xml").first()
        assert source is not None
        assert source.name == "Test RSS"
        assert source.type == "rss"
        assert source.config == {"max_items": 10}

        # Verify feed-source link
        feed_source = db_session.query(FeedSource).filter(
            FeedSource.feed_id == result.feed_id,
            FeedSource.source_id == source.id,
        ).first()
        assert feed_source is not None
        assert feed_source.enabled is True

    def test_import_bundle_creates_prompt_template(self, db_session, valid_bundle_data):
        """Test that prompt template is created with correct origin."""
        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data)

        template = db_session.query(PromptTemplate).filter(
            PromptTemplate.id == result.prompt_template_id
        ).first()
        assert template is not None
        assert "Test Prompt" in template.name
        assert template.origin == "imported"
        assert template.imported_from_bundle == "test-feed@1.0.0"

    def test_import_bundle_creates_report_template(self, db_session, valid_bundle_data):
        """Test that report template is created with correct origin."""
        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data)

        template = db_session.query(ReportTemplate).filter(
            ReportTemplate.id == result.report_template_id
        ).first()
        assert template is not None
        assert "Test Report" in template.name
        assert template.origin == "imported"
        assert template.imported_from_bundle == "test-feed@1.0.0"

    def test_import_bundle_reuses_existing_source(self, db_session, valid_bundle_data):
        """Test that existing sources with same URL are reused."""
        # Create existing source
        existing_source = Source(
            name="Existing Source",
            type="rss",
            url="https://example.com/feed.xml",
            enabled=True,
        )
        db_session.add(existing_source)
        db_session.commit()
        existing_id = existing_source.id

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data, skip_duplicate_sources=True)

        assert result.success is True
        # Should have a warning about reusing source
        assert any("Reusing" in w for w in result.warnings)

        # Verify the feed uses the existing source
        feed = db_session.query(Feed).filter(Feed.id == result.feed_id).first()
        feed_source = db_session.query(FeedSource).filter(
            FeedSource.feed_id == feed.id
        ).first()
        assert feed_source.source_id == existing_id

    def test_import_bundle_duplicate_feed_name_error(self, db_session, valid_bundle_data):
        """Test error when feed with same name already exists."""
        # Create existing feed
        existing_feed = Feed(name="Test Feed", description="Existing")
        db_session.add(existing_feed)
        db_session.commit()

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(valid_bundle_data)

        assert result.success is False
        assert any("already exists" in e for e in result.errors)

    def test_import_bundle_validation_error(self, db_session):
        """Test that validation errors are caught."""
        invalid_data = {
            "schema_version": "1.0",
            "bundle": {
                "id": "test",
                # Missing required fields
            },
        }

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(invalid_data)

        assert result.success is False
        assert len(result.errors) > 0

    def test_import_bundle_without_templates(self, db_session):
        """Test import of bundle without templates."""
        data = {
            "schema_version": "1.0",
            "bundle": {
                "id": "simple-feed",
                "name": "Simple Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Test", "type": "rss", "url": "https://example.com/feed"},
                ],
            },
        }

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(data)

        assert result.success is True
        assert result.prompt_template_id is None
        assert result.report_template_id is None

    def test_import_bundle_without_schedule(self, db_session):
        """Test import of bundle without schedule."""
        data = {
            "schema_version": "1.0",
            "bundle": {
                "id": "no-schedule",
                "name": "No Schedule Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Test", "type": "rss", "url": "https://example.com/feed"},
                ],
            },
        }

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(data)

        assert result.success is True
        feed = db_session.query(Feed).filter(Feed.id == result.feed_id).first()
        assert feed.schedule_cron is None
        assert feed.schedule_enabled is False

    def test_import_bundle_reuses_template_from_same_bundle(self, db_session, valid_bundle_data):
        """Test that templates from same bundle version are reused."""
        importer = FeedBundleImporter(db_session)

        # First import (creates templates)
        result1 = importer.import_bundle(valid_bundle_data)
        assert result1.success is True
        prompt_id1 = result1.prompt_template_id

        # Delete the feed but keep templates
        db_session.delete(db_session.query(Feed).filter(Feed.id == result1.feed_id).first())
        db_session.commit()

        # Second import with same bundle - should reuse templates
        valid_bundle_data["bundle"]["name"] = "Test Feed 2"  # Different feed name
        result2 = importer.import_bundle(valid_bundle_data)

        assert result2.success is True
        assert result2.prompt_template_id == prompt_id1
        # Should have warning about reusing template
        assert any("Reusing existing prompt template" in w for w in result2.warnings)

    def test_import_from_json_string(self, db_session, valid_bundle_data):
        """Test importing from JSON string."""
        json_str = json.dumps(valid_bundle_data)

        importer = FeedBundleImporter(db_session)
        result = importer.import_from_json(json_str)

        assert result.success is True
        assert result.feed_id is not None

    def test_import_from_invalid_json(self, db_session):
        """Test error handling for invalid JSON."""
        importer = FeedBundleImporter(db_session)
        result = importer.import_from_json("not valid json {{{")

        assert result.success is False
        assert any("Invalid JSON" in e for e in result.errors)

    def test_import_bundle_multiple_sources(self, db_session):
        """Test importing bundle with multiple sources."""
        data = {
            "schema_version": "1.0",
            "bundle": {
                "id": "multi-source",
                "name": "Multi Source Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Source 1", "type": "rss", "url": "https://example.com/feed1"},
                    {"name": "Source 2", "type": "youtube", "url": "https://youtube.com/@channel"},
                    {"name": "Source 3", "type": "website", "url": "https://example.org"},
                ],
            },
        }

        importer = FeedBundleImporter(db_session)
        result = importer.import_bundle(data)

        assert result.success is True
        assert result.sources_created == 3

        # Verify priority ordering (first source has highest priority)
        feed = db_session.query(Feed).filter(Feed.id == result.feed_id).first()
        feed_sources = db_session.query(FeedSource).filter(
            FeedSource.feed_id == feed.id
        ).order_by(FeedSource.priority.desc()).all()
        assert len(feed_sources) == 3
        # First source should have highest priority
        assert feed_sources[0].priority == 3
        assert feed_sources[2].priority == 1


class TestPreviewImport:
    """Tests for preview_import method."""

    @pytest.fixture
    def valid_bundle_data(self):
        return {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "description": "A test feed",
                "sources": [
                    {"name": "Test", "type": "rss", "url": "https://example.com/feed.xml"},
                ],
                "prompt_template": {
                    "name": "Prompt",
                    "system_prompt": "Test",
                    "user_prompt_template": "Test",
                },
            },
        }

    def test_preview_valid_bundle(self, db_session, valid_bundle_data):
        """Test preview of valid bundle."""
        importer = FeedBundleImporter(db_session)
        preview = importer.preview_import(valid_bundle_data)

        assert preview["valid"] is True
        assert preview["feed"]["name"] == "Test Feed"
        assert preview["feed"]["already_exists"] is False
        assert preview["sources"]["total"] == 1
        assert len(preview["sources"]["new"]) == 1
        assert preview["prompt_template"]["included"] is True

    def test_preview_invalid_bundle(self, db_session):
        """Test preview of invalid bundle."""
        invalid_data = {"schema_version": "1.0", "bundle": {}}

        importer = FeedBundleImporter(db_session)
        preview = importer.preview_import(invalid_data)

        assert preview["valid"] is False
        assert len(preview["errors"]) > 0

    def test_preview_shows_existing_feed(self, db_session, valid_bundle_data):
        """Test preview identifies existing feed."""
        # Create existing feed
        existing = Feed(name="Test Feed", description="Existing")
        db_session.add(existing)
        db_session.commit()

        importer = FeedBundleImporter(db_session)
        preview = importer.preview_import(valid_bundle_data)

        assert preview["valid"] is True
        assert preview["feed"]["already_exists"] is True

    def test_preview_shows_existing_sources(self, db_session, valid_bundle_data):
        """Test preview identifies existing sources."""
        # Create existing source
        existing = Source(name="Existing", type="rss", url="https://example.com/feed.xml")
        db_session.add(existing)
        db_session.commit()

        importer = FeedBundleImporter(db_session)
        preview = importer.preview_import(valid_bundle_data)

        assert preview["valid"] is True
        assert len(preview["sources"]["existing"]) == 1
        assert len(preview["sources"]["new"]) == 0
        assert preview["sources"]["existing"][0]["existing_id"] == existing.id
