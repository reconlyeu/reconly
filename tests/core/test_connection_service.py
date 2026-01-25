"""Unit tests for Connection service.

Tests connection CRUD operations, encryption/decryption, and health tracking.
"""
import os
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from reconly_core.database.models import Connection, Source
from reconly_core.services.connection_service import (
    ConnectionEncryptionError,
    ConnectionInUseError,
    ConnectionNotFoundError,
    create_connection,
    delete_connection,
    get_connection,
    get_connection_decrypted,
    get_sources_using_connection,
    list_connections,
    update_connection,
    update_connection_health,
)


@pytest.fixture(autouse=True)
def set_secret_key(monkeypatch):
    """Set SECRET_KEY for all tests in this module."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-connection-tests-minimum-32-chars")


@pytest.fixture
def sample_connection(test_db: Session) -> Connection:
    """Create a sample connection for testing."""
    connection = create_connection(
        db=test_db,
        name="Test Connection",
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


class TestCreateConnection:
    """Test connection creation with encryption."""

    def test_create_connection_encrypts_config(self, test_db: Session):
        """Test that create_connection encrypts the config correctly."""
        config = {
            "host": "mail.example.com",
            "port": 993,
            "username": "user@example.com",
            "password": "my_secret_password",
            "use_ssl": True,
        }

        connection = create_connection(
            db=test_db,
            name="Email Connection",
            connection_type="email_imap",
            config=config,
            provider="gmail",
        )
        test_db.commit()

        # Verify connection was created
        assert connection.id is not None
        assert connection.name == "Email Connection"
        assert connection.type == "email_imap"
        assert connection.provider == "gmail"

        # Verify config is encrypted (not plain text)
        assert connection.config_encrypted is not None
        assert "my_secret_password" not in connection.config_encrypted
        assert "user@example.com" not in connection.config_encrypted

    def test_create_connection_without_provider(self, test_db: Session):
        """Test creating a connection without a provider."""
        config = {"api_key": "sk-test123", "endpoint": "https://api.example.com"}

        connection = create_connection(
            db=test_db,
            name="API Connection",
            connection_type="api_key",
            config=config,
            provider=None,
        )
        test_db.commit()

        assert connection.id is not None
        assert connection.provider is None

    def test_create_connection_with_user_id(self, test_db: Session):
        """Test creating a connection associated with a user."""
        config = {"host": "imap.test.com", "port": 993, "username": "test", "password": "pass"}

        connection = create_connection(
            db=test_db,
            name="User Connection",
            connection_type="email_imap",
            config=config,
            user_id=1,
        )
        test_db.commit()

        assert connection.user_id == 1

    def test_create_connection_without_secret_key(self, test_db: Session, monkeypatch):
        """Test that connection creation fails if SECRET_KEY is not set."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        config = {"host": "imap.test.com", "port": 993, "username": "test", "password": "pass"}

        with pytest.raises(ConnectionEncryptionError) as exc_info:
            create_connection(
                db=test_db,
                name="Test Connection",
                connection_type="email_imap",
                config=config,
            )

        assert "Failed to encrypt config" in str(exc_info.value)


class TestGetConnection:
    """Test connection retrieval operations."""

    def test_get_connection_by_id(self, test_db: Session, sample_connection: Connection):
        """Test retrieving a connection by ID."""
        connection = get_connection(test_db, sample_connection.id)

        assert connection is not None
        assert connection.id == sample_connection.id
        assert connection.name == "Test Connection"
        assert connection.type == "email_imap"

    def test_get_connection_not_found(self, test_db: Session):
        """Test retrieving a non-existent connection."""
        connection = get_connection(test_db, 99999)
        assert connection is None

    def test_get_connection_with_user_filter(self, test_db: Session):
        """Test retrieving connection filtered by user_id."""
        # Create connection with user_id=1
        connection1 = create_connection(
            db=test_db,
            name="User 1 Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "user1", "password": "pass1"},
            user_id=1,
        )
        test_db.commit()

        # Create connection with user_id=2
        connection2 = create_connection(
            db=test_db,
            name="User 2 Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "user2", "password": "pass2"},
            user_id=2,
        )
        test_db.commit()

        # Get connection1 with user_id filter
        result = get_connection(test_db, connection1.id, user_id=1)
        assert result is not None
        assert result.id == connection1.id

        # Try to get connection1 with wrong user_id
        result = get_connection(test_db, connection1.id, user_id=2)
        assert result is None

    def test_get_connection_decrypted(self, test_db: Session, sample_connection: Connection):
        """Test retrieving and decrypting connection config."""
        config = get_connection_decrypted(test_db, sample_connection.id)

        assert config is not None
        assert config["host"] == "imap.example.com"
        assert config["port"] == 993
        assert config["username"] == "test@example.com"
        assert config["password"] == "secret123"
        assert config["use_ssl"] is True

    def test_get_connection_decrypted_not_found(self, test_db: Session):
        """Test decrypting a non-existent connection."""
        config = get_connection_decrypted(test_db, 99999)
        assert config is None

    def test_get_connection_decrypted_without_secret_key(
        self, test_db: Session, sample_connection: Connection, monkeypatch
    ):
        """Test that decryption fails if SECRET_KEY is changed."""
        # Change SECRET_KEY to a different value
        monkeypatch.setenv("SECRET_KEY", "different-secret-key-with-minimum-32-characters-here")

        with pytest.raises(ConnectionEncryptionError) as exc_info:
            get_connection_decrypted(test_db, sample_connection.id)

        assert "Failed to decrypt config" in str(exc_info.value)


