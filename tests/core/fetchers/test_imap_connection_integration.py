"""Integration tests for IMAP fetcher with Connection system.

Tests that the IMAP fetcher correctly uses Connection-provided credentials
and that feed_service's _process_imap_source correctly resolves and
injects connection credentials.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from reconly_core.database.models import Connection, Feed, FeedRun, FeedSource, Source
from reconly_core.fetchers.imap import IMAPFetcher
from reconly_core.email import IMAPError


@pytest.fixture(autouse=True)
def set_secret_key(monkeypatch):
    """Set SECRET_KEY for all tests in this module."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-imap-connection-tests-minimum-32-chars")


@pytest.fixture
def imap_connection(test_db: Session) -> Connection:
    """Create a sample IMAP connection with encrypted credentials."""
    from reconly_core.services.connection_service import create_connection

    connection = create_connection(
        db=test_db,
        name="Test IMAP Connection",
        connection_type="email_imap",
        config={
            "host": "imap.example.com",
            "port": 993,
            "username": "test@example.com",
            "password": "secret123",
            "use_ssl": True,
        },
        provider="generic",
    )
    test_db.commit()
    test_db.refresh(connection)
    return connection


@pytest.fixture
def imap_source_with_connection(test_db: Session, imap_connection: Connection) -> Source:
    """Create an IMAP source that uses a connection."""
    source = Source(
        name="Test IMAP Source",
        type="imap",
        url="imap://imap.example.com",
        connection_id=imap_connection.id,
        config={
            "provider": "generic",
            "folders": ["INBOX"],
        },
        enabled=True,
    )
    test_db.add(source)
    test_db.commit()
    test_db.refresh(source)
    return source


class TestIMAPFetcherRequiresConnection:
    """Test that IMAP fetcher requires connection credentials."""

    def test_fetcher_requires_connection_host(self):
        """Test that fetcher raises error when _connection_host is missing."""
        fetcher = IMAPFetcher()

        with pytest.raises(Exception) as exc_info:
            fetcher.fetch(
                url="imap://example.com",
                # Missing _connection_* credentials
                imap_provider="generic",
                imap_folders=["INBOX"],
            )

        assert "connection credentials not configured" in str(exc_info.value).lower()
        assert "host" in str(exc_info.value).lower()

    def test_fetcher_requires_connection_username(self):
        """Test that fetcher raises error when _connection_username is missing."""
        fetcher = IMAPFetcher()

        with pytest.raises(Exception) as exc_info:
            fetcher.fetch(
                url="imap://imap.example.com",
                _connection_host="imap.example.com",
                _connection_port=993,
                # Missing username and password
                imap_provider="generic",
                imap_folders=["INBOX"],
            )

        assert "username not configured" in str(exc_info.value).lower()

    def test_fetcher_requires_connection_password(self):
        """Test that fetcher raises error when _connection_password is missing."""
        fetcher = IMAPFetcher()

        with pytest.raises(Exception) as exc_info:
            fetcher.fetch(
                url="imap://imap.example.com",
                _connection_host="imap.example.com",
                _connection_port=993,
                _connection_username="test@example.com",
                # Missing password
                imap_provider="generic",
                imap_folders=["INBOX"],
            )

        assert "password not configured" in str(exc_info.value).lower()


