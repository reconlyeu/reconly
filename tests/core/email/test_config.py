"""Tests for IMAPConfig validation and defaults."""
import pytest

from reconly_core.email.base import IMAPConfig


class TestIMAPConfigDefaults:
    """Test IMAPConfig default values."""

    def test_generic_provider_requires_host(self):
        """Test that generic provider requires host parameter."""
        with pytest.raises(ValueError, match="host is required"):
            IMAPConfig(
                provider="generic",
                username="user@example.com",
                password="password",
            )

    def test_generic_provider_with_host(self):
        """Test generic provider with explicit host."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
        )
        assert config.host == "mail.example.com"
        assert config.port == 993
        assert config.use_ssl is True
        assert config.folders == ["INBOX"]
        assert config.timeout == 30

    def test_gmail_provider_defaults(self):
        """Test Gmail provider sets correct defaults."""
        config = IMAPConfig(
            provider="gmail",
            username="user@gmail.com",
            password="app_password",
        )
        assert config.host == "imap.gmail.com"
        assert config.port == 993
        assert config.use_ssl is True

    def test_outlook_provider_defaults(self):
        """Test Outlook provider sets correct defaults."""
        config = IMAPConfig(
            provider="outlook",
            username="user@outlook.com",
            password="password",
        )
        assert config.host == "outlook.office365.com"
        assert config.port == 993
        assert config.use_ssl is True

    def test_custom_port(self):
        """Test custom port configuration."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            port=143,
            username="user@example.com",
            password="password",
            use_ssl=False,
        )
        assert config.port == 143
        assert config.use_ssl is False

    def test_custom_folders(self):
        """Test custom folders configuration."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            folders=["INBOX", "Sent", "Archive"],
        )
        assert config.folders == ["INBOX", "Sent", "Archive"]

    def test_from_filter(self):
        """Test from_filter configuration."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            from_filter="*@example.com",
        )
        assert config.from_filter == "*@example.com"

    def test_subject_filter(self):
        """Test subject_filter configuration."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            subject_filter="*[ALERT]*",
        )
        assert config.subject_filter == "*[ALERT]*"

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            timeout=60,
        )
        assert config.timeout == 60


class TestIMAPConfigSerialization:
    """Test IMAPConfig serialization."""

    def test_to_dict_excludes_password(self):
        """Test that to_dict excludes sensitive password data."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="secret_password",
        )
        config_dict = config.to_dict()

        # Should include non-sensitive fields
        assert config_dict["provider"] == "generic"
        assert config_dict["host"] == "mail.example.com"
        assert config_dict["username"] == "user@example.com"
        assert config_dict["port"] == 993
        assert config_dict["use_ssl"] is True

        # Should NOT include password
        assert "password" not in config_dict

    def test_to_dict_includes_filters(self):
        """Test that to_dict includes filter configurations."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            from_filter="*@example.com",
            subject_filter="*ALERT*",
        )
        config_dict = config.to_dict()

        assert config_dict["from_filter"] == "*@example.com"
        assert config_dict["subject_filter"] == "*ALERT*"

    def test_to_dict_includes_folders(self):
        """Test that to_dict includes folders list."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            folders=["INBOX", "Important"],
        )
        config_dict = config.to_dict()

        assert config_dict["folders"] == ["INBOX", "Important"]