class TestListConnections:
    """Test connection listing with filters."""

    def test_list_connections_empty(self, test_db: Session):
        """Test listing connections when none exist."""
        connections = list_connections(test_db)
        assert connections == []

    def test_list_connections(self, test_db: Session, sample_connection: Connection):
        """Test listing all connections."""
        connections = list_connections(test_db)
        assert len(connections) == 1
        assert connections[0].id == sample_connection.id

    def test_list_connections_multiple(self, test_db: Session):
        """Test listing multiple connections."""
        connection1 = create_connection(
            db=test_db,
            name="Connection 1",
            connection_type="email_imap",
            config={"host": "imap1.test.com", "username": "user1", "password": "pass1"},
        )
        connection2 = create_connection(
            db=test_db,
            name="Connection 2",
            connection_type="api_key",
            config={"api_key": "key123"},
        )
        test_db.commit()

        connections = list_connections(test_db)
        assert len(connections) == 2
        # Should be ordered by name
        assert connections[0].name == "Connection 1"
        assert connections[1].name == "Connection 2"

    def test_list_connections_filter_by_type(self, test_db: Session):
        """Test filtering connections by type."""
        create_connection(
            db=test_db,
            name="IMAP Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "user", "password": "pass"},
        )
        create_connection(
            db=test_db,
            name="API Connection",
            connection_type="api_key",
            config={"api_key": "key123"},
        )
        test_db.commit()

        # Filter by email_imap
        imap_connections = list_connections(test_db, connection_type="email_imap")
        assert len(imap_connections) == 1
        assert imap_connections[0].type == "email_imap"

        # Filter by api_key
        api_connections = list_connections(test_db, connection_type="api_key")
        assert len(api_connections) == 1
        assert api_connections[0].type == "api_key"

    def test_list_connections_filter_by_provider(self, test_db: Session):
        """Test filtering connections by provider."""
        create_connection(
            db=test_db,
            name="Gmail Connection",
            connection_type="email_imap",
            config={"host": "imap.gmail.com", "username": "user@gmail.com", "password": "pass"},
            provider="gmail",
        )
        create_connection(
            db=test_db,
            name="Outlook Connection",
            connection_type="email_imap",
            config={"host": "outlook.office365.com", "username": "user@outlook.com", "password": "pass"},
            provider="outlook",
        )
        test_db.commit()

        # Filter by gmail
        gmail_connections = list_connections(test_db, provider="gmail")
        assert len(gmail_connections) == 1
        assert gmail_connections[0].provider == "gmail"

        # Filter by outlook
        outlook_connections = list_connections(test_db, provider="outlook")
        assert len(outlook_connections) == 1
        assert outlook_connections[0].provider == "outlook"

    def test_list_connections_filter_by_user_id(self, test_db: Session):
        """Test filtering connections by user_id."""
        create_connection(
            db=test_db,
            name="User 1 Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "user1", "password": "pass1"},
            user_id=1,
        )
        create_connection(
            db=test_db,
            name="User 2 Connection",
            connection_type="email_imap",
            config={"host": "imap.test.com", "username": "user2", "password": "pass2"},
            user_id=2,
        )
        test_db.commit()

        # Filter by user_id=1
        user1_connections = list_connections(test_db, user_id=1)
        assert len(user1_connections) == 1
        assert user1_connections[0].user_id == 1

        # Filter by user_id=2
        user2_connections = list_connections(test_db, user_id=2)
        assert len(user2_connections) == 1
        assert user2_connections[0].user_id == 2


