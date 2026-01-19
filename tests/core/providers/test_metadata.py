"""Tests for provider metadata."""
import os
from unittest import mock

import pytest

from reconly_core.providers.metadata import ProviderMetadata


class TestProviderMetadata:
    """Test cases for ProviderMetadata dataclass."""

    def test_default_values(self):
        """Test default values for provider metadata."""
        metadata = ProviderMetadata(
            name="test",
            display_name="Test Provider",
            description="A test provider",
        )

        assert metadata.name == "test"
        assert metadata.display_name == "Test Provider"
        assert metadata.description == "A test provider"
        assert metadata.icon is None
        assert metadata.is_local is False
        assert metadata.requires_api_key is True
        assert metadata.api_key_env_var is None
        assert metadata.api_key_prefix is None
        assert metadata.base_url_env_var is None
        assert metadata.base_url_default is None
        assert metadata.timeout_env_var == "PROVIDER_TIMEOUT"
        assert metadata.timeout_default == 120
        assert metadata.availability_endpoint is None

    def test_cloud_provider_metadata(self):
        """Test metadata for a cloud provider like OpenAI."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI GPT models via API",
            icon="simple-icons:openai",
            is_local=False,
            requires_api_key=True,
            api_key_env_var="OPENAI_API_KEY",
            api_key_prefix="sk-",
            timeout_env_var="PROVIDER_TIMEOUT_OPENAI",
            timeout_default=120,
        )

        assert metadata.is_local is False
        assert metadata.requires_api_key is True
        assert metadata.api_key_env_var == "OPENAI_API_KEY"
        assert metadata.api_key_prefix == "sk-"
        assert metadata.availability_endpoint is None  # Cloud providers don't have this

    def test_local_provider_metadata(self):
        """Test metadata for a local provider like Ollama."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Local LLM via Ollama server",
            icon="mdi:robot",
            is_local=True,
            requires_api_key=False,
            base_url_env_var="OLLAMA_BASE_URL",
            base_url_default="http://localhost:11434",
            timeout_env_var="PROVIDER_TIMEOUT_OLLAMA",
            timeout_default=900,
            availability_endpoint="/api/tags",
        )

        assert metadata.is_local is True
        assert metadata.requires_api_key is False
        assert metadata.base_url_default == "http://localhost:11434"
        assert metadata.availability_endpoint == "/api/tags"
        assert metadata.timeout_default == 900


class TestProviderMetadataGetApiKey:
    """Test cases for get_api_key() method."""

    def test_get_api_key_from_env(self):
        """Test getting API key from environment variable."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_env_var="TEST_OPENAI_API_KEY",
        )

        with mock.patch.dict(os.environ, {"TEST_OPENAI_API_KEY": "sk-test123"}):
            result = metadata.get_api_key()
            assert result == "sk-test123"

    def test_get_api_key_not_set(self):
        """Test getting API key when env var is not set."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_env_var="NONEXISTENT_API_KEY_VAR",
        )

        # Ensure the env var is not set
        with mock.patch.dict(os.environ, {}, clear=True):
            result = metadata.get_api_key()
            assert result is None

    def test_get_api_key_no_env_var_configured(self):
        """Test getting API key when no env var is configured."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            api_key_env_var=None,
        )

        result = metadata.get_api_key()
        assert result is None


class TestProviderMetadataGetBaseUrl:
    """Test cases for get_base_url() method."""

    def test_get_base_url_from_env(self):
        """Test getting base URL from environment variable."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            base_url_env_var="TEST_OLLAMA_BASE_URL",
            base_url_default="http://localhost:11434",
        )

        with mock.patch.dict(os.environ, {"TEST_OLLAMA_BASE_URL": "http://remote:11434"}):
            result = metadata.get_base_url()
            assert result == "http://remote:11434"

    def test_get_base_url_falls_back_to_default(self):
        """Test that base URL falls back to default when env var not set."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            base_url_env_var="NONEXISTENT_URL_VAR",
            base_url_default="http://localhost:11434",
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            result = metadata.get_base_url()
            assert result == "http://localhost:11434"

    def test_get_base_url_no_config(self):
        """Test getting base URL when nothing is configured."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            base_url_env_var=None,
            base_url_default=None,
        )

        result = metadata.get_base_url()
        assert result is None

    def test_get_base_url_env_empty_string_uses_default(self):
        """Test that empty env var string uses default."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            base_url_env_var="TEST_EMPTY_URL",
            base_url_default="http://localhost:11434",
        )

        # Empty string should be falsy, so should fall back to default
        with mock.patch.dict(os.environ, {"TEST_EMPTY_URL": ""}):
            result = metadata.get_base_url()
            assert result == "http://localhost:11434"


class TestProviderMetadataGetTimeout:
    """Test cases for get_timeout() method."""

    def test_get_timeout_from_env(self):
        """Test getting timeout from environment variable."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            timeout_env_var="TEST_TIMEOUT",
            timeout_default=900,
        )

        with mock.patch.dict(os.environ, {"TEST_TIMEOUT": "600"}):
            result = metadata.get_timeout()
            assert result == 600

    def test_get_timeout_falls_back_to_default(self):
        """Test that timeout falls back to default when env var not set."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            timeout_env_var="NONEXISTENT_TIMEOUT",
            timeout_default=900,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            result = metadata.get_timeout()
            assert result == 900

    def test_get_timeout_invalid_env_value_uses_default(self):
        """Test that invalid env value falls back to default."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Ollama",
            timeout_env_var="TEST_INVALID_TIMEOUT",
            timeout_default=120,
        )

        with mock.patch.dict(os.environ, {"TEST_INVALID_TIMEOUT": "not_a_number"}):
            result = metadata.get_timeout()
            assert result == 120


