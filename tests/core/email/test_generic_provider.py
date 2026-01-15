"""Tests for GenericIMAPProvider with mocked IMAP connections."""
import socket
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from reconly_core.email.base import IMAPConfig
from reconly_core.email.errors import (
    IMAPAuthError,
    IMAPConnectionError,
    IMAPFetchError,
    IMAPFolderError,
)
from reconly_core.email.generic import GenericIMAPProvider


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def basic_config():
    """Create a basic IMAP configuration for testing."""
    return IMAPConfig(
        provider="generic",
        host="mail.example.com",
        username="user@example.com",
        password="password123",
    )


@pytest.fixture
def sample_email_raw():
    """Create a sample raw email message for testing."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Test Email Subject"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"
    msg["Message-ID"] = "<test123@example.com>"

    # Plain text part
    text_part = MIMEText("This is the plain text content.", "plain")
    msg.attach(text_part)

    # HTML part
    html_part = MIMEText("<p>This is the <strong>HTML</strong> content.</p>", "html")
    msg.attach(html_part)

    return msg.as_bytes()


# =============================================================================
# Connection Tests
# =============================================================================

class TestConnection:
    """Test IMAP connection establishment and authentication."""

    @patch("imaplib.IMAP4_SSL")
    def test_connect_success_ssl(self, mock_imap_class, basic_config):
        """Test successful SSL connection."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        assert provider.is_connected
        mock_imap_class.assert_called_once_with("mail.example.com", 993)
        mock_conn.login.assert_called_once_with("user@example.com", "password123")

    @patch("imaplib.IMAP4")
    def test_connect_success_no_ssl(self, mock_imap_class, basic_config):
        """Test successful connection without SSL."""
        basic_config.use_ssl = False
        basic_config.port = 143

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        assert provider.is_connected
        mock_imap_class.assert_called_once_with("mail.example.com", 143)

    @patch("imaplib.IMAP4_SSL")
    def test_connect_timeout(self, mock_imap_class, basic_config):
        """Test connection timeout handling."""
        mock_imap_class.side_effect = socket.timeout()

        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPConnectionError, match="timed out"):
            provider.connect()

        assert not provider.is_connected

    @patch("imaplib.IMAP4_SSL")
    def test_connect_hostname_resolution_error(self, mock_imap_class, basic_config):
        """Test hostname resolution error handling."""
        mock_imap_class.side_effect = socket.gaierror("Name or service not known")

        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPConnectionError, match="Cannot resolve hostname"):
            provider.connect()

        assert not provider.is_connected

    @patch("imaplib.IMAP4_SSL")
    def test_connect_connection_refused(self, mock_imap_class, basic_config):
        """Test connection refused error handling."""
        mock_imap_class.side_effect = ConnectionRefusedError()

        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPConnectionError, match="Connection refused"):
            provider.connect()

        assert not provider.is_connected

    @patch("imaplib.IMAP4_SSL")
    def test_auth_failure(self, mock_imap_class, basic_config):
        """Test authentication failure handling."""
        import imaplib

        mock_conn = MagicMock()
        mock_conn.login.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        mock_conn.logout.return_value = ("OK", [b"Logged out"])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPAuthError, match="Authentication failed"):
            provider.connect()

        assert not provider.is_connected
        # Connection should be cleaned up after auth failure
        mock_conn.logout.assert_called_once()

    @patch("imaplib.IMAP4_SSL")
    def test_disconnect(self, mock_imap_class, basic_config):
        """Test disconnection cleans up resources."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.logout.return_value = ("OK", [b"Logged out"])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        assert provider.is_connected

        provider.disconnect()
        assert not provider.is_connected
        mock_conn.logout.assert_called_once()

    @patch("imaplib.IMAP4_SSL")
    def test_context_manager(self, mock_imap_class, basic_config):
        """Test using provider as context manager."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.logout.return_value = ("OK", [b"Logged out"])
        mock_imap_class.return_value = mock_conn

        with GenericIMAPProvider(basic_config) as provider:
            assert provider.is_connected

        # Should be disconnected after context exit
        assert not provider.is_connected
        mock_conn.logout.assert_called_once()


# =============================================================================
# Folder Operations Tests
# =============================================================================