class TestUpdateConnection:
    """Test connection update operations."""

    def test_update_connection_name(self, test_db: Session, sample_connection: Connection):
        """Test updating connection name."""
        updated = update_connection(test_db, sample_connection.id, name="Updated Name")
        test_db.commit()

        assert updated.name == "Updated Name"
        assert updated.type == sample_connection.type  # Unchanged

    def test_update_connection_type(self, test_db: Session, sample_connection: Connection):
        """Test updating connection type."""
        updated = update_connection(test_db, sample_connection.id, connection_type="http_basic")
        test_db.commit()

        assert updated.type == "http_basic"

    def test_update_connection_provider(self, test_db: Session, sample_connection: Connection):
        """Test updating connection provider."""
        updated = update_connection(test_db, sample_connection.id, provider="gmail")
        test_db.commit()

        assert updated.provider == "gmail"

    def test_update_connection_config(self, test_db: Session, sample_connection: Connection):
        """Test updating connection config with re-encryption."""
        new_config = {
            "host": "imap.newhost.com",
            "port": 993,
            "username": "newuser@example.com",
            "password": "newsecret456",
            "use_ssl": False,
        }

        updated = update_connection(test_db, sample_connection.id, config=new_config)
        test_db.commit()

        # Verify config is updated and encrypted
        decrypted = get_connection_decrypted(test_db, sample_connection.id)
        assert decrypted["host"] == "imap.newhost.com"
        assert decrypted["username"] == "newuser@example.com"
        assert decrypted["password"] == "newsecret456"
        assert decrypted["use_ssl"] is False

    def test_update_connection_partial_update(self, test_db: Session, sample_connection: Connection):
        """Test partial update only updates specified fields."""
        # Only update name, leave everything else unchanged
        updated = update_connection(test_db, sample_connection.id, name="New Name Only")
        test_db.commit()

        assert updated.name == "New Name Only"
        assert updated.type == "email_imap"  # Unchanged
        assert updated.provider == "generic"  # Unchanged

        # Verify config is still decryptable and unchanged
        decrypted = get_connection_decrypted(test_db, sample_connection.id)
        assert decrypted["host"] == "imap.example.com"
        assert decrypted["password"] == "secret123"

    def test_update_connection_not_found(self, test_db: Session):
        """Test updating a non-existent connection."""
        with pytest.raises(ConnectionNotFoundError) as exc_info:
            update_connection(test_db, 99999, name="New Name")

        assert "Connection 99999 not found" in str(exc_info.value)

    def test_update_connection_updates_timestamp(self, test_db: Session, sample_connection: Connection):
        """Test that updating a connection updates the updated_at timestamp."""
        original_updated_at = sample_connection.updated_at

        # Update connection
        updated = update_connection(test_db, sample_connection.id, name="Updated")
        test_db.commit()

        # Verify updated_at changed
        assert updated.updated_at is not None
        if original_updated_at:
            assert updated.updated_at >= original_updated_at


