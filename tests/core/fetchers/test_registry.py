"""Tests for fetcher registry."""
import pytest

from reconly_core.fetchers.registry import (
    register_fetcher,
    get_fetcher_class,
    list_fetchers,
    is_fetcher_registered,
    detect_fetcher,
    _FETCHER_REGISTRY
)
from reconly_core.fetchers.base import BaseFetcher, ConfigField, FetcherConfigSchema
from reconly_core.services.settings_registry import SETTINGS_REGISTRY


class TestFetcherRegistry:
    """Test cases for fetcher registry functionality."""

    def setup_method(self):
        """Store original registry and clear it before each test."""
        self._original_registry = _FETCHER_REGISTRY.copy()
        self._original_settings = set(SETTINGS_REGISTRY.keys())
        _FETCHER_REGISTRY.clear()

    def teardown_method(self):
        """Restore original registry after each test."""
        _FETCHER_REGISTRY.clear()
        _FETCHER_REGISTRY.update(self._original_registry)
        # Clean up any settings added during tests
        keys_to_remove = set(SETTINGS_REGISTRY.keys()) - self._original_settings
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

    def test_register_fetcher_decorator(self):
        """Test that @register_fetcher decorator registers a fetcher."""
        @register_fetcher('test-source')
        class TestFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'test-source'

        assert is_fetcher_registered('test-source')
        assert get_fetcher_class('test-source') == TestFetcher

    def test_register_fetcher_appears_in_list(self):
        """Test that registered fetcher appears in list_fetchers()."""
        @register_fetcher('test-source')
        class TestFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'test-source'

        sources = list_fetchers()
        assert 'test-source' in sources

    def test_get_fetcher_class_raises_on_unknown(self):
        """Test that get_fetcher_class raises ValueError for unknown source."""
        with pytest.raises(ValueError) as exc_info:
            get_fetcher_class('nonexistent-source')

        error_msg = str(exc_info.value)
        assert 'nonexistent-source' in error_msg
        assert 'Available types' in error_msg
        assert 'ADDING_FETCHERS.md' in error_msg

    def test_register_non_basefetcher_raises(self):
        """Test that registering a non-BaseFetcher class raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            @register_fetcher('invalid')
            class NotAFetcher:
                pass

        assert 'must inherit from BaseFetcher' in str(exc_info.value)

    def test_register_fetcher_override_warns(self, caplog):
        """Test that overriding a fetcher logs a warning."""
        @register_fetcher('foo')
        class FetcherOne(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'foo'

        @register_fetcher('foo')
        class FetcherTwo(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'foo'

        # Check that warning was logged
        assert any('already registered' in record.message.lower() for record in caplog.records)

        # Check that new fetcher replaced the old one
        assert get_fetcher_class('foo') == FetcherTwo

    def test_is_fetcher_registered(self):
        """Test is_fetcher_registered helper function."""
        assert not is_fetcher_registered('test-source')

        @register_fetcher('test-source')
        class TestFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'test-source'

        assert is_fetcher_registered('test-source')

    def test_list_fetchers_empty(self):
        """Test that list_fetchers returns empty list when no fetchers registered."""
        assert list_fetchers() == []

    def test_multiple_fetchers_registration(self):
        """Test registering multiple fetchers."""
        @register_fetcher('source-1')
        class Fetcher1(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'source-1'

        @register_fetcher('source-2')
        class Fetcher2(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'source-2'

        sources = list_fetchers()
        assert len(sources) == 2
        assert 'source-1' in sources
        assert 'source-2' in sources

    def test_detect_fetcher_finds_matching(self):
        """Test that detect_fetcher finds fetcher that can handle URL."""
        @register_fetcher('video')
        class VideoFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'video'

            def can_handle(self, url):
                return 'video.example.com' in url

        @register_fetcher('blog')
        class BlogFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'blog'

            def can_handle(self, url):
                return 'blog.example.com' in url

        fetcher = detect_fetcher('https://video.example.com/watch')
        assert fetcher is not None
        assert fetcher.get_source_type() == 'video'

        fetcher = detect_fetcher('https://blog.example.com/post')
        assert fetcher is not None
        assert fetcher.get_source_type() == 'blog'

    def test_detect_fetcher_returns_none_when_no_match(self):
        """Test that detect_fetcher returns None when no fetcher can handle URL."""
        @register_fetcher('specific')
        class SpecificFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'specific'

            def can_handle(self, url):
                return 'specific.example.com' in url

        fetcher = detect_fetcher('https://other.example.com/page')
        assert fetcher is None

    def test_register_fetcher_auto_registers_settings(self):
        """Test that @register_fetcher automatically registers settings from config schema."""
        @register_fetcher('auto-settings')
        class AutoSettingsFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'auto-settings'

            def get_config_schema(self):
                return FetcherConfigSchema(
                    fields=[
                        ConfigField(
                            key="timeout",
                            type="integer",
                            label="Request Timeout",
                            description="HTTP request timeout in seconds",
                            default=30,
                            required=False,
                        ),
                        ConfigField(
                            key="user_agent",
                            type="string",
                            label="User Agent",
                            description="Custom User-Agent header",
                            default=None,
                            required=True,
                        ),
                    ],
                )

        # Verify fetcher is registered
        assert is_fetcher_registered('auto-settings')

        # Verify settings were auto-registered
        assert "fetch.auto-settings.enabled" in SETTINGS_REGISTRY
        assert "fetch.auto-settings.timeout" in SETTINGS_REGISTRY
        assert "fetch.auto-settings.user_agent" in SETTINGS_REGISTRY

        # Verify setting properties
        enabled_setting = SETTINGS_REGISTRY["fetch.auto-settings.enabled"]
        assert enabled_setting.type is bool
        assert enabled_setting.default is False  # Has required field

        timeout_setting = SETTINGS_REGISTRY["fetch.auto-settings.timeout"]
        assert timeout_setting.type is int
        assert timeout_setting.default == 30
        assert timeout_setting.description == "HTTP request timeout in seconds"

        user_agent_setting = SETTINGS_REGISTRY["fetch.auto-settings.user_agent"]
        assert user_agent_setting.type is str
        assert user_agent_setting.default is None

    def test_register_fetcher_no_settings_for_empty_schema(self):
        """Test that fetcher with empty schema only registers enabled setting."""
        @register_fetcher('no-schema')
        class NoSchemaFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'no-schema'

            # Uses default get_config_schema() which returns empty schema

        # Fetcher should be registered
        assert is_fetcher_registered('no-schema')

        # Only the enabled setting should be registered (always added for all fetchers)
        assert "fetch.no-schema.enabled" in SETTINGS_REGISTRY
        # But no other custom settings from schema
        assert "fetch.no-schema.timeout" not in SETTINGS_REGISTRY

    def test_fetcher_config_schema_stored_in_registry_entry(self):
        """Test that config schema is stored in the registry entry."""
        @register_fetcher('schema-stored')
        class SchemaStoredFetcher(BaseFetcher):
            def fetch(self, url, since=None, max_items=None, **kwargs):
                return []

            def get_source_type(self):
                return 'schema-stored'

            def get_config_schema(self):
                return FetcherConfigSchema(
                    fields=[
                        ConfigField(
                            key="api_key",
                            type="string",
                            label="API Key",
                            description="API key for authentication",
                            default=None,
                            required=True,
                        ),
                    ],
                )

        # Verify config schema is stored in registry entry
        entry = _FETCHER_REGISTRY['schema-stored']
        assert entry.config_schema is not None
        assert len(entry.config_schema.fields) == 1
        assert entry.config_schema.fields[0].key == "api_key"
