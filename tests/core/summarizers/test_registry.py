"""Tests for provider registry."""
import pytest
from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.summarizers.registry import (
    register_provider,
    get_provider,
    get_provider_entry,
    list_providers,
    get_provider_by_capability,
    is_provider_registered,
    is_provider_extension,
    _PROVIDER_REGISTRY
)
from reconly_core.summarizers.base import BaseSummarizer
from reconly_core.summarizers.capabilities import ProviderCapabilities
from reconly_core.services.settings_registry import SETTINGS_REGISTRY


class TestProviderRegistry:
    """Test cases for provider registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        _PROVIDER_REGISTRY.clear()

    def test_register_provider_decorator(self):
        """Test that @register_provider decorator registers a provider."""
        @register_provider('test-provider')
        class TestSummarizer(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        assert is_provider_registered('test-provider')
        assert get_provider('test-provider') == TestSummarizer

    def test_register_provider_appears_in_list(self):
        """Test that registered provider appears in list_providers()."""
        @register_provider('test-provider')
        class TestSummarizer(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        providers = list_providers()
        assert 'test-provider' in providers

    def test_get_provider_raises_on_unknown(self):
        """Test that get_provider raises ValueError with helpful message for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            get_provider('nonexistent-provider')

        error_msg = str(exc_info.value)
        assert 'nonexistent-provider' in error_msg
        assert 'Available providers' in error_msg
        assert 'ADDING_PROVIDERS.md' in error_msg

    def test_get_provider_error_lists_available(self):
        """Test that error message lists all available providers."""
        @register_provider('provider-a')
        class ProviderA(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'provider-a'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('provider-b')
        class ProviderB(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'provider-b'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        with pytest.raises(ValueError) as exc_info:
            get_provider('nonexistent')

        error_msg = str(exc_info.value)
        assert 'provider-a' in error_msg
        assert 'provider-b' in error_msg

    def test_register_provider_override_warns(self, caplog):
        """Test that overriding a provider logs a warning."""
        @register_provider('foo')
        class ProviderOne(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'foo'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('foo')
        class ProviderTwo(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'foo'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        # Check that warning was logged
        assert any('already registered' in record.message.lower() for record in caplog.records)

        # Check that new provider replaced the old one
        assert get_provider('foo') == ProviderTwo

    def test_register_non_basesummarizer_raises(self):
        """Test that registering a non-BaseSummarizer class raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            @register_provider('invalid')
            class NotASummarizer:
                pass

        assert 'must inherit from BaseSummarizer' in str(exc_info.value)

    def test_get_provider_by_capability_local(self):
        """Test finding providers by is_local capability."""
        @register_provider('local-provider')
        class LocalProvider(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'local-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities(is_local=True)

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('cloud-provider')
        class CloudProvider(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'cloud-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities(is_local=False)

            def is_available(self):
                return True

            def validate_config(self):
                return []

        local_providers = get_provider_by_capability('is_local', True)
        assert 'local-provider' in local_providers
        assert 'cloud-provider' not in local_providers

    def test_get_provider_by_capability_no_api_key(self):
        """Test finding providers that don't require API keys."""
        @register_provider('no-key-provider')
        class NoKeyProvider(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'no-key-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities(requires_api_key=False)

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('needs-key-provider')
        class NeedsKeyProvider(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'needs-key-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities(requires_api_key=True)

            def is_available(self):
                return True

            def validate_config(self):
                return []

        no_key_providers = get_provider_by_capability('requires_api_key', False)
        assert 'no-key-provider' in no_key_providers
        assert 'needs-key-provider' not in no_key_providers

    def test_is_provider_registered(self):
        """Test is_provider_registered helper function."""
        assert not is_provider_registered('test-provider')

        @register_provider('test-provider')
        class TestProvider(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-provider'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        assert is_provider_registered('test-provider')

    def test_list_providers_empty(self):
        """Test that list_providers returns empty list when no providers registered."""
        _PROVIDER_REGISTRY.clear()
        assert list_providers() == []

    def test_multiple_providers_registration(self):
        """Test registering multiple providers."""
        @register_provider('provider-1')
        class Provider1(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'provider-1'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('provider-2')
        class Provider2(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'provider-2'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        @register_provider('provider-3')
        class Provider3(BaseSummarizer):
            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'provider-3'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        providers = list_providers()
        assert len(providers) == 3
        assert 'provider-1' in providers
        assert 'provider-2' in providers
        assert 'provider-3' in providers

    def test_provider_with_config_schema_registers_settings(self):
        """Test that provider with config schema auto-registers settings."""
        # Clear any existing settings with this prefix
        keys_to_remove = [k for k in SETTINGS_REGISTRY.keys() if k.startswith('provider.test-schema')]
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

        @register_provider('test-schema')
        class TestSchemaProvider(BaseSummarizer):
            def __init__(self, api_key=None):
                super().__init__(api_key)

            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-schema'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities(requires_api_key=True)

            def is_available(self):
                return True

            def validate_config(self):
                return []

            def get_config_schema(self):
                return ProviderConfigSchema(
                    fields=[
                        ConfigField(
                            key="api_key",
                            type="string",
                            label="API Key",
                            description="Test API key",
                            env_var="TEST_SCHEMA_API_KEY",
                            editable=False,
                            secret=True,
                            required=True,
                        ),
                        ConfigField(
                            key="model",
                            type="string",
                            label="Model",
                            description="Test model",
                            default="test-model",
                            editable=True,
                        ),
                    ],
                    requires_api_key=True,
                )

        # Verify provider is registered
        assert is_provider_registered('test-schema')

        # Verify config schema is stored in registry entry
        entry = get_provider_entry('test-schema')
        assert entry.config_schema is not None
        assert len(entry.config_schema.fields) == 2

        # Verify settings were auto-registered with correct pattern
        assert 'provider.test-schema.api_key' in SETTINGS_REGISTRY
        assert 'provider.test-schema.model' in SETTINGS_REGISTRY

        # Verify api_key settings
        api_key_setting = SETTINGS_REGISTRY['provider.test-schema.api_key']
        assert api_key_setting.category == 'provider'
        assert api_key_setting.env_var == 'TEST_SCHEMA_API_KEY'
        assert api_key_setting.editable is False
        assert api_key_setting.secret is True

        # Verify model settings
        model_setting = SETTINGS_REGISTRY['provider.test-schema.model']
        assert model_setting.category == 'provider'
        assert model_setting.default == 'test-model'
        assert model_setting.editable is True
        assert model_setting.secret is False

    def test_provider_without_config_schema_no_settings(self):
        """Test that provider without config schema doesn't register settings."""
        # Clear any existing settings with this prefix
        keys_to_remove = [k for k in SETTINGS_REGISTRY.keys() if k.startswith('provider.test-no-schema')]
        for key in keys_to_remove:
            del SETTINGS_REGISTRY[key]

        @register_provider('test-no-schema')
        class TestNoSchemaProvider(BaseSummarizer):
            def __init__(self, api_key=None):
                super().__init__(api_key)

            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-no-schema'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []
            # Note: No get_config_schema() override - uses base class default

        # Verify provider is registered
        assert is_provider_registered('test-no-schema')

        # Verify no settings were auto-registered (base class returns empty schema)
        settings_for_provider = [k for k in SETTINGS_REGISTRY.keys() if k.startswith('provider.test-no-schema')]
        assert len(settings_for_provider) == 0

    def test_extension_provider_registration(self):
        """Test that extension providers can be registered with is_extension flag."""
        @register_provider('test-extension', is_extension=True)
        class TestExtensionProvider(BaseSummarizer):
            def __init__(self, api_key=None):
                super().__init__(api_key)

            def summarize(self, content_data, language='de'):
                return {}

            def get_provider_name(self):
                return 'test-extension'

            def estimate_cost(self, content_length):
                return 0.0

            @classmethod
            def get_capabilities(cls):
                return ProviderCapabilities()

            def is_available(self):
                return True

            def validate_config(self):
                return []

        # Verify provider is registered
        assert is_provider_registered('test-extension')

        # Verify extension flag
        assert is_provider_extension('test-extension') is True

        # Verify entry has is_extension
        entry = get_provider_entry('test-extension')
        assert entry.is_extension is True
