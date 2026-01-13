"""Tests for bundle dataclass and serialization."""
import pytest

from reconly_core.marketplace.bundle import (
    FeedBundle,
    BundleAuthor,
    BundleSource,
    BundlePromptTemplate,
    BundleReportTemplate,
    BundleSchedule,
    BundleCompatibility,
    BundleMetadata,
    slugify,
)


class TestSlugify:
    """Tests for the slugify function."""

    def test_basic_slugify(self):
        """Test basic name to slug conversion."""
        assert slugify("AI News Daily") == "ai-news-daily"

    def test_slugify_with_underscores(self):
        """Test slugify handles underscores."""
        assert slugify("sap_analyst_brief") == "sap-analyst-brief"

    def test_slugify_removes_special_chars(self):
        """Test slugify removes special characters."""
        assert slugify("AI News! Daily @ 2024") == "ai-news-daily-2024"

    def test_slugify_multiple_spaces(self):
        """Test slugify handles multiple spaces."""
        assert slugify("AI   News   Daily") == "ai-news-daily"

    def test_slugify_preserves_numbers(self):
        """Test slugify preserves numbers."""
        assert slugify("Tech News 123") == "tech-news-123"

    def test_slugify_trims_hyphens(self):
        """Test slugify trims leading/trailing hyphens."""
        assert slugify("--test--name--") == "test-name"

    def test_slugify_empty_string(self):
        """Test slugify with empty string."""
        assert slugify("") == ""


class TestBundleAuthor:
    """Tests for BundleAuthor dataclass."""

    def test_to_dict_minimal(self):
        """Test to_dict with only name."""
        author = BundleAuthor(name="John Doe")
        result = author.to_dict()
        assert result == {"name": "John Doe"}

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        author = BundleAuthor(
            name="John Doe",
            github="johndoe",
            email="john@example.com",
        )
        result = author.to_dict()
        assert result == {
            "name": "John Doe",
            "github": "johndoe",
            "email": "john@example.com",
        }

    def test_from_dict_minimal(self):
        """Test from_dict with only name."""
        author = BundleAuthor.from_dict({"name": "Jane Doe"})
        assert author.name == "Jane Doe"
        assert author.github is None
        assert author.email is None

    def test_from_dict_missing_name(self):
        """Test from_dict defaults to Anonymous if name is missing."""
        author = BundleAuthor.from_dict({})
        assert author.name == "Anonymous"


class TestBundleSource:
    """Tests for BundleSource dataclass."""

    def test_to_dict_minimal(self):
        """Test to_dict with required fields only."""
        source = BundleSource(
            name="TechCrunch",
            type="rss",
            url="https://techcrunch.com/feed/",
        )
        result = source.to_dict()
        assert result == {
            "name": "TechCrunch",
            "type": "rss",
            "url": "https://techcrunch.com/feed/",
        }

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        source = BundleSource(
            name="TechCrunch",
            type="rss",
            url="https://techcrunch.com/feed/",
            config={"max_items": 10},
            default_language="en",
            include_keywords=["AI", "startups"],
            exclude_keywords=["spam"],
            filter_mode="title_only",
            use_regex=True,
        )
        result = source.to_dict()
        assert result["config"] == {"max_items": 10}
        assert result["include_keywords"] == ["AI", "startups"]
        assert result["use_regex"] is True

    def test_from_dict(self):
        """Test from_dict creates source correctly."""
        data = {
            "name": "YouTube Tech",
            "type": "youtube",
            "url": "https://youtube.com/@techreview",
            "config": {"playlist_id": "abc123"},
        }
        source = BundleSource.from_dict(data)
        assert source.name == "YouTube Tech"
        assert source.type == "youtube"
        assert source.config == {"playlist_id": "abc123"}
        assert source.use_regex is False  # default


class TestBundlePromptTemplate:
    """Tests for BundlePromptTemplate dataclass."""

    def test_to_dict(self):
        """Test prompt template serialization."""
        template = BundlePromptTemplate(
            name="Summary Template",
            system_prompt="You are a helpful assistant.",
            user_prompt_template="Summarize: {content}",
            description="Creates brief summaries",
            language="en",
            target_length=200,
        )
        result = template.to_dict()
        assert result["name"] == "Summary Template"
        assert result["system_prompt"] == "You are a helpful assistant."
        assert result["target_length"] == 200

    def test_from_dict_defaults(self):
        """Test from_dict applies defaults."""
        data = {
            "name": "Test",
            "system_prompt": "Test system",
            "user_prompt_template": "Test user",
        }
        template = BundlePromptTemplate.from_dict(data)
        assert template.language == "en"
        assert template.target_length == 150


class TestBundleReportTemplate:
    """Tests for BundleReportTemplate dataclass."""

    def test_to_dict(self):
        """Test report template serialization."""
        template = BundleReportTemplate(
            name="Markdown Report",
            format="markdown",
            template_content="# Report\n\n{content}",
            description="Standard markdown format",
        )
        result = template.to_dict()
        assert result["name"] == "Markdown Report"
        assert result["format"] == "markdown"
        assert "description" in result

    def test_from_dict(self):
        """Test from_dict creates template."""
        data = {
            "name": "HTML Report",
            "format": "html",
            "template_content": "<html>{content}</html>",
        }
        template = BundleReportTemplate.from_dict(data)
        assert template.name == "HTML Report"
        assert template.format == "html"
        assert template.description is None


