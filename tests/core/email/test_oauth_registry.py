"""Tests for OAuth provider registry pattern.

Tests the OAuthProviderMetadata dataclass and registry functions for managing
OAuth email providers (Gmail, Outlook, etc.).
"""
import os
from unittest.mock import Mock

import pytest

from reconly_core.email.oauth_registry import (
    OAuthProviderMetadata,
    register_oauth_provider,
    unregister_oauth_provider,
    get_oauth_provider,
    list_oauth_providers,
    list_oauth_provider_metadata,
    is_provider_configured,
    get_configured_providers,
    clear_oauth_providers,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_metadata():
    """Create a sample OAuthProviderMetadata for testing."""
    return OAuthProviderMetadata(
        name="test_provider",
        display_name="Test Provider",
        description="A test OAuth provider",
        icon="mdi:test",
        client_id_env_var="TEST_CLIENT_ID",
        client_secret_env_var="TEST_CLIENT_SECRET",
        scopes=["scope1", "scope2"],
        auth_url_generator=lambda r, s, c: f"https://auth.test?redirect={r}&state={s}&challenge={c}",
        token_exchanger=lambda c, r, v: {"access_token": "test_token"},
        token_revoker=lambda t: True,
    )


@pytest.fixture
def env_credentials():
    """Set up test OAuth credentials in environment."""
    old_client_id = os.environ.get("TEST_CLIENT_ID")
    old_client_secret = os.environ.get("TEST_CLIENT_SECRET")

    os.environ["TEST_CLIENT_ID"] = "test_id_value"
    os.environ["TEST_CLIENT_SECRET"] = "test_secret_value"

    yield

    # Restore original values
    if old_client_id:
        os.environ["TEST_CLIENT_ID"] = old_client_id
    else:
        os.environ.pop("TEST_CLIENT_ID", None)

    if old_client_secret:
        os.environ["TEST_CLIENT_SECRET"] = old_client_secret
    else:
        os.environ.pop("TEST_CLIENT_SECRET", None)


@pytest.fixture
def partial_env_credentials():
    """Set up partial test OAuth credentials (only client_id)."""
    old_client_id = os.environ.get("TEST_CLIENT_ID")
    old_client_secret = os.environ.get("TEST_CLIENT_SECRET")

    os.environ["TEST_CLIENT_ID"] = "test_id_value"
    os.environ.pop("TEST_CLIENT_SECRET", None)

    yield

    # Restore original values
    if old_client_id:
        os.environ["TEST_CLIENT_ID"] = old_client_id
    else:
        os.environ.pop("TEST_CLIENT_ID", None)

    if old_client_secret:
        os.environ["TEST_CLIENT_SECRET"] = old_client_secret
    else:
        os.environ.pop("TEST_CLIENT_SECRET", None)


@pytest.fixture
def no_env_credentials():
    """Ensure test OAuth credentials are not in environment."""
    old_client_id = os.environ.pop("TEST_CLIENT_ID", None)
    old_client_secret = os.environ.pop("TEST_CLIENT_SECRET", None)

    yield

    # Restore original values
    if old_client_id:
        os.environ["TEST_CLIENT_ID"] = old_client_id
    if old_client_secret:
        os.environ["TEST_CLIENT_SECRET"] = old_client_secret


# =============================================================================
# OAuthProviderMetadata Tests
# =============================================================================


class TestOAuthProviderMetadata:
    """Test OAuthProviderMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating OAuthProviderMetadata with all fields."""
        auth_generator = Mock()
        token_exchanger = Mock()
        token_revoker = Mock()

        metadata = OAuthProviderMetadata(
            name="test_provider",
            display_name="Test Provider",
            description="A test OAuth provider",
            icon="mdi:test-icon",
            client_id_env_var="TEST_CLIENT_ID",
            client_secret_env_var="TEST_CLIENT_SECRET",
            scopes=["https://test.com/scope1", "https://test.com/scope2"],
            auth_url_generator=auth_generator,
            token_exchanger=token_exchanger,
            token_revoker=token_revoker,
        )

        assert metadata.name == "test_provider"
        assert metadata.display_name == "Test Provider"
        assert metadata.description == "A test OAuth provider"
        assert metadata.icon == "mdi:test-icon"
        assert metadata.client_id_env_var == "TEST_CLIENT_ID"
        assert metadata.client_secret_env_var == "TEST_CLIENT_SECRET"
        assert metadata.scopes == ["https://test.com/scope1", "https://test.com/scope2"]
        assert metadata.auth_url_generator is auth_generator
        assert metadata.token_exchanger is token_exchanger
        assert metadata.token_revoker is token_revoker

    def test_metadata_creation_with_defaults(self):
        """Test creating OAuthProviderMetadata with default values."""
        metadata = OAuthProviderMetadata(
            name="minimal",
            display_name="Minimal Provider",
            description="Minimal test provider",
        )

        assert metadata.name == "minimal"
        assert metadata.display_name == "Minimal Provider"
        assert metadata.description == "Minimal test provider"
        assert metadata.icon is None
        assert metadata.client_id_env_var == ""
        assert metadata.client_secret_env_var == ""
        assert metadata.scopes == []
        assert metadata.auth_url_generator is None
        assert metadata.token_exchanger is None
        assert metadata.token_revoker is None

    def test_is_configured_true(self, sample_metadata, env_credentials):
        """Test is_configured returns True when both env vars are set."""
        assert sample_metadata.is_configured() is True

    def test_is_configured_false_missing_id(self, sample_metadata, no_env_credentials):
        """Test is_configured returns False when client_id env var missing."""
        # Set only the secret
        os.environ["TEST_CLIENT_SECRET"] = "secret_only"
        try:
            assert sample_metadata.is_configured() is False
        finally:
            os.environ.pop("TEST_CLIENT_SECRET", None)

    def test_is_configured_false_missing_secret(self, sample_metadata, partial_env_credentials):
        """Test is_configured returns False when client_secret env var missing."""
        assert sample_metadata.is_configured() is False

    def test_is_configured_false_both_missing(self, sample_metadata, no_env_credentials):
        """Test is_configured returns False when both env vars are missing."""
        assert sample_metadata.is_configured() is False

    def test_is_configured_false_empty_values(self, sample_metadata):
        """Test is_configured returns False when env vars are empty strings."""
        os.environ["TEST_CLIENT_ID"] = ""
        os.environ["TEST_CLIENT_SECRET"] = ""
        try:
            assert sample_metadata.is_configured() is False
        finally:
            os.environ.pop("TEST_CLIENT_ID", None)
            os.environ.pop("TEST_CLIENT_SECRET", None)

    def test_to_dict_excludes_callables(self, sample_metadata, env_credentials):
        """Test to_dict returns dict without callable fields."""
        result = sample_metadata.to_dict()

        # Should not contain callables
        assert "auth_url_generator" not in result
        assert "token_exchanger" not in result
        assert "token_revoker" not in result

        # Should contain serializable fields
        assert result["name"] == "test_provider"
        assert result["display_name"] == "Test Provider"
        assert result["description"] == "A test OAuth provider"
        assert result["icon"] == "mdi:test"
        assert result["client_id_env_var"] == "TEST_CLIENT_ID"
        assert result["client_secret_env_var"] == "TEST_CLIENT_SECRET"
        assert result["scopes"] == ["scope1", "scope2"]

    def test_to_dict_includes_configured_status(self, sample_metadata, env_credentials):
        """Test to_dict includes is_configured status."""
        result = sample_metadata.to_dict()
        assert "is_configured" in result
        assert result["is_configured"] is True

    def test_to_dict_configured_false(self, sample_metadata, no_env_credentials):
        """Test to_dict shows is_configured=False when not configured."""
        result = sample_metadata.to_dict()
        assert "is_configured" in result
        assert result["is_configured"] is False

    def test_to_dict_scopes_is_copy(self, sample_metadata, env_credentials):
        """Test to_dict returns a copy of scopes list."""
        result = sample_metadata.to_dict()
        result["scopes"].append("modified_scope")
        assert "modified_scope" not in sample_metadata.scopes


# =============================================================================
# OAuth Provider Registry Tests
# =============================================================================


class TestOAuthProviderRegistry:
    """Test OAuth provider registry functions."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clear registry before and after each test."""
        clear_oauth_providers()
        yield
        clear_oauth_providers()

    def test_register_provider(self, sample_metadata):
        """Test registering a new OAuth provider."""
        result = register_oauth_provider(sample_metadata)

        assert result is sample_metadata
        assert get_oauth_provider("test_provider") is sample_metadata

    def test_register_duplicate_raises_error(self, sample_metadata):
        """Test registering same provider name raises ValueError."""
        register_oauth_provider(sample_metadata)

        duplicate = OAuthProviderMetadata(
            name="test_provider",  # Same name
            display_name="Duplicate Provider",
            description="A duplicate provider",
        )

        with pytest.raises(ValueError, match="already registered"):
            register_oauth_provider(duplicate)

    def test_register_multiple_providers(self):
        """Test registering multiple different providers."""
        provider1 = OAuthProviderMetadata(
            name="provider1",
            display_name="Provider 1",
            description="First provider",
        )
        provider2 = OAuthProviderMetadata(
            name="provider2",
            display_name="Provider 2",
            description="Second provider",
        )

        register_oauth_provider(provider1)
        register_oauth_provider(provider2)

        assert get_oauth_provider("provider1") is provider1
        assert get_oauth_provider("provider2") is provider2
        assert len(list_oauth_providers()) == 2

    def test_get_oauth_provider_exists(self, sample_metadata):
        """Test getting existing provider returns metadata."""
        register_oauth_provider(sample_metadata)
        result = get_oauth_provider("test_provider")

        assert result is sample_metadata
        assert result.name == "test_provider"
        assert result.display_name == "Test Provider"

    def test_get_oauth_provider_not_found(self):
        """Test getting non-existent provider returns None."""
        result = get_oauth_provider("nonexistent_provider")
        assert result is None

    def test_list_oauth_providers(self, sample_metadata):
        """Test listing all registered providers."""
        # Empty at start
        assert list_oauth_providers() == []

        # Register one
        register_oauth_provider(sample_metadata)
        providers = list_oauth_providers()

        assert len(providers) == 1
        assert providers[0] is sample_metadata

    def test_list_oauth_providers_multiple(self):
        """Test listing multiple providers."""
        provider1 = OAuthProviderMetadata(
            name="provider1",
            display_name="Provider 1",
            description="First",
        )
        provider2 = OAuthProviderMetadata(
            name="provider2",
            display_name="Provider 2",
            description="Second",
        )

        register_oauth_provider(provider1)
        register_oauth_provider(provider2)

        providers = list_oauth_providers()
        assert len(providers) == 2
        names = [p.name for p in providers]
        assert "provider1" in names
        assert "provider2" in names

    def test_list_oauth_provider_metadata(self, sample_metadata, env_credentials):
        """Test listing providers as serialized dicts."""
        register_oauth_provider(sample_metadata)

        metadata_list = list_oauth_provider_metadata()

        assert len(metadata_list) == 1
        assert isinstance(metadata_list[0], dict)
        assert metadata_list[0]["name"] == "test_provider"
        assert metadata_list[0]["display_name"] == "Test Provider"
        assert metadata_list[0]["is_configured"] is True
        assert "auth_url_generator" not in metadata_list[0]

    def test_list_oauth_provider_metadata_empty(self):
        """Test listing providers returns empty list when none registered."""
        metadata_list = list_oauth_provider_metadata()
        assert metadata_list == []

    def test_is_provider_configured_with_env(self, sample_metadata, env_credentials):
        """Test is_provider_configured checks env vars."""
        register_oauth_provider(sample_metadata)

        assert is_provider_configured("test_provider") is True

    def test_is_provider_configured_without_env(self, sample_metadata, no_env_credentials):
        """Test is_provider_configured returns False without env vars."""
        register_oauth_provider(sample_metadata)

        assert is_provider_configured("test_provider") is False

    def test_is_provider_configured_unknown(self):
        """Test is_provider_configured returns False for unknown provider."""
        assert is_provider_configured("unknown_provider") is False

    def test_get_configured_providers(self, env_credentials):
        """Test getting only configured providers."""
        # Create two providers with different env vars
        configured_provider = OAuthProviderMetadata(
            name="configured",
            display_name="Configured Provider",
            description="Has env vars",
            client_id_env_var="TEST_CLIENT_ID",
            client_secret_env_var="TEST_CLIENT_SECRET",
        )
        unconfigured_provider = OAuthProviderMetadata(
            name="unconfigured",
            display_name="Unconfigured Provider",
            description="Missing env vars",
            client_id_env_var="MISSING_CLIENT_ID",
            client_secret_env_var="MISSING_CLIENT_SECRET",
        )

        register_oauth_provider(configured_provider)
        register_oauth_provider(unconfigured_provider)

        configured = get_configured_providers()

        assert len(configured) == 1
        assert configured[0] is configured_provider

    def test_get_configured_providers_empty(self, no_env_credentials):
        """Test get_configured_providers returns empty when none configured."""
        unconfigured = OAuthProviderMetadata(
            name="unconfigured",
            display_name="Unconfigured",
            description="Not configured",
            client_id_env_var="MISSING_ID",
            client_secret_env_var="MISSING_SECRET",
        )
        register_oauth_provider(unconfigured)

        assert get_configured_providers() == []

    def test_unregister_provider(self, sample_metadata):
        """Test removing a provider from registry."""
        register_oauth_provider(sample_metadata)
        assert get_oauth_provider("test_provider") is not None

        result = unregister_oauth_provider("test_provider")

        assert result is True
        assert get_oauth_provider("test_provider") is None

    def test_unregister_nonexistent_provider(self):
        """Test unregistering non-existent provider returns False."""
        result = unregister_oauth_provider("nonexistent")
        assert result is False

    def test_clear_oauth_providers(self, sample_metadata):
        """Test clearing all providers from registry."""
        register_oauth_provider(sample_metadata)
        assert len(list_oauth_providers()) == 1

        clear_oauth_providers()

        assert len(list_oauth_providers()) == 0
        assert get_oauth_provider("test_provider") is None


# =============================================================================
# Builtin Provider Registration Tests
# =============================================================================


class TestBuiltinProviderRegistration:
    """Test that Gmail and Outlook auto-register when imported."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clear registry before and after each test."""
        clear_oauth_providers()
        yield
        clear_oauth_providers()

    def test_gmail_registered_on_import(self):
        """Test Gmail is registered when gmail module imported."""
        # Clear and re-import
        clear_oauth_providers()

        # Force reimport by removing from sys.modules if present
        import sys
        if "reconly_core.email.gmail" in sys.modules:
            del sys.modules["reconly_core.email.gmail"]

        import reconly_core.email.gmail  # noqa: F401

        provider = get_oauth_provider("gmail")
        assert provider is not None
        assert provider.name == "gmail"
        assert provider.display_name == "Gmail"
        assert provider.description == "Google Gmail via OAuth2"
        assert provider.icon == "mdi:google"
        assert provider.client_id_env_var == "GOOGLE_CLIENT_ID"
        assert provider.client_secret_env_var == "GOOGLE_CLIENT_SECRET"

    def test_outlook_registered_on_import(self):
        """Test Outlook is registered when outlook module imported."""
        clear_oauth_providers()

        # Force reimport by removing from sys.modules if present
        import sys
        if "reconly_core.email.outlook" in sys.modules:
            del sys.modules["reconly_core.email.outlook"]

        import reconly_core.email.outlook  # noqa: F401

        provider = get_oauth_provider("outlook")
        assert provider is not None
        assert provider.name == "outlook"
        assert provider.display_name == "Outlook / Microsoft 365"
        assert provider.description == "Microsoft Outlook via OAuth2"
        assert provider.icon == "mdi:microsoft"
        assert provider.client_id_env_var == "MICROSOFT_CLIENT_ID"
        assert provider.client_secret_env_var == "MICROSOFT_CLIENT_SECRET"

    def test_provider_callables_work(self):
        """Test registered provider callables are functional."""
        clear_oauth_providers()

        # Force reimport
        import sys
        for mod in ["reconly_core.email.gmail", "reconly_core.email.outlook"]:
            if mod in sys.modules:
                del sys.modules[mod]

        import reconly_core.email.gmail
        import reconly_core.email.outlook

        gmail = get_oauth_provider("gmail")
        outlook = get_oauth_provider("outlook")

        # Auth URL generators should be the actual functions
        assert gmail.auth_url_generator == reconly_core.email.gmail.generate_gmail_auth_url
        assert outlook.auth_url_generator == reconly_core.email.outlook.generate_outlook_auth_url

        # Token exchangers should be the actual functions
        assert gmail.token_exchanger == reconly_core.email.gmail.exchange_gmail_code
        assert outlook.token_exchanger == reconly_core.email.outlook.exchange_outlook_code

        # Token revokers should be the actual functions
        assert gmail.token_revoker == reconly_core.email.gmail.revoke_gmail_token
        assert outlook.token_revoker == reconly_core.email.outlook.revoke_outlook_token

    def test_provider_scopes(self):
        """Test registered providers have correct scopes."""
        clear_oauth_providers()

        import sys
        for mod in ["reconly_core.email.gmail", "reconly_core.email.outlook"]:
            if mod in sys.modules:
                del sys.modules[mod]

        import reconly_core.email.gmail
        import reconly_core.email.outlook

        gmail = get_oauth_provider("gmail")
        outlook = get_oauth_provider("outlook")

        # Gmail scopes
        assert gmail.scopes == reconly_core.email.gmail.GMAIL_SCOPES
        assert "https://www.googleapis.com/auth/gmail.readonly" in gmail.scopes

        # Outlook scopes
        assert outlook.scopes == reconly_core.email.outlook.OUTLOOK_SCOPES
        assert "https://graph.microsoft.com/Mail.Read" in outlook.scopes
        assert "offline_access" in outlook.scopes

    def test_reimport_raises_duplicate_error(self):
        """Test that reimporting after registration raises error."""
        clear_oauth_providers()

        import sys
        if "reconly_core.email.gmail" in sys.modules:
            del sys.modules["reconly_core.email.gmail"]

        # First import - should work
        import reconly_core.email.gmail  # noqa: F401
        assert get_oauth_provider("gmail") is not None

        # Try to register again manually - should raise
        from reconly_core.email.gmail import (
            generate_gmail_auth_url,
            exchange_gmail_code,
            revoke_gmail_token,
            GMAIL_SCOPES,
        )

        duplicate_metadata = OAuthProviderMetadata(
            name="gmail",
            display_name="Gmail Duplicate",
            description="Should fail",
            client_id_env_var="GOOGLE_CLIENT_ID",
            client_secret_env_var="GOOGLE_CLIENT_SECRET",
            scopes=GMAIL_SCOPES,
            auth_url_generator=generate_gmail_auth_url,
            token_exchanger=exchange_gmail_code,
            token_revoker=revoke_gmail_token,
        )

        with pytest.raises(ValueError, match="already registered"):
            register_oauth_provider(duplicate_metadata)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Clear registry before and after each test."""
        clear_oauth_providers()
        yield
        clear_oauth_providers()

    def test_register_with_none_callables(self):
        """Test registering provider with None callables."""
        metadata = OAuthProviderMetadata(
            name="no_callables",
            display_name="No Callables Provider",
            description="Provider without callable implementations",
            auth_url_generator=None,
            token_exchanger=None,
            token_revoker=None,
        )

        result = register_oauth_provider(metadata)
        assert result.auth_url_generator is None
        assert result.token_exchanger is None
        assert result.token_revoker is None

    def test_register_with_empty_scopes(self):
        """Test registering provider with empty scopes list."""
        metadata = OAuthProviderMetadata(
            name="no_scopes",
            display_name="No Scopes Provider",
            description="Provider without scopes",
            scopes=[],
        )

        result = register_oauth_provider(metadata)
        assert result.scopes == []

    def test_to_dict_with_none_icon(self):
        """Test to_dict handles None icon correctly."""
        metadata = OAuthProviderMetadata(
            name="no_icon",
            display_name="No Icon Provider",
            description="Provider without icon",
            icon=None,
        )

        result = metadata.to_dict()
        assert result["icon"] is None

    def test_get_provider_case_sensitive(self):
        """Test that provider lookup is case-sensitive."""
        metadata = OAuthProviderMetadata(
            name="CaseSensitive",
            display_name="Case Sensitive",
            description="Test case sensitivity",
        )
        register_oauth_provider(metadata)

        assert get_oauth_provider("CaseSensitive") is not None
        assert get_oauth_provider("casesensitive") is None
        assert get_oauth_provider("CASESENSITIVE") is None

    def test_provider_metadata_immutability_concern(self, sample_metadata, env_credentials):
        """Test that modifying returned list doesn't affect registry."""
        register_oauth_provider(sample_metadata)

        providers = list_oauth_providers()
        original_count = len(providers)

        # Clear the returned list
        providers.clear()

        # Registry should be unaffected
        assert len(list_oauth_providers()) == original_count
