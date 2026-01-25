"""Connection management API routes.

Connections provide reusable credential storage for email and other authenticated sources.
Credentials are encrypted at rest and NEVER exposed in API responses.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.connections import (
    ConnectionCreate,
    ConnectionListResponse,
    ConnectionResponse,
    ConnectionTestResult,
    ConnectionType,
    ConnectionUpdate,
)
from reconly_core.logging import get_logger
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

logger = get_logger(__name__)

router = APIRouter()


def _connection_to_response(connection, db: Session) -> ConnectionResponse:
    """Convert Connection model to ConnectionResponse with computed fields."""
    return ConnectionResponse(
        id=connection.id,
        name=connection.name,
        type=connection.type,
        provider=connection.provider,
        last_check_at=connection.last_check_at,
        last_success_at=connection.last_success_at,
        last_failure_at=connection.last_failure_at,
        has_password=bool(connection.config_encrypted),
        source_count=len(get_sources_using_connection(db, connection.id)),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.get("", response_model=ConnectionListResponse)
async def list_all_connections(
    type: str | None = None,
    db: Session = Depends(get_db),
) -> ConnectionListResponse:
    """List all connections with optional type filtering."""
    connections = list_connections(db, connection_type=type)
    items = [_connection_to_response(c, db) for c in connections]
    return ConnectionListResponse(total=len(items), items=items)


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_new_connection(
    connection: ConnectionCreate,
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    """Create a new connection with encrypted credentials."""
    try:
        db_connection = create_connection(
            db=db,
            name=connection.name,
            connection_type=connection.type.value,
            config=connection.config,
            provider=connection.provider.value if connection.provider else None,
        )
        db.commit()
        logger.info(
            "Created connection",
            connection_id=db_connection.id,
            connection_type=connection.type.value,
        )
        return _connection_to_response(db_connection, db)
    except ConnectionEncryptionError as e:
        logger.error("Failed to create connection - encryption error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to encrypt credentials. Ensure SECRET_KEY is set.",
        )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection_by_id(
    connection_id: int,
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    """Get a specific connection by ID (credentials excluded)."""
    connection = get_connection(db, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_to_response(connection, db)


@router.patch("/{connection_id}", response_model=ConnectionResponse)
async def update_connection_by_id(
    connection_id: int,
    connection_update: ConnectionUpdate,
    db: Session = Depends(get_db),
) -> ConnectionResponse:
    """Update an existing connection (partial update)."""
    try:
        db_connection = update_connection(
            db=db,
            connection_id=connection_id,
            name=connection_update.name,
            provider=connection_update.provider.value if connection_update.provider else None,
            config=connection_update.config,
        )
        db.commit()
        logger.info("Updated connection", connection_id=connection_id)
        return _connection_to_response(db_connection, db)
    except ConnectionNotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")
    except ConnectionEncryptionError as e:
        logger.error("Failed to update connection - encryption error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to encrypt credentials. Ensure SECRET_KEY is set.",
        )


@router.delete("/{connection_id}", status_code=204)
async def delete_connection_by_id(
    connection_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
) -> None:
    """Delete a connection. Use force=true if connection is still in use by sources."""
    try:
        deleted = delete_connection(db, connection_id, force=force)
        if not deleted:
            raise HTTPException(status_code=404, detail="Connection not found")
        db.commit()
        logger.info("Deleted connection", connection_id=connection_id)
    except ConnectionInUseError:
        sources = get_sources_using_connection(db, connection_id)
        source_names = [str(s.name) for s in sources[:5]]
        detail = f"Connection is in use by {len(sources)} source(s)"
        if source_names:
            detail += f": {', '.join(source_names)}"
            if len(sources) > 5:
                detail += f" and {len(sources) - 5} more"
        detail += ". Use force=true to delete anyway."
        raise HTTPException(status_code=409, detail=detail)


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(
    connection_id: int,
    db: Session = Depends(get_db),
) -> ConnectionTestResult:
    """Test a connection by verifying credentials work."""
    connection = get_connection(db, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        config = get_connection_decrypted(db, connection_id)
        if config is None:
            raise HTTPException(status_code=404, detail="Connection not found")
    except ConnectionEncryptionError as e:
        logger.error("Failed to decrypt connection config", connection_id=connection_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to decrypt credentials. SECRET_KEY may have changed.",
        )

    start_time = time.time()

    # Route to appropriate test function based on connection type
    test_functions = {
        ConnectionType.EMAIL_IMAP.value: _test_imap_connection,
        ConnectionType.HTTP_BASIC.value: _test_http_basic_connection,
        ConnectionType.API_KEY.value: _test_api_key_connection,
    }

    conn_type = str(connection.type)
    test_fn = test_functions.get(conn_type)
    if test_fn:
        result = test_fn(config)
    else:
        result = ConnectionTestResult(
            success=False,
            message=f"Testing not supported for connection type: {connection.type}",
        )

    result.response_time_ms = int((time.time() - start_time) * 1000)

    update_connection_health(db, connection_id, success=result.success)
    db.commit()

    logger.info(
        "Tested connection",
        connection_id=connection_id,
        success=result.success,
        response_time_ms=result.response_time_ms,
    )
    return result


def _test_imap_connection(config: dict) -> ConnectionTestResult:
    """Test IMAP connection with provided config."""
    from reconly_core.email import GenericIMAPProvider, IMAPConfig, IMAPError

    try:
        imap_config = IMAPConfig(
            provider="generic",
            host=config.get("host", ""),
            port=config.get("port", 993),
            username=config.get("username", ""),
            password=config.get("password", ""),
            use_ssl=config.get("use_ssl", True),
            folders=["INBOX"],
            timeout=10,
        )

        with GenericIMAPProvider(imap_config) as provider:
            if provider._connection:
                provider._connection.select("INBOX", readonly=True)

        return ConnectionTestResult(
            success=True,
            message="Successfully connected to IMAP server and authenticated.",
        )
    except IMAPError as e:
        return _imap_error_to_result(e)
    except Exception as e:
        logger.exception("IMAP connection test failed", error=str(e))
        return ConnectionTestResult(success=False, message=f"Connection test failed: {str(e)}")


def _imap_error_to_result(error: Exception) -> ConnectionTestResult:
    """Convert IMAP error to user-friendly ConnectionTestResult."""
    error_msg = str(error).lower()

    if "authentication" in error_msg or "login" in error_msg:
        message = "Authentication failed. Please check username and password."
    elif "timeout" in error_msg:
        message = "Connection timed out. IMAP server may be unreachable."
    elif "ssl" in error_msg or "certificate" in error_msg:
        message = "SSL/TLS connection failed. Try disabling SSL or check certificate settings."
    else:
        message = f"IMAP connection failed: {error}"

    return ConnectionTestResult(success=False, message=message)


def _test_http_basic_connection(config: dict) -> ConnectionTestResult:
    """Test HTTP Basic auth connection (validates credentials exist)."""
    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        return ConnectionTestResult(success=False, message="Username and password are required.")

    return ConnectionTestResult(
        success=True,
        message="HTTP Basic credentials are configured. Cannot verify without target URL.",
    )


def _test_api_key_connection(config: dict) -> ConnectionTestResult:
    """Test API key connection (validates key exists)."""
    api_key = config.get("api_key", "")

    if not api_key:
        return ConnectionTestResult(success=False, message="API key is required.")

    endpoint = config.get("endpoint")
    if endpoint:
        return ConnectionTestResult(success=True, message=f"API key is configured for endpoint: {endpoint}")

    return ConnectionTestResult(
        success=True,
        message="API key is configured. Cannot verify without target endpoint.",
    )