class TestFeedBundle:
    """Tests for FeedBundle dataclass."""

    @pytest.fixture
    def minimal_bundle(self):
        """Create a minimal valid bundle."""
        return FeedBundle(
            id="test-feed",
            name="Test Feed",
            version="1.0.0",
            sources=[
                BundleSource(
                    name="Test Source",
                    type="rss",
                    url="https://example.com/feed.xml",
                ),
            ],
        )

    @pytest.fixture
    def full_bundle(self):
        """Create a full bundle with all fields."""
        return FeedBundle(
            id="ai-news-daily",
            name="AI News Daily",
            version="1.0.0",
            description="Daily AI news digest",
            author=BundleAuthor(name="John Doe", github="johndoe"),
            category="tech",
            tags=["ai", "news", "daily"],
            language="en",
            sources=[
                BundleSource(
                    name="TechCrunch AI",
                    type="rss",
                    url="https://techcrunch.com/category/ai/feed/",
                ),
                BundleSource(
                    name="MIT Tech Review",
                    type="rss",
                    url="https://technologyreview.com/feed/",
                ),
            ],
            prompt_template=BundlePromptTemplate(
                name="AI Summary",
                system_prompt="You are an AI news analyst.",
                user_prompt_template="Summarize this AI news: {content}",
                target_length=200,
            ),
            report_template=BundleReportTemplate(
                name="Daily Digest",
                format="markdown",
                template_content="# Daily AI News\n\n{content}",
            ),
            schedule=BundleSchedule(cron="0 9 * * *", description="Daily at 9 AM"),
            output_config={"db": True, "email": {"enabled": True}},
            digest_mode="per_source",
            compatibility=BundleCompatibility(
                min_reconly_version="0.2.0",
                required_features=["ollama"],
            ),
            metadata=BundleMetadata(
                license="MIT",
                homepage="https://example.com",
            ),
        )

    def test_to_dict_minimal(self, minimal_bundle):
        """Test minimal bundle serialization."""
        result = minimal_bundle.to_dict()

        assert result["schema_version"] == "1.0"
        assert "bundle" in result
        assert result["bundle"]["id"] == "test-feed"
        assert result["bundle"]["name"] == "Test Feed"
        assert result["bundle"]["version"] == "1.0.0"
        assert len(result["bundle"]["sources"]) == 1

    def test_to_dict_full(self, full_bundle):
        """Test full bundle serialization."""
        result = full_bundle.to_dict()

        assert result["schema_version"] == "1.0"
        assert result["bundle"]["id"] == "ai-news-daily"
        assert result["bundle"]["category"] == "tech"
        assert result["bundle"]["tags"] == ["ai", "news", "daily"]
        assert "prompt_template" in result["bundle"]
        assert "report_template" in result["bundle"]
        assert result["bundle"]["digest_mode"] == "per_source"
        assert "compatibility" in result
        assert "metadata" in result

    def test_from_dict_minimal(self):
        """Test deserialization of minimal bundle."""
        data = {
            "schema_version": "1.0",
            "bundle": {
                "id": "test-feed",
                "name": "Test Feed",
                "version": "1.0.0",
                "sources": [
                    {"name": "Source1", "type": "rss", "url": "https://example.com/feed.xml"},
                ],
            },
        }
        bundle = FeedBundle.from_dict(data)

        assert bundle.id == "test-feed"
        assert bundle.name == "Test Feed"
        assert bundle.version == "1.0.0"
        assert len(bundle.sources) == 1
        assert bundle.digest_mode == "individual"  # default

    def test_from_dict_full(self, full_bundle):
        """Test round-trip serialization."""
        data = full_bundle.to_dict()
        restored = FeedBundle.from_dict(data)

        assert restored.id == full_bundle.id
        assert restored.name == full_bundle.name
        assert restored.category == full_bundle.category
        assert len(restored.sources) == len(full_bundle.sources)
        assert restored.prompt_template is not None
        assert restored.report_template is not None
        assert restored.compatibility.min_reconly_version == "0.2.0"
        assert restored.metadata.license == "MIT"

    def test_from_feed_name(self):
        """Test creating bundle with auto-generated slug."""
        bundle = FeedBundle.from_feed_name(
            name="AI News Daily",
            version="1.0.0",
            sources=[
                BundleSource(name="Test", type="rss", url="https://example.com/feed"),
            ],
        )
        assert bundle.id == "ai-news-daily"
        assert bundle.name == "AI News Daily"

    def test_provenance_string(self, minimal_bundle):
        """Test provenance string generation."""
        assert minimal_bundle.provenance_string == "test-feed@1.0.0"

    def test_to_dict_excludes_default_digest_mode(self, minimal_bundle):
        """Test that default digest_mode is not included in serialization."""
        result = minimal_bundle.to_dict()
        assert "digest_mode" not in result["bundle"]

    def test_to_dict_includes_non_default_digest_mode(self, full_bundle):
        """Test that non-default digest_mode is included."""
        result = full_bundle.to_dict()
        assert result["bundle"]["digest_mode"] == "per_source"
