"""Tests for bundle schema validation."""
import pytest

from reconly_core.marketplace.validator import BundleValidator, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_initial_state(self):
        """Test initial state is valid with empty lists."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        """Test adding an error marks result invalid."""
        result = ValidationResult(is_valid=True)
        result.add_error("Test error")
        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding a warning does not affect validity."""
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        assert result.is_valid is True
        assert "Test warning" in result.warnings


class TestBundleValidator:
    """Tests for BundleValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return BundleValidator()

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
                    {"name": "Test Source", "type": "rss", "url": "https://example.com/feed.xml"},
                ],
            },
        }

    def test_valid_minimal_bundle(self, validator, valid_bundle):
        """Test validation of a minimal valid bundle."""
        result = validator.validate(valid_bundle)
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_schema_version(self, validator, valid_bundle):
        """Test error when schema_version is missing."""
        del valid_bundle["schema_version"]
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("schema_version" in e for e in result.errors)

    def test_unsupported_schema_version(self, validator, valid_bundle):
        """Test error for unsupported schema version."""
        valid_bundle["schema_version"] = "2.0"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("Unsupported schema version" in e for e in result.errors)

    def test_missing_bundle_field(self, validator):
        """Test error when bundle field is missing."""
        data = {"schema_version": "1.0"}
        result = validator.validate(data)
        assert result.is_valid is False
        assert any("bundle" in e for e in result.errors)

    # =========================================================================
    # ID Validation
    # =========================================================================

    def test_valid_id_format(self, validator, valid_bundle):
        """Test valid kebab-case ID."""
        valid_bundle["bundle"]["id"] = "my-test-feed-123"
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_invalid_id_uppercase(self, validator, valid_bundle):
        """Test error for uppercase in ID."""
        valid_bundle["bundle"]["id"] = "My-Test-Feed"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("kebab-case" in e for e in result.errors)

    def test_invalid_id_spaces(self, validator, valid_bundle):
        """Test error for spaces in ID."""
        valid_bundle["bundle"]["id"] = "my test feed"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Version Validation
    # =========================================================================

    def test_valid_version_format(self, validator, valid_bundle):
        """Test valid semantic version."""
        valid_bundle["bundle"]["version"] = "2.1.3"
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_invalid_version_format(self, validator, valid_bundle):
        """Test error for invalid version format."""
        valid_bundle["bundle"]["version"] = "1.0"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("semantic version" in e for e in result.errors)

    def test_invalid_version_not_string(self, validator, valid_bundle):
        """Test error when version is not a string."""
        valid_bundle["bundle"]["version"] = 1.0
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Name Validation
    # =========================================================================

    def test_empty_name(self, validator, valid_bundle):
        """Test error for empty name."""
        valid_bundle["bundle"]["name"] = ""
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("empty" in e for e in result.errors)

    def test_name_too_long(self, validator, valid_bundle):
        """Test error for name exceeding max length."""
        valid_bundle["bundle"]["name"] = "x" * 256
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("255" in e for e in result.errors)

    # =========================================================================
    # Sources Validation
    # =========================================================================

    def test_empty_sources_array(self, validator, valid_bundle):
        """Test error for empty sources array."""
        valid_bundle["bundle"]["sources"] = []
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("at least one source" in e for e in result.errors)

    def test_sources_not_array(self, validator, valid_bundle):
        """Test error when sources is not an array."""
        valid_bundle["bundle"]["sources"] = "not an array"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("array" in e for e in result.errors)

    def test_source_missing_required_fields(self, validator, valid_bundle):
        """Test error for source missing required fields."""
        valid_bundle["bundle"]["sources"] = [{"name": "Test"}]
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("type" in e for e in result.errors)
        assert any("url" in e for e in result.errors)

    def test_source_invalid_type(self, validator, valid_bundle):
        """Test error for invalid source type."""
        valid_bundle["bundle"]["sources"][0]["type"] = "invalid"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("invalid" in e.lower() for e in result.errors)

    def test_source_valid_types(self, validator, valid_bundle):
        """Test all valid source types are accepted."""
        for source_type in ["rss", "youtube", "website", "blog", "podcast"]:
            valid_bundle["bundle"]["sources"][0]["type"] = source_type
            result = validator.validate(valid_bundle)
            assert result.is_valid is True, f"Type {{ source_type }} should be valid"

    def test_source_url_warning(self, validator, valid_bundle):
        """Test warning for non-http URL."""
        valid_bundle["bundle"]["sources"][0]["url"] = "ftp://example.com/feed"
        result = validator.validate(valid_bundle)
        # Should still be valid but with warning
        assert len(result.warnings) > 0

    def test_source_filter_mode_valid(self, validator, valid_bundle):
        """Test valid filter modes."""
        for mode in ["title_only", "content", "both"]:
            valid_bundle["bundle"]["sources"][0]["filter_mode"] = mode
            result = validator.validate(valid_bundle)
            assert result.is_valid is True

    def test_source_filter_mode_invalid(self, validator, valid_bundle):
        """Test invalid filter mode."""
        valid_bundle["bundle"]["sources"][0]["filter_mode"] = "invalid"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Prompt Template Validation
    # =========================================================================

    def test_prompt_template_valid(self, validator, valid_bundle):
        """Test valid prompt template."""
        valid_bundle["bundle"]["prompt_template"] = {
            "name": "Test Template",
            "system_prompt": "You are helpful.",
            "user_prompt_template": "Summarize: {{ content }}",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_prompt_template_missing_fields(self, validator, valid_bundle):
        """Test error for prompt template missing required fields."""
        valid_bundle["bundle"]["prompt_template"] = {"name": "Test"}
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("system_prompt" in e for e in result.errors)

    def test_prompt_template_target_length_out_of_range(self, validator, valid_bundle):
        """Test error for target_length out of range."""
        valid_bundle["bundle"]["prompt_template"] = {
            "name": "Test",
            "system_prompt": "Test",
            "user_prompt_template": "Test",
            "target_length": 5,  # Too small
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("target_length" in e for e in result.errors)

    # =========================================================================
    # Report Template Validation
    # =========================================================================

    def test_report_template_valid(self, validator, valid_bundle):
        """Test valid report template."""
        valid_bundle["bundle"]["report_template"] = {
            "name": "Test Report",
            "format": "markdown",
            "template_content": "# Report\n{{ content }}",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_report_template_invalid_format(self, validator, valid_bundle):
        """Test error for invalid report format."""
        valid_bundle["bundle"]["report_template"] = {
            "name": "Test",
            "format": "pdf",  # Not supported
            "template_content": "test",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("format" in e for e in result.errors)

    # =========================================================================
    # Category Validation
    # =========================================================================

    def test_valid_categories(self, validator, valid_bundle):
        """Test all valid categories are accepted."""
        categories = ["news", "finance", "tech", "science", "entertainment", "sports", "business", "other"]
        for cat in categories:
            valid_bundle["bundle"]["category"] = cat
            result = validator.validate(valid_bundle)
            assert result.is_valid is True, f"Category {cat} should be valid"

    def test_invalid_category(self, validator, valid_bundle):
        """Test error for invalid category."""
        valid_bundle["bundle"]["category"] = "invalid-category"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Tags Validation
    # =========================================================================

    def test_tags_valid(self, validator, valid_bundle):
        """Test valid tags array."""
        valid_bundle["bundle"]["tags"] = ["ai", "news", "daily"]
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_tags_too_many(self, validator, valid_bundle):
        """Test error for too many tags."""
        valid_bundle["bundle"]["tags"] = [f"tag{i}" for i in range(15)]
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("10" in e for e in result.errors)

    def test_tags_not_strings(self, validator, valid_bundle):
        """Test error for non-string tags."""
        valid_bundle["bundle"]["tags"] = ["valid", 123, "also-valid"]
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Language Validation
    # =========================================================================

    def test_language_valid(self, validator, valid_bundle):
        """Test valid language codes."""
        for lang in ["en", "de", "fr", "es"]:
            valid_bundle["bundle"]["language"] = lang
            result = validator.validate(valid_bundle)
            assert result.is_valid is True

    def test_language_invalid(self, validator, valid_bundle):
        """Test error for invalid language code."""
        valid_bundle["bundle"]["language"] = "english"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("2-letter" in e for e in result.errors)

    # =========================================================================
    # Digest Mode Validation
    # =========================================================================

    def test_digest_mode_valid(self, validator, valid_bundle):
        """Test valid digest modes."""
        for mode in ["individual", "per_source", "all_sources"]:
            valid_bundle["bundle"]["digest_mode"] = mode
            result = validator.validate(valid_bundle)
            assert result.is_valid is True

    def test_digest_mode_invalid(self, validator, valid_bundle):
        """Test error for invalid digest mode."""
        valid_bundle["bundle"]["digest_mode"] = "invalid"
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Schedule Validation
    # =========================================================================

    def test_schedule_valid_cron(self, validator, valid_bundle):
        """Test valid cron expression."""
        valid_bundle["bundle"]["schedule"] = {"cron": "0 9 * * *"}
        result = validator.validate(valid_bundle)
        assert result.is_valid is True
        assert len(result.warnings) == 0

    def test_schedule_invalid_cron_parts(self, validator, valid_bundle):
        """Test warning for cron with wrong number of parts."""
        valid_bundle["bundle"]["schedule"] = {"cron": "0 9 * *"}  # 4 parts
        result = validator.validate(valid_bundle)
        # Should produce a warning, not an error
        assert any("5 parts" in w for w in result.warnings)

    # =========================================================================
    # Compatibility Validation
    # =========================================================================

    def test_compatibility_valid(self, validator, valid_bundle):
        """Test valid compatibility section."""
        valid_bundle["compatibility"] = {
            "min_reconly_version": "0.2.0",
            "required_features": ["ollama", "email"],
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_compatibility_invalid_version(self, validator, valid_bundle):
        """Test error for invalid min version format."""
        valid_bundle["compatibility"] = {
            "min_reconly_version": "0.2",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is False

    # =========================================================================
    # Metadata Validation
    # =========================================================================

    def test_metadata_valid(self, validator, valid_bundle):
        """Test valid metadata section."""
        valid_bundle["metadata"] = {
            "license": "MIT",
            "homepage": "https://example.com",
            "repository": "https://github.com/user/repo",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_metadata_invalid_url_warning(self, validator, valid_bundle):
        """Test warning for non-URL homepage."""
        valid_bundle["metadata"] = {
            "homepage": "not-a-url",
        }
        result = validator.validate(valid_bundle)
        # Should produce warning, not error
        assert any("URL" in w for w in result.warnings)

    # =========================================================================
    # Author Validation
    # =========================================================================

    def test_author_valid(self, validator, valid_bundle):
        """Test valid author section."""
        valid_bundle["bundle"]["author"] = {
            "name": "John Doe",
            "github": "johndoe",
            "email": "john@example.com",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is True

    def test_author_missing_name(self, validator, valid_bundle):
        """Test error for author without name."""
        valid_bundle["bundle"]["author"] = {
            "github": "johndoe",
        }
        result = validator.validate(valid_bundle)
        assert result.is_valid is False
        assert any("name" in e for e in result.errors)

    # =========================================================================
    # Full Bundle Validation
    # =========================================================================

    def test_full_valid_bundle(self, validator):
        """Test validation of a complete bundle with all optional fields."""
        full_bundle = {
            "schema_version": "1.0",
            "bundle": {
                "id": "ai-news-daily",
                "name": "AI News Daily",
                "version": "1.0.0",
                "description": "Daily AI news digest",
                "category": "tech",
                "language": "en",
                "tags": ["ai", "news", "daily"],
                "author": {
                    "name": "John Doe",
                    "github": "johndoe",
                },
                "sources": [
                    {
                        "name": "TechCrunch AI",
                        "type": "rss",
                        "url": "https://techcrunch.com/category/ai/feed/",
                        "include_keywords": ["AI", "ML"],
                        "filter_mode": "title_only",
                    },
                ],
                "prompt_template": {
                    "name": "AI Summary",
                    "system_prompt": "You are an AI news analyst.",
                    "user_prompt_template": "Summarize: {{ content }}",
                    "target_length": 200,
                },
                "report_template": {
                    "name": "Daily Report",
                    "format": "markdown",
                    "template_content": "# Report\n\n{{ content }}",
                },
                "schedule": {
                    "cron": "0 9 * * *",
                    "description": "Daily at 9 AM",
                },
                "digest_mode": "per_source",
            },
            "compatibility": {
                "min_reconly_version": "0.2.0",
                "required_features": ["ollama"],
            },
            "metadata": {
                "license": "MIT",
                "homepage": "https://example.com",
            },
        }
        result = validator.validate(full_bundle)
        assert result.is_valid is True
        assert len(result.errors) == 0
