"""Tests for feed bundle exporter."""
import pytest
from unittest.mock import MagicMock

from reconly_core.marketplace.exporter import FeedBundleExporter
from reconly_core.marketplace.bundle import FeedBundle


class TestFeedBundleExporter:
    """Tests for FeedBundleExporter."""

    @pytest.fixture
    def exporter(self):
        """Create an exporter instance."""
        return FeedBundleExporter(
            author_name="Test Author",
            author_github="testauthor",
            author_email="test@example.com",
        )

    @pytest.fixture
    def mock_feed(self):
        """Create a mock feed with all relationships."""
        # Create mock source
        mock_source = MagicMock()
        mock_source.name = "Test RSS Feed"
        mock_source.type = "rss"
        mock_source.url = "https://example.com/feed.xml"
        mock_source.config = {"max_items": 10}
        mock_source.default_language = "en"
        mock_source.include_keywords = ["tech"]
        mock_source.exclude_keywords = None
        mock_source.filter_mode = "title_only"
        mock_source.use_regex = False

        # Create mock feed_source junction
        mock_feed_source = MagicMock()
        mock_feed_source.enabled = True
        mock_feed_source.source = mock_source

        # Create mock prompt template
        mock_prompt = MagicMock()
        mock_prompt.name = "Test Prompt"
        mock_prompt.description = "A test prompt template"
        mock_prompt.system_prompt = "You are helpful."
        mock_prompt.user_prompt_template = "Summarize: {content}"
        mock_prompt.language = "en"
        mock_prompt.target_length = 150

        # Create mock report template
        mock_report = MagicMock()
        mock_report.name = "Test Report"
        mock_report.description = "A test report template"
        mock_report.format = "markdown"
        mock_report.template_content = "# Report\n\n{content}"

        # Create mock feed
        mock_feed = MagicMock()
        mock_feed.name = "Test Feed"
        mock_feed.description = "A test feed for testing"
        mock_feed.schedule_cron = "0 9 * * *"
        mock_feed.digest_mode = "individual"
        mock_feed.output_config = {"db": True, "email": {"enabled": True, "to": ["test@example.com"]}}
        mock_feed.feed_sources = [mock_feed_source]
        mock_feed.prompt_template = mock_prompt
        mock_feed.report_template = mock_report

        return mock_feed

    def test_export_feed_basic(self, exporter, mock_feed):
        """Test basic feed export."""
        bundle = exporter.export_feed(mock_feed)

        assert isinstance(bundle, FeedBundle)
        assert bundle.name == "Test Feed"
        assert bundle.id == "test-feed"
        assert bundle.version == "1.0.0"
        assert bundle.description == "A test feed for testing"

    def test_export_feed_author(self, exporter, mock_feed):
        """Test that author info is included."""
        bundle = exporter.export_feed(mock_feed)

        assert bundle.author is not None
        assert bundle.author.name == "Test Author"
        assert bundle.author.github == "testauthor"
        assert bundle.author.email == "test@example.com"

    def test_export_feed_sources(self, exporter, mock_feed):
        """Test that sources are exported correctly."""
        bundle = exporter.export_feed(mock_feed)

        assert len(bundle.sources) == 1
        source = bundle.sources[0]
        assert source.name == "Test RSS Feed"
        assert source.type == "rss"
        assert source.url == "https://example.com/feed.xml"
        assert source.config == {"max_items": 10}
        assert source.include_keywords == ["tech"]
        assert source.filter_mode == "title_only"

    def test_export_feed_prompt_template(self, exporter, mock_feed):
        """Test that prompt template is exported correctly."""
        bundle = exporter.export_feed(mock_feed)

        assert bundle.prompt_template is not None
        assert bundle.prompt_template.name == "Test Prompt"
        assert bundle.prompt_template.system_prompt == "You are helpful."
        assert bundle.prompt_template.user_prompt_template == "Summarize: {content}"
        assert bundle.prompt_template.target_length == 150

    def test_export_feed_report_template(self, exporter, mock_feed):
        """Test that report template is exported correctly."""
        bundle = exporter.export_feed(mock_feed)

        assert bundle.report_template is not None
        assert bundle.report_template.name == "Test Report"
        assert bundle.report_template.format == "markdown"
        assert bundle.report_template.template_content == "# Report\n\n{content}"

    def test_export_feed_schedule(self, exporter, mock_feed):
        """Test that schedule is exported correctly."""
        bundle = exporter.export_feed(mock_feed)

        assert bundle.schedule is not None
        assert bundle.schedule.cron == "0 9 * * *"

    def test_export_feed_without_schedule(self, exporter, mock_feed):
        """Test export when feed has no schedule."""
        mock_feed.schedule_cron = None
        bundle = exporter.export_feed(mock_feed)

        assert bundle.schedule is None

    def test_export_feed_without_templates(self, exporter, mock_feed):
        """Test export when feed has no templates."""
        mock_feed.prompt_template = None
        mock_feed.report_template = None
        bundle = exporter.export_feed(mock_feed)

        assert bundle.prompt_template is None
        assert bundle.report_template is None

    def test_export_feed_disabled_source_excluded(self, exporter, mock_feed):
        """Test that disabled sources are not exported."""
        mock_feed.feed_sources[0].enabled = False
        bundle = exporter.export_feed(mock_feed)

        assert len(bundle.sources) == 0

    def test_export_feed_with_category_and_tags(self, exporter, mock_feed):
        """Test export with category and tags."""
        bundle = exporter.export_feed(
            mock_feed,
            category="tech",
            tags=["ai", "news"],
        )

        assert bundle.category == "tech"
        assert bundle.tags == ["ai", "news"]

    def test_export_feed_with_custom_version(self, exporter, mock_feed):
        """Test export with custom version."""
        bundle = exporter.export_feed(mock_feed, version="2.0.0")

        assert bundle.version == "2.0.0"

    def test_export_feed_with_compatibility(self, exporter, mock_feed):
        """Test export with compatibility requirements."""
        bundle = exporter.export_feed(
            mock_feed,
            min_reconly_version="0.2.0",
            required_features=["ollama", "email"],
        )

        assert bundle.compatibility is not None
        assert bundle.compatibility.min_reconly_version == "0.2.0"
        assert bundle.compatibility.required_features == ["ollama", "email"]

    def test_export_feed_with_metadata(self, exporter, mock_feed):
        """Test export with metadata."""
        bundle = exporter.export_feed(
            mock_feed,
            license_name="MIT",
            homepage="https://example.com",
            repository="https://github.com/test/repo",
        )

        assert bundle.metadata is not None
        assert bundle.metadata.license == "MIT"
        assert bundle.metadata.homepage == "https://example.com"
        assert bundle.metadata.repository == "https://github.com/test/repo"

    def test_export_feed_sanitizes_output_config(self, exporter, mock_feed):
        """Test that output_config is sanitized (email addresses removed)."""
        bundle = exporter.export_feed(mock_feed)

        assert bundle.output_config is not None
        assert bundle.output_config.get("db") is True
        # Email should be sanitized - addresses removed
        email_config = bundle.output_config.get("email", {})
        assert "to" not in email_config
        assert email_config.get("enabled") is True

    def test_export_feed_language_from_prompt(self, exporter, mock_feed):
        """Test that language is inferred from prompt template."""
        mock_feed.prompt_template.language = "de"
        bundle = exporter.export_feed(mock_feed)

        assert bundle.language == "de"

    def test_export_feed_language_from_source(self, exporter, mock_feed):
        """Test that language is inferred from source when no prompt template."""
        mock_feed.prompt_template = None
        bundle = exporter.export_feed(mock_feed)

        assert bundle.language == "en"

    def test_export_feed_to_json(self, exporter, mock_feed):
        """Test export directly to JSON string."""
        json_str = exporter.export_feed_to_json(mock_feed)

        assert isinstance(json_str, str)
        assert '"schema_version": "1.0"' in json_str
        assert '"name": "Test Feed"' in json_str

    def test_export_feed_to_dict(self, exporter, mock_feed):
        """Test export directly to dictionary."""
        data = exporter.export_feed_to_dict(mock_feed)

        assert isinstance(data, dict)
        assert data["schema_version"] == "1.0"
        assert data["bundle"]["name"] == "Test Feed"
        assert len(data["bundle"]["sources"]) == 1