class TestDeleteConnection:
    """Test connection deletion operations."""

    def test_delete_connection_success(self, test_db: Session, sample_connection: Connection):
        """Test deleting a connection that is not in use."""
        deleted = delete_connection(test_db, sample_connection.id)
        test_db.commit()

        assert deleted is True

        # Verify connection is deleted
        connection = get_connection(test_db, sample_connection.id)
        assert connection is None

    def test_delete_connection_not_found(self, test_db: Session):
        """Test deleting a non-existent connection."""
        deleted = delete_connection(test_db, 99999)
        assert deleted is False

    def test_delete_connection_in_use_raises_error(self, test_db: Session, sample_connection: Connection):
        """Test that deleting a connection in use by sources raises an error."""
        # Create a source using the connection
        source = Source(
            name="Test Source",
            type="imap",
            url="imap://test",
            connection_id=sample_connection.id,
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()

        # Try to delete connection without force
        with pytest.raises(ConnectionInUseError) as exc_info:
            delete_connection(test_db, sample_connection.id, force=False)

        assert f"Connection {sample_connection.id} is in use by 1 source(s)" in str(exc_info.value)
        assert "force=True" in str(exc_info.value)

        # Verify connection still exists
        connection = get_connection(test_db, sample_connection.id)
        assert connection is not None

    def test_delete_connection_in_use_with_force(self, test_db: Session, sample_connection: Connection):
        """Test that force=True allows deleting a connection in use."""
        # Create a source using the connection
        source = Source(
            name="Test Source",
            type="imap",
            url="imap://test",
            connection_id=sample_connection.id,
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()
        source_id = source.id

        # Delete with force=True
        deleted = delete_connection(test_db, sample_connection.id, force=True)
        test_db.commit()

        assert deleted is True

        # Verify connection is deleted
        connection = get_connection(test_db, sample_connection.id)
        assert connection is None

        # Verify source's connection_id is set to NULL (ON DELETE SET NULL)
        test_db.expire_all()  # Clear cache to reload from DB
        source = test_db.query(Source).filter(Source.id == source_id).first()
        assert source is not None
        assert source.connection_id is None


class TestUpdateConnectionHealth:
    """Test connection health tracking."""

    def test_update_connection_health_success(self, test_db: Session, sample_connection: Connection):
        """Test updating connection health after success."""
        # Initially, health timestamps should be None
        assert sample_connection.last_success_at is None

        # Update health with success
        updated = update_connection_health(test_db, sample_connection.id, success=True)
        test_db.commit()

        assert updated is not None
        assert updated.last_check_at is not None
        assert updated.last_success_at is not None
        # last_failure_at should still be None
        assert updated.last_failure_at is None

    def test_update_connection_health_failure(self, test_db: Session, sample_connection: Connection):
        """Test updating connection health after failure."""
        # Initially, health timestamps should be None
        assert sample_connection.last_failure_at is None

        # Update health with failure
        updated = update_connection_health(test_db, sample_connection.id, success=False)
        test_db.commit()

        assert updated is not None
        assert updated.last_check_at is not None
        assert updated.last_failure_at is not None
        # last_success_at should still be None
        assert updated.last_success_at is None

    def test_update_connection_health_multiple_calls(self, test_db: Session, sample_connection: Connection):
        """Test multiple health updates track timestamps correctly."""
        # First success
        update_connection_health(test_db, sample_connection.id, success=True)
        test_db.commit()
        test_db.refresh(sample_connection)

        first_success_at = sample_connection.last_success_at
        assert first_success_at is not None

        # Then failure
        update_connection_health(test_db, sample_connection.id, success=False)
        test_db.commit()
        test_db.refresh(sample_connection)

        assert sample_connection.last_failure_at is not None
        # last_success_at should still be the first timestamp
        assert sample_connection.last_success_at == first_success_at

        # Another success
        update_connection_health(test_db, sample_connection.id, success=True)
        test_db.commit()
        test_db.refresh(sample_connection)

        # last_success_at should be updated
        assert sample_connection.last_success_at is not None
        assert sample_connection.last_success_at >= first_success_at

    def test_update_connection_health_not_found(self, test_db: Session):
        """Test updating health for non-existent connection."""
        updated = update_connection_health(test_db, 99999, success=True)
        assert updated is None


class TestGetSourcesUsingConnection:
    """Test retrieving sources that use a connection."""

    def test_get_sources_using_connection_empty(self, test_db: Session, sample_connection: Connection):
        """Test getting sources when none use the connection."""
        sources = get_sources_using_connection(test_db, sample_connection.id)
        assert sources == []

    def test_get_sources_using_connection_single(self, test_db: Session, sample_connection: Connection):
        """Test getting sources that use a connection."""
        source = Source(
            name="IMAP Source",
            type="imap",
            url="imap://test",
            connection_id=sample_connection.id,
            enabled=True,
        )
        test_db.add(source)
        test_db.commit()

        sources = get_sources_using_connection(test_db, sample_connection.id)
        assert len(sources) == 1
        assert sources[0].id == source.id
        assert sources[0].name == "IMAP Source"

    def test_get_sources_using_connection_multiple(self, test_db: Session, sample_connection: Connection):
        """Test getting multiple sources that use the same connection."""
        source1 = Source(
            name="IMAP Source 1",
            type="imap",
            url="imap://test1",
            connection_id=sample_connection.id,
            enabled=True,
        )
        source2 = Source(
            name="IMAP Source 2",
            type="imap",
            url="imap://test2",
            connection_id=sample_connection.id,
            enabled=True,
        )
        test_db.add_all([source1, source2])
        test_db.commit()

        sources = get_sources_using_connection(test_db, sample_connection.id)
        assert len(sources) == 2
        assert {s.name for s in sources} == {"IMAP Source 1", "IMAP Source 2"}

    def test_get_sources_using_connection_excludes_others(self, test_db: Session):
        """Test that only sources using the specified connection are returned."""
        # Create two connections
        connection1 = create_connection(
            db=test_db,
            name="Connection 1",
            connection_type="email_imap",
            config={"host": "imap1.test.com", "username": "user1", "password": "pass1"},
        )
        connection2 = create_connection(
            db=test_db,
            name="Connection 2",
            connection_type="email_imap",
            config={"host": "imap2.test.com", "username": "user2", "password": "pass2"},
        )
        test_db.commit()

        # Create sources for each connection
        source1 = Source(
            name="Source for Connection 1",
            type="imap",
            url="imap://test1",
            connection_id=connection1.id,
            enabled=True,
        )
        source2 = Source(
            name="Source for Connection 2",
            type="imap",
            url="imap://test2",
            connection_id=connection2.id,
            enabled=True,
        )
        test_db.add_all([source1, source2])
        test_db.commit()

        # Get sources for connection1
        sources = get_sources_using_connection(test_db, connection1.id)
        assert len(sources) == 1
        assert sources[0].name == "Source for Connection 1"

        # Get sources for connection2
        sources = get_sources_using_connection(test_db, connection2.id)
        assert len(sources) == 1
        assert sources[0].name == "Source for Connection 2"