class TestProviderMetadataMaskApiKey:
    """Test cases for mask_api_key() method."""

    def test_mask_api_key_with_prefix(self):
        """Test masking API key that has a known prefix."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_prefix="sk-",
        )

        result = metadata.mask_api_key("sk-abc123xyz789")
        assert result == "sk-***789"

    def test_mask_api_key_without_prefix(self):
        """Test masking API key when no prefix is configured."""
        metadata = ProviderMetadata(
            name="anthropic",
            display_name="Anthropic",
            description="Anthropic",
            api_key_prefix=None,
        )

        result = metadata.mask_api_key("abc123xyz789")
        assert result == "***789"

    def test_mask_api_key_none_input(self):
        """Test masking returns None for None input."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_prefix="sk-",
        )

        result = metadata.mask_api_key(None)
        assert result is None

    def test_mask_api_key_empty_string(self):
        """Test masking returns None for empty string."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_prefix="sk-",
        )

        result = metadata.mask_api_key("")
        assert result is None

    def test_mask_api_key_short_key_with_prefix(self):
        """Test masking short API key with prefix."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_prefix="sk-",
        )

        # Key is just "sk-ab" - only 2 chars after prefix
        result = metadata.mask_api_key("sk-ab")
        assert result == "sk-***"  # No suffix since key is too short

    def test_mask_api_key_prefix_mismatch(self):
        """Test masking when key doesn't match expected prefix."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_prefix="sk-",
        )

        # Key doesn't start with sk-
        result = metadata.mask_api_key("abc123xyz789")
        assert result == "***789"

    def test_mask_api_key_anthropic_style(self):
        """Test masking Anthropic-style API key."""
        metadata = ProviderMetadata(
            name="anthropic",
            display_name="Anthropic",
            description="Anthropic Claude API",
            api_key_prefix="sk-ant-",
        )

        result = metadata.mask_api_key("sk-ant-api03-abcdefghijklmnop")
        assert result == "sk-ant-***nop"


class TestProviderMetadataToDict:
    """Test cases for to_dict() method."""

    def test_to_dict_cloud_provider(self):
        """Test to_dict for cloud provider."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI GPT models",
            icon="simple-icons:openai",
            is_local=False,
            requires_api_key=True,
            api_key_env_var="OPENAI_API_KEY",
            api_key_prefix="sk-",
            timeout_env_var="PROVIDER_TIMEOUT_OPENAI",
            timeout_default=120,
        )

        result = metadata.to_dict()

        assert result == {
            "name": "openai",
            "display_name": "OpenAI",
            "description": "OpenAI GPT models",
            "icon": "simple-icons:openai",
            "is_local": False,
            "requires_api_key": True,
            "api_key_env_var": "OPENAI_API_KEY",
            "api_key_prefix": "sk-",
            "base_url_env_var": None,
            "base_url_default": None,
            "timeout_env_var": "PROVIDER_TIMEOUT_OPENAI",
            "timeout_default": 120,
            "availability_endpoint": None,
        }

    def test_to_dict_local_provider(self):
        """Test to_dict for local provider."""
        metadata = ProviderMetadata(
            name="ollama",
            display_name="Ollama",
            description="Local LLM via Ollama",
            icon="mdi:robot",
            is_local=True,
            requires_api_key=False,
            base_url_env_var="OLLAMA_BASE_URL",
            base_url_default="http://localhost:11434",
            timeout_env_var="PROVIDER_TIMEOUT_OLLAMA",
            timeout_default=900,
            availability_endpoint="/api/tags",
        )

        result = metadata.to_dict()

        assert result["is_local"] is True
        assert result["requires_api_key"] is False
        assert result["base_url_default"] == "http://localhost:11434"
        assert result["availability_endpoint"] == "/api/tags"
        assert result["timeout_default"] == 900

    def test_to_dict_does_not_include_actual_api_key(self):
        """Test that to_dict does not expose actual API key values."""
        metadata = ProviderMetadata(
            name="openai",
            display_name="OpenAI",
            description="OpenAI",
            api_key_env_var="OPENAI_API_KEY",
        )

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-secret123"}):
            result = metadata.to_dict()

            # Should contain env var name, not the actual key
            assert result["api_key_env_var"] == "OPENAI_API_KEY"
            assert "sk-secret123" not in str(result)


class TestProviderMetadataInheritance:
    """Test that ProviderMetadata properly inherits from ComponentMetadata."""

    def test_inherits_component_fields(self):
        """Test that base ComponentMetadata fields are available."""
        metadata = ProviderMetadata(
            name="test",
            display_name="Test",
            description="Test provider",
            icon="mdi:test",
        )

        # These come from ComponentMetadata
        assert hasattr(metadata, "name")
        assert hasattr(metadata, "display_name")
        assert hasattr(metadata, "description")
        assert hasattr(metadata, "icon")

    def test_to_dict_includes_base_fields(self):
        """Test that to_dict includes fields from base class."""
        metadata = ProviderMetadata(
            name="test",
            display_name="Test Provider",
            description="A test provider",
            icon="mdi:test",
        )

        result = metadata.to_dict()

        # Base class fields should be present
        assert "name" in result
        assert "display_name" in result
        assert "description" in result
        assert "icon" in result