class TestIMAPFetcherWithConnectionCredentials:
    """Test IMAP fetcher with properly injected connection credentials."""

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetcher_accepts_connection_credentials(self, mock_provider_class):
        """Test that fetcher works when _connection_* credentials are provided."""
        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()

        items = fetcher.fetch(
            url="imap://imap.example.com",
            _connection_host="imap.example.com",
            _connection_port=993,
            _connection_username="test@example.com",
            _connection_password="secret123",
            _connection_use_ssl=True,
            imap_provider="generic",
            imap_folders=["INBOX"],
        )

        # Should succeed without raising error
        assert isinstance(items, list)

        # Verify provider was called with correct config
        mock_provider_class.assert_called_once()
        config_arg = mock_provider_class.call_args[0][0]
        assert config_arg.host == "imap.example.com"
        assert config_arg.port == 993
        assert config_arg.username == "test@example.com"
        assert config_arg.password == "secret123"
        assert config_arg.use_ssl is True

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetcher_uses_connection_credentials_for_fetch(self, mock_provider_class):
        """Test that fetcher uses connection credentials to fetch emails."""
        from reconly_core.email import EmailMessage

        # Mock email messages
        mock_email = EmailMessage(
            message_id="test-msg-1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["test@example.com"],
            date=datetime(2024, 1, 1),
            content="Test email content",
            folder="INBOX",
        )

        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = [mock_email]
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()

        items = fetcher.fetch(
            url="imap://imap.example.com",
            _connection_host="imap.example.com",
            _connection_port=993,
            _connection_username="test@example.com",
            _connection_password="secret123",
            _connection_use_ssl=True,
            imap_provider="generic",
            imap_folders=["INBOX"],
        )

        # Verify we got the email
        assert len(items) == 2  # 1 email + 1 metadata
        assert items[0]["title"] == "Test Email"
        assert items[0]["message_id"] == "test-msg-1"

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetcher_uses_source_config_for_folders(self, mock_provider_class):
        """Test that fetcher uses source-specific config like folders."""
        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()

        # Credentials from Connection, folders from Source config
        items = fetcher.fetch(
            url="imap://imap.example.com",
            _connection_host="imap.example.com",
            _connection_port=993,
            _connection_username="test@example.com",
            _connection_password="secret123",
            _connection_use_ssl=True,
            imap_provider="generic",
            imap_folders=["INBOX", "Sent", "Archive"],  # Source-specific
        )

        # Verify folders from source config were used
        config_arg = mock_provider_class.call_args[0][0]
        assert config_arg.folders == ["INBOX", "Sent", "Archive"]


