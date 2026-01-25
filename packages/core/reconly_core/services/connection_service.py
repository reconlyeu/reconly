"""Connection service for managing reusable credentials.

This service handles CRUD operations for Connection entities with encrypted
config storage. Credentials are stored as encrypted JSON blobs using Fernet
symmetric encryption.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from reconly_core.database.models import Connection, Source
from reconly_core.email.crypto import (
    encrypt_token,
    decrypt_token,
    TokenEncryptionError,
)


logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Base exception for connection service errors."""
    pass


class ConnectionNotFoundError(ConnectionError):
    """Raised when a connection is not found."""
    pass


class ConnectionInUseError(ConnectionError):
    """Raised when trying to delete a connection that is still in use by sources."""
    pass


class ConnectionEncryptionError(ConnectionError):
    """Raised when encryption/decryption fails."""
    pass


def _encrypt_config(config: Dict[str, Any]) -> str:
    """Encrypt a config dictionary to a string for storage.

    Args:
        config: Dictionary containing connection configuration

    Returns:
        Encrypted config string

    Raises:
        ConnectionEncryptionError: If encryption fails
    """
    try:
        config_json = json.dumps(config, separators=(',', ':'))
        return encrypt_token(config_json)
    except TokenEncryptionError as e:
        raise ConnectionEncryptionError(f"Failed to encrypt config: {e}") from e
    except (TypeError, ValueError) as e:
        raise ConnectionEncryptionError(f"Failed to serialize config: {e}") from e


def _decrypt_config(encrypted_config: str) -> Dict[str, Any]:
    """Decrypt a config string to a dictionary.

    Args:
        encrypted_config: Encrypted config string from database

    Returns:
        Decrypted config dictionary

    Raises:
        ConnectionEncryptionError: If decryption fails
    """
    try:
        config_json = decrypt_token(encrypted_config)
        return json.loads(config_json)
    except TokenEncryptionError as e:
        raise ConnectionEncryptionError(f"Failed to decrypt config: {e}") from e
    except json.JSONDecodeError as e:
        raise ConnectionEncryptionError(f"Failed to parse config: {e}") from e


def create_connection(
    db: Session,
    name: str,
    connection_type: str,
    config: Dict[str, Any],
    provider: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Connection:
    """Create a new connection with encrypted config.

    Args:
        db: Database session
        name: Display name for the connection
        connection_type: Connection type (email_imap, email_oauth, http_basic, api_key)
        config: Configuration dictionary to encrypt and store
        provider: Provider name for email types (gmail, outlook, generic)
        user_id: User ID to associate with the connection

    Returns:
        Created Connection instance

    Raises:
        ConnectionEncryptionError: If config encryption fails
    """
    encrypted = _encrypt_config(config)

    connection = Connection(
        name=name,
        type=connection_type,
        provider=provider,
        config_encrypted=encrypted,
        user_id=user_id,
        created_at=datetime.utcnow(),
    )

    db.add(connection)
    db.flush()
    logger.info(f"Created connection: id={connection.id}, name='{name}', type='{connection_type}'")

    return connection


def get_connection(
    db: Session,
    connection_id: int,
    user_id: Optional[int] = None,
) -> Optional[Connection]:
    """Get a connection by ID without decrypting config.

    Args:
        db: Database session
        connection_id: Connection ID
        user_id: Optional user ID for filtering

    Returns:
        Connection instance or None if not found
    """
    query = db.query(Connection).filter(Connection.id == connection_id)

    if user_id is not None:
        query = query.filter(Connection.user_id == user_id)

    return query.first()


def get_connection_decrypted(
    db: Session,
    connection_id: int,
    user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Get a connection's decrypted config dictionary.

    Args:
        db: Database session
        connection_id: Connection ID
        user_id: Optional user ID for filtering

    Returns:
        Decrypted config dictionary or None if connection not found

    Raises:
        ConnectionEncryptionError: If config decryption fails
    """
    connection = get_connection(db, connection_id, user_id)
    if connection is None:
        return None

    return _decrypt_config(connection.config_encrypted)


def list_connections(
    db: Session,
    user_id: Optional[int] = None,
    connection_type: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[Connection]:
    """List connections with optional filters.

    Args:
        db: Database session
        user_id: Optional user ID for filtering
        connection_type: Optional connection type filter
        provider: Optional provider filter

    Returns:
        List of Connection instances
    """
    query = db.query(Connection)

    if user_id is not None:
        query = query.filter(Connection.user_id == user_id)
    if connection_type is not None:
        query = query.filter(Connection.type == connection_type)
    if provider is not None:
        query = query.filter(Connection.provider == provider)

    return query.order_by(Connection.name).all()


def update_connection(
    db: Session,
    connection_id: int,
    name: Optional[str] = None,
    connection_type: Optional[str] = None,
    provider: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> Connection:
    """Update a connection, re-encrypting config if changed.

    Args:
        db: Database session
        connection_id: Connection ID to update
        name: New display name (optional)
        connection_type: New connection type (optional)
        provider: New provider (optional)
        config: New configuration dictionary to encrypt (optional)
        user_id: User ID for filtering (optional)

    Returns:
        Updated Connection instance

    Raises:
        ConnectionNotFoundError: If connection not found
        ConnectionEncryptionError: If config encryption fails
    """
    connection = get_connection(db, connection_id, user_id)
    if connection is None:
        raise ConnectionNotFoundError(f"Connection {connection_id} not found")

    if name is not None:
        connection.name = name
    if connection_type is not None:
        connection.type = connection_type
    if provider is not None:
        connection.provider = provider
    if config is not None:
        connection.config_encrypted = _encrypt_config(config)

    connection.updated_at = datetime.utcnow()
    db.flush()

    logger.info(f"Updated connection: id={connection_id}")
    return connection


def delete_connection(
    db: Session,
    connection_id: int,
    user_id: Optional[int] = None,
    force: bool = False,
) -> bool:
    """Delete a connection.

    By default, this checks if the connection is in use by any sources
    and raises an error if so. Use force=True to delete anyway (sources
    will have their connection_id set to NULL via ON DELETE SET NULL).

    Args:
        db: Database session
        connection_id: Connection ID to delete
        user_id: User ID for filtering (optional)
        force: If True, delete even if in use by sources

    Returns:
        True if deleted, False if not found

    Raises:
        ConnectionInUseError: If connection is in use and force=False
    """
    connection = get_connection(db, connection_id, user_id)
    if connection is None:
        return False

    # Check if in use by any sources
    source_count = db.query(Source).filter(Source.connection_id == connection_id).count()
    if source_count > 0 and not force:
        raise ConnectionInUseError(
            f"Connection {connection_id} is in use by {source_count} source(s). "
            "Use force=True to delete anyway."
        )

    db.delete(connection)
    db.flush()

    logger.info(f"Deleted connection: id={connection_id}")
    return True


def update_connection_health(
    db: Session,
    connection_id: int,
    success: bool,
) -> Optional[Connection]:
    """Update connection health timestamps after a check.

    Args:
        db: Database session
        connection_id: Connection ID
        success: Whether the health check succeeded

    Returns:
        Updated Connection or None if not found
    """
    connection = get_connection(db, connection_id)
    if connection is None:
        return None

    if success:
        connection.update_health_success()
    else:
        connection.update_health_failure()

    db.flush()
    return connection


def get_sources_using_connection(
    db: Session,
    connection_id: int,
) -> List[Source]:
    """Get all sources using a specific connection.

    Args:
        db: Database session
        connection_id: Connection ID

    Returns:
        List of Source instances using this connection
    """
    return db.query(Source).filter(Source.connection_id == connection_id).all()