class TestExporterEdgeCases:
    """Edge case tests for exporter."""

    @pytest.fixture
    def exporter(self):
        return FeedBundleExporter()

    def test_export_feed_with_none_config(self, exporter):
        """Test export when source config is None."""
        mock_source = MagicMock()
        mock_source.name = "Test"
        mock_source.type = "rss"
        mock_source.url = "https://example.com/feed"
        mock_source.config = None
        mock_source.default_language = None
        mock_source.include_keywords = None
        mock_source.exclude_keywords = None
        mock_source.filter_mode = None
        mock_source.use_regex = None

        mock_feed_source = MagicMock()
        mock_feed_source.enabled = True
        mock_feed_source.source = mock_source

        mock_feed = MagicMock()
        mock_feed.name = "Test"
        mock_feed.description = None
        mock_feed.schedule_cron = None
        mock_feed.digest_mode = None
        mock_feed.output_config = None
        mock_feed.feed_sources = [mock_feed_source]
        mock_feed.prompt_template = None
        mock_feed.report_template = None

        bundle = exporter.export_feed(mock_feed)

        assert bundle.sources[0].config is None
        assert bundle.digest_mode == "individual"

    def test_export_feed_name_with_special_chars(self, exporter):
        """Test that feed names with special chars produce valid slugs."""
        mock_source = MagicMock()
        mock_source.name = "Test"
        mock_source.type = "rss"
        mock_source.url = "https://example.com"
        mock_source.config = None
        mock_source.default_language = None
        mock_source.include_keywords = None
        mock_source.exclude_keywords = None
        mock_source.filter_mode = None
        mock_source.use_regex = False

        mock_feed_source = MagicMock()
        mock_feed_source.enabled = True
        mock_feed_source.source = mock_source

        mock_feed = MagicMock()
        mock_feed.name = "AI & ML News! Daily @ 2024"
        mock_feed.description = None
        mock_feed.schedule_cron = None
        mock_feed.digest_mode = None
        mock_feed.output_config = None
        mock_feed.feed_sources = [mock_feed_source]
        mock_feed.prompt_template = None
        mock_feed.report_template = None

        bundle = exporter.export_feed(mock_feed)

        assert bundle.id == "ai-ml-news-daily-2024"

    def test_exporter_default_author(self):
        """Test exporter with default author settings."""
        exporter = FeedBundleExporter()

        assert exporter.author.name == "Anonymous"
        assert exporter.author.github is None
        assert exporter.author.email is None