class TestFeedServiceConnectionIntegration:
    """Test that feed_service correctly resolves Connection and injects credentials.

    Tests _process_imap_source directly since it's the internal method that handles
    connection credential injection. FeedService is instantiated without a database_url
    and the session is passed directly to _process_imap_source.
    """

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_feed_service_injects_connection_credentials(
        self, mock_provider_class, test_db: Session, imap_connection: Connection, imap_source_with_connection: Source
    ):
        """Test that _process_imap_source resolves connection and injects credentials."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        # Create feed service and call _process_imap_source directly
        feed_service = FeedService()

        # Create minimal required mock objects
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        result = feed_service._process_imap_source(
            source=imap_source_with_connection,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )

        # Verify credentials were injected and used
        mock_provider_class.assert_called_once()
        config_arg = mock_provider_class.call_args[0][0]
        assert config_arg.host == "imap.example.com"
        assert config_arg.username == "test@example.com"
        assert config_arg.password == "secret123"

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_feed_service_updates_connection_health_on_success(
        self, mock_provider_class, test_db: Session, imap_connection: Connection, imap_source_with_connection: Source
    ):
        """Test that _process_imap_source updates connection health after successful fetch."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Mock successful fetch
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        # Initially, health timestamps should be None
        assert imap_connection.last_success_at is None

        feed_service = FeedService()
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        result = feed_service._process_imap_source(
            source=imap_source_with_connection,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )

        # Verify connection health was updated
        test_db.refresh(imap_connection)
        assert imap_connection.last_check_at is not None
        assert imap_connection.last_success_at is not None
        assert imap_connection.last_failure_at is None

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_feed_service_updates_connection_health_on_failure(
        self, mock_provider_class, test_db: Session, imap_connection: Connection, imap_source_with_connection: Source
    ):
        """Test that _process_imap_source updates connection health after failed fetch."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Mock failed fetch - the fetcher.fetch() raises IMAPError
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider_class.return_value = mock_provider

        # Initially, health timestamps should be None
        assert imap_connection.last_failure_at is None

        feed_service = FeedService()
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        # Patch the fetcher.fetch to raise an error
        with patch("reconly_core.fetchers.imap.IMAPFetcher.fetch", side_effect=IMAPError("Authentication failed")):
            result = feed_service._process_imap_source(
                source=imap_source_with_connection,
                feed=mock_feed,
                feed_run=mock_feed_run,
                summarizer=mock_summarizer,
                language="en",
                options=options,
                session=test_db,
            )

        # _process_imap_source catches exceptions and returns error dict
        assert result["success"] is False

        # Verify connection health was updated with failure
        test_db.refresh(imap_connection)
        assert imap_connection.last_check_at is not None
        assert imap_connection.last_failure_at is not None


class TestSourceWithoutConnection:
    """Test that sources without connection are handled gracefully."""

    def test_source_without_connection_fails(self, test_db: Session):
        """Test that IMAP source without connection fails with clear error."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Create source without connection (legacy source)
        source = Source(
            name="Legacy IMAP Source",
            type="imap",
            url="imap://imap.example.com",
            connection_id=None,  # No connection
            config={
                "provider": "generic",
                "folders": ["INBOX"],
            },
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        test_db.refresh(source)

        feed_service = FeedService()
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        # _process_imap_source returns an error dict instead of raising
        result = feed_service._process_imap_source(
            source=source,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )

        # Verify error message mentions missing connection
        assert result["success"] is False
        error_message = result["error"].lower()
        assert "connection" in error_message


class TestConnectionCredentialInjection:
    """Test the _connection_* credential injection pattern."""

    def test_connection_credentials_prefixed_correctly(self, test_db: Session, imap_connection: Connection):
        """Test that connection credentials can be decrypted with expected fields."""
        from reconly_core.services.connection_service import get_connection_decrypted

        # Get decrypted config
        config = get_connection_decrypted(test_db, imap_connection.id)

        # Verify config has expected fields
        assert "host" in config
        assert "username" in config
        assert "password" in config

        # When injected by feed_service, these become:
        # _connection_host, _connection_username, _connection_password
        # This is the pattern the IMAP fetcher expects

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_feed_service_prefixes_connection_credentials(
        self, mock_provider_class, test_db: Session, imap_connection: Connection, imap_source_with_connection: Source
    ):
        """Test that _process_imap_source prefixes connection config keys with _connection_."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        feed_service = FeedService()
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        # Fetch from source
        feed_service._process_imap_source(
            source=imap_source_with_connection,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )

        # Verify IMAPConfig was created with connection credentials
        mock_provider_class.assert_called_once()
        config_arg = mock_provider_class.call_args[0][0]

        # Verify credentials came from connection
        assert config_arg.host == "imap.example.com"
        assert config_arg.username == "test@example.com"
        assert config_arg.password == "secret123"
        assert config_arg.use_ssl is True


class TestMultipleSourcesUsingOneConnection:
    """Test that multiple sources can share the same connection."""

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_multiple_sources_share_connection(
        self, mock_provider_class, test_db: Session, imap_connection: Connection
    ):
        """Test that multiple sources can use the same connection with different configs."""
        from reconly_core.services.feed_service import FeedService, FeedRunOptions

        # Mock the IMAP provider
        mock_provider = MagicMock()
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider.fetch_emails.return_value = []
        mock_provider_class.return_value = mock_provider

        # Create two sources using the same connection but different folders
        # Note: _process_imap_source reads source.config.get('folders', ['INBOX'])
        source1 = Source(
            name="IMAP Source - INBOX",
            type="imap",
            url="imap://imap.example.com",
            connection_id=imap_connection.id,
            config={
                "provider": "generic",
                "folders": ["INBOX"],
            },
            enabled=True,
        )
        source2 = Source(
            name="IMAP Source - Sent",
            type="imap",
            url="imap://imap.example.com",
            connection_id=imap_connection.id,
            config={
                "provider": "generic",
                "folders": ["Sent"],
            },
            enabled=True,
        )
        test_db.add_all([source1, source2])
        test_db.commit()
        test_db.refresh(source1)
        test_db.refresh(source2)

        feed_service = FeedService()
        mock_feed = MagicMock(spec=Feed)
        mock_feed.default_language = "en"
        mock_feed_run = MagicMock(spec=FeedRun)
        mock_summarizer = MagicMock()
        options = FeedRunOptions()

        # Fetch from first source (INBOX)
        feed_service._process_imap_source(
            source=source1,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )
        config1 = mock_provider_class.call_args[0][0]
        assert config1.folders == ["INBOX"]

        # Reset mock
        mock_provider_class.reset_mock()

        # Fetch from second source (Sent)
        feed_service._process_imap_source(
            source=source2,
            feed=mock_feed,
            feed_run=mock_feed_run,
            summarizer=mock_summarizer,
            language="en",
            options=options,
            session=test_db,
        )
        config2 = mock_provider_class.call_args[0][0]
        assert config2.folders == ["Sent"]

        # Both should use same connection credentials
        assert config1.host == config2.host == "imap.example.com"
        assert config1.username == config2.username == "test@example.com"
        assert config1.password == config2.password == "secret123"