class TestFolderOperations:
    """Test folder listing and selection."""

    @patch("imaplib.IMAP4_SSL")
    def test_list_folders(self, mock_imap_class, basic_config):
        """Test listing available folders."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.list.return_value = (
            "OK",
            [
                b'(\\HasNoChildren) "/" "INBOX"',
                b'(\\HasNoChildren) "/" "Sent"',
                b'(\\HasNoChildren) "/" "Archive"',
            ],
        )
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        folders = provider.list_folders()

        assert len(folders) == 3
        assert "INBOX" in folders
        assert "Sent" in folders
        assert "Archive" in folders

    @patch("imaplib.IMAP4_SSL")
    def test_list_folders_not_connected(self, mock_imap_class, basic_config):
        """Test that list_folders raises error when not connected."""
        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPConnectionError, match="Not connected"):
            provider.list_folders()

    @patch("imaplib.IMAP4_SSL")
    def test_list_folders_error(self, mock_imap_class, basic_config):
        """Test handling of folder list errors."""
        import imaplib

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.list.side_effect = imaplib.IMAP4.error("List failed")
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        with pytest.raises(IMAPFolderError, match="Failed to list folders"):
            provider.list_folders()


# =============================================================================
# Email Fetching Tests
# =============================================================================

class TestFetchEmails:
    """Test email fetching with various filters and configurations."""

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_basic(self, mock_imap_class, basic_config, sample_email_raw):
        """Test basic email fetching."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, sample_email_raw)])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails(folder="INBOX")

        assert len(emails) == 1
        assert emails[0].subject == "Test Email Subject"
        assert emails[0].sender == "sender@example.com"
        assert emails[0].content == "This is the plain text content."
        assert emails[0].folder == "INBOX"

        # Verify folder was selected in read-only mode
        mock_conn.select.assert_called_once_with("INBOX", readonly=True)

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_with_since_filter(self, mock_imap_class, basic_config, sample_email_raw):
        """Test fetching emails with since date filter."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, sample_email_raw)])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        since_date = datetime(2024, 1, 1)
        emails = provider.fetch_emails(folder="INBOX", since=since_date)

        # Verify SINCE search criterion was used
        mock_conn.search.assert_called_once()
        search_args = mock_conn.search.call_args[0]
        assert "SINCE" in search_args
        assert "01-Jan-2024" in search_args

        assert len(emails) == 1

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_with_max_items(self, mock_imap_class, basic_config, sample_email_raw):
        """Test fetching emails with max_items limit."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])
        mock_conn.fetch.return_value = ("OK", [(None, sample_email_raw)])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails(folder="INBOX", max_items=2)

        # Should only fetch 2 emails even though 5 were found
        assert mock_conn.fetch.call_count == 2

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_no_results(self, mock_imap_class, basic_config):
        """Test fetching when no emails match criteria."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"0"])
        mock_conn.search.return_value = ("OK", [b""])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails(folder="INBOX")

        assert len(emails) == 0
        mock_conn.fetch.assert_not_called()

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_folder_not_found(self, mock_imap_class, basic_config):
        """Test fetching from non-existent folder."""
        import imaplib

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.side_effect = imaplib.IMAP4.error("Folder not found")
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        with pytest.raises(IMAPFolderError, match="Cannot select folder"):
            provider.fetch_emails(folder="NonExistent")

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_emails_not_connected(self, mock_imap_class, basic_config):
        """Test that fetch_emails raises error when not connected."""
        provider = GenericIMAPProvider(basic_config)

        with pytest.raises(IMAPConnectionError, match="Not connected"):
            provider.fetch_emails()


# =============================================================================
# Email Filtering Tests
# =============================================================================

class TestEmailFiltering:
    """Test sender and subject filtering."""

    def create_email_with_headers(self, sender, subject):
        """Helper to create email with specific headers."""
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = "recipient@example.com"
        msg["Subject"] = subject
        msg["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"
        msg["Message-ID"] = f"<test{sender}{subject}@example.com>"
        msg.attach(MIMEText("Test content", "plain"))
        return msg.as_bytes()

    @patch("imaplib.IMAP4_SSL")
    def test_from_filter_exact_match(self, mock_imap_class):
        """Test from_filter with exact email match."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            from_filter="sender@example.com",
        )

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"2"])
        mock_conn.search.return_value = ("OK", [b"1 2"])

        # First email matches filter, second doesn't
        email1 = self.create_email_with_headers("sender@example.com", "Test 1")
        email2 = self.create_email_with_headers("other@example.com", "Test 2")

        mock_conn.fetch.side_effect = [
            ("OK", [(None, email2)]),  # Newest first (ID 2)
            ("OK", [(None, email1)]),  # Then ID 1
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should only return email matching the from_filter
        assert len(emails) == 1
        assert emails[0].sender == "sender@example.com"

    @patch("imaplib.IMAP4_SSL")
    def test_from_filter_wildcard(self, mock_imap_class):
        """Test from_filter with wildcard pattern."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            from_filter="*@example.com",
        )

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"2"])
        mock_conn.search.return_value = ("OK", [b"1 2"])

        email1 = self.create_email_with_headers("alice@example.com", "Test 1")
        email2 = self.create_email_with_headers("bob@other.com", "Test 2")

        mock_conn.fetch.side_effect = [
            ("OK", [(None, email2)]),
            ("OK", [(None, email1)]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should only return email from @example.com domain
        assert len(emails) == 1
        assert emails[0].sender == "alice@example.com"

    @patch("imaplib.IMAP4_SSL")
    def test_subject_filter_exact_match(self, mock_imap_class):
        """Test subject_filter with exact match."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            subject_filter="[ALERT]",
        )

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"2"])
        mock_conn.search.return_value = ("OK", [b"1 2"])

        email1 = self.create_email_with_headers("sender@example.com", "[ALERT] System Down")
        email2 = self.create_email_with_headers("sender@example.com", "Regular Email")

        mock_conn.fetch.side_effect = [
            ("OK", [(None, email2)]),
            ("OK", [(None, email1)]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should only return email with [ALERT] in subject
        assert len(emails) == 1
        assert "[ALERT]" in emails[0].subject

    @patch("imaplib.IMAP4_SSL")
    def test_subject_filter_wildcard(self, mock_imap_class):
        """Test subject_filter with wildcard pattern."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            subject_filter="*Report*",
        )

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"3"])
        mock_conn.search.return_value = ("OK", [b"1 2 3"])

        email1 = self.create_email_with_headers("sender@example.com", "Daily Report")
        email2 = self.create_email_with_headers("sender@example.com", "Weekly Report Summary")
        email3 = self.create_email_with_headers("sender@example.com", "Unrelated Email")

        mock_conn.fetch.side_effect = [
            ("OK", [(None, email3)]),
            ("OK", [(None, email2)]),
            ("OK", [(None, email1)]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should return 2 emails with "Report" in subject
        assert len(emails) == 2
        for email in emails:
            assert "Report" in email.subject

    @patch("imaplib.IMAP4_SSL")
    def test_combined_filters(self, mock_imap_class):
        """Test using both from_filter and subject_filter together."""
        config = IMAPConfig(
            provider="generic",
            host="mail.example.com",
            username="user@example.com",
            password="password",
            from_filter="*@alerts.com",
            subject_filter="*[CRITICAL]*",
        )

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"3"])
        mock_conn.search.return_value = ("OK", [b"1 2 3"])

        # Only email1 matches both filters
        email1 = self.create_email_with_headers("monitor@alerts.com", "[CRITICAL] Server Down")
        email2 = self.create_email_with_headers("monitor@alerts.com", "Info: All OK")
        email3 = self.create_email_with_headers("other@example.com", "[CRITICAL] Issue")

        mock_conn.fetch.side_effect = [
            ("OK", [(None, email3)]),
            ("OK", [(None, email2)]),
            ("OK", [(None, email1)]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should only return email matching BOTH filters
        assert len(emails) == 1
        assert emails[0].sender == "monitor@alerts.com"
        assert "[CRITICAL]" in emails[0].subject


# =============================================================================
# Email Content Parsing Tests
# =============================================================================

class TestEmailParsing:
    """Test email content parsing and extraction."""

    @patch("imaplib.IMAP4_SSL")
    def test_parse_multipart_email(self, mock_imap_class, basic_config, sample_email_raw):
        """Test parsing multipart email with text and HTML."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, sample_email_raw)])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        assert len(emails) == 1
        email = emails[0]

        # Should extract plain text content
        assert email.content == "This is the plain text content."
        # Should also store HTML content
        assert email.html_content is not None
        assert "HTML" in email.html_content

    @patch("imaplib.IMAP4_SSL")
    def test_parse_plain_text_only_email(self, mock_imap_class, basic_config):
        """Test parsing email with only plain text (no HTML)."""
        msg = MIMEText("Just plain text content", "plain")
        msg["Subject"] = "Plain Text Email"
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"
        msg["Message-ID"] = "<plain123@example.com>"

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, msg.as_bytes())])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        assert len(emails) == 1
        assert emails[0].content == "Just plain text content"
        assert emails[0].html_content is None

    @patch("imaplib.IMAP4_SSL")
    def test_parse_html_only_email(self, mock_imap_class, basic_config):
        """Test parsing email with only HTML (no plain text)."""
        msg = MIMEText("<p>HTML only content</p>", "html")
        msg["Subject"] = "HTML Email"
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"
        msg["Message-ID"] = "<html123@example.com>"

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, msg.as_bytes())])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        assert len(emails) == 1
        # Should convert HTML to text
        assert "HTML only content" in emails[0].content
        assert emails[0].html_content is not None

    @patch("imaplib.IMAP4_SSL")
    def test_parse_email_headers(self, mock_imap_class, basic_config, sample_email_raw):
        """Test that email headers are correctly parsed."""
        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, sample_email_raw)])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        assert len(emails) == 1
        email = emails[0]

        assert email.message_id == "test123@example.com"
        assert email.subject == "Test Email Subject"
        assert email.sender == "sender@example.com"
        assert "recipient@example.com" in email.recipients
        assert email.date is not None

    @patch("imaplib.IMAP4_SSL")
    def test_parse_email_with_encoded_subject(self, mock_imap_class, basic_config):
        """Test parsing email with encoded (non-ASCII) subject."""
        msg = MIMEText("Content", "plain")
        msg["Subject"] = "=?utf-8?b?VGVzdCDwn5iA?="  # "Test 😀" encoded
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(None, msg.as_bytes())])
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        assert len(emails) == 1
        # Subject should be decoded
        assert "Test" in emails[0].subject

    @patch("imaplib.IMAP4_SSL")
    def test_handle_fetch_error_gracefully(self, mock_imap_class, basic_config):
        """Test that fetch errors are handled gracefully."""
        good_email = MIMEText("Good email", "plain")
        good_email["Subject"] = "Good"
        good_email["From"] = "sender@example.com"
        good_email["To"] = "recipient@example.com"
        good_email["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"
        good_email["Message-ID"] = "<good@example.com>"

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"2"])
        mock_conn.search.return_value = ("OK", [b"1 2"])

        # First fetch fails with an exception, second succeeds
        mock_conn.fetch.side_effect = [
            Exception("Network error"),
            ("OK", [(None, good_email.as_bytes())]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should return only the good email, skip the failed one
        assert len(emails) == 1
        assert emails[0].subject == "Good"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in various scenarios."""

    @patch("imaplib.IMAP4_SSL")
    def test_search_error(self, mock_imap_class, basic_config):
        """Test handling of search errors."""
        import imaplib

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"1"])
        mock_conn.search.side_effect = imaplib.IMAP4.error("Search failed")
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()

        with pytest.raises(IMAPFetchError, match="Failed to fetch emails"):
            provider.fetch_emails()

    @patch("imaplib.IMAP4_SSL")
    def test_fetch_partial_failure(self, mock_imap_class, basic_config):
        """Test that partial fetch failures don't stop the entire operation."""
        good_email = MIMEText("Good email", "plain")
        good_email["Subject"] = "Good"
        good_email["From"] = "sender@example.com"
        good_email["To"] = "recipient@example.com"
        good_email["Date"] = "Mon, 15 Jan 2024 10:30:00 +0000"

        mock_conn = MagicMock()
        mock_conn.login.return_value = ("OK", [b"Logged in"])
        mock_conn.select.return_value = ("OK", [b"3"])
        mock_conn.search.return_value = ("OK", [b"1 2 3"])

        # One fetch fails, others succeed
        mock_conn.fetch.side_effect = [
            ("OK", [(None, good_email.as_bytes())]),
            Exception("Temporary failure"),
            ("OK", [(None, good_email.as_bytes())]),
        ]
        mock_imap_class.return_value = mock_conn

        provider = GenericIMAPProvider(basic_config)
        provider.connect()
        emails = provider.fetch_emails()

        # Should return the 2 successful emails, skip the failed one
        assert len(emails) == 2
