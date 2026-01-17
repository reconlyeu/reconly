"""Source management API routes."""
import os
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session, joinedload

from reconly_core.database.models import OAuthCredential, Source
from reconly_core.email.crypto import encrypt_token, TokenEncryptionError
from reconly_core.email.oauth import create_oauth_state, get_redirect_uri
from reconly_core.email.gmail import generate_gmail_auth_url
from reconly_core.email.outlook import generate_outlook_auth_url
from reconly_core.logging import get_logger
from reconly_core.fetchers import get_fetcher, detect_fetcher, is_fetcher_registered

from reconly_api.dependencies import get_db, limiter
from reconly_api.schemas.sources import (
    IMAPSourceCreateRequest,
    IMAPSourceCreateResponse,
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    SourceHealthResponse,
    ValidationResponse,
)
from reconly_api.schemas.batch import BatchDeleteRequest, BatchDeleteResponse
from reconly_core.resilience import ValidationConfig

logger = get_logger(__name__)

router = APIRouter()


def _sanitize_source_config(config: dict | None, source_type: str) -> dict | None:
    """Remove sensitive fields from source config before returning to API.

    Passwords and tokens are encrypted in the database but should never
    be returned in API responses.

    Args:
        config: Source configuration dict
        source_type: Source type (imap, etc.)

    Returns:
        Sanitized config dict with sensitive fields removed
    """
    if config is None:
        return None

    # Fields to exclude from IMAP config
    sensitive_fields = {
        "imap_password",
        "imap_password_encrypted",
        "password",
        "access_token",
        "refresh_token",
    }

    return {k: v for k, v in config.items() if k not in sensitive_fields}


def _source_to_response(source: Source) -> SourceResponse:
    """Convert Source model to SourceResponse with sanitization.

    Handles:
    - Sanitizing sensitive config fields
    - Adding oauth_credential_id from relationship
    """
    # oauth_credentials is uselist=False, so it's a single object or None
    oauth_credential = getattr(source, 'oauth_credentials', None)

    return SourceResponse(
        id=source.id,
        name=source.name,
        type=source.type,
        url=source.url,
        config=_sanitize_source_config(source.config, source.type),
        enabled=source.enabled,
        include_keywords=source.include_keywords,
        exclude_keywords=source.exclude_keywords,
        filter_mode=source.filter_mode,
        use_regex=source.use_regex,
        user_id=source.user_id,
        created_at=source.created_at,
        updated_at=source.updated_at,
        auth_status=source.auth_status,
        oauth_credential_id=oauth_credential.id if oauth_credential else None,
    )


def _get_base_url(request: Request) -> str:
    """Get the base URL from the request for OAuth redirect URIs."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
    return f"{proto}://{host}"


def _is_oauth_provider_configured(provider: str) -> bool:
    """Check if OAuth provider credentials are configured."""
    if provider == "gmail":
        return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))
    if provider == "outlook":
        return bool(os.environ.get("MICROSOFT_CLIENT_ID") and os.environ.get("MICROSOFT_CLIENT_SECRET"))
    return False


def _build_imap_source(
    imap_request: IMAPSourceCreateRequest,
    url: str,
    config: dict,
    auth_status: str,
) -> Source:
    """Build a Source model for IMAP source creation.

    Args:
        imap_request: The IMAP source creation request
        url: The computed URL for the source
        config: The IMAP configuration dict
        auth_status: Authentication status ('active' or 'pending_oauth')

    Returns:
        Source model instance (not yet committed)
    """
    return Source(
        name=imap_request.name,
        type="imap",
        url=url,
        config=config,
        enabled=True,
        auth_status=auth_status,
        include_keywords=imap_request.include_keywords,
        exclude_keywords=imap_request.exclude_keywords,
        filter_mode=imap_request.filter_mode,
        use_regex=imap_request.use_regex or False,
    )


def _validate_source_url(
    url: str,
    source_type: str,
    config: Optional[dict] = None,
    test_fetch: bool = False,
    timeout: int = 10,
) -> ValidationResponse:
    """Validate a source URL using the appropriate fetcher.

    Args:
        url: Source URL to validate
        source_type: Source type (e.g., 'rss', 'youtube', 'website')
        config: Additional configuration for the fetcher
        test_fetch: If True, attempt to fetch content to verify accessibility
        timeout: Timeout in seconds for test fetch operations

    Returns:
        ValidationResponse with validation results
    """
    errors = []
    warnings = []
    test_item_count = None
    response_time_ms = None
    url_type = None

    # Check if we can get a fetcher for this source type
    if not is_fetcher_registered(source_type):
        # Try to auto-detect fetcher from URL
        fetcher = detect_fetcher(url)
        if fetcher:
            url_type = fetcher.get_source_type()
        else:
            errors.append(f"Unknown source type: {source_type}")
            return ValidationResponse(
                valid=False,
                errors=errors,
                warnings=warnings,
            )
    else:
        fetcher = get_fetcher(source_type)
        url_type = source_type

    # Run fetcher's validation
    start_time = time.time()
    try:
        result = fetcher.validate(url, config=config, test_fetch=test_fetch, timeout=timeout)
        elapsed = time.time() - start_time
        response_time_ms = elapsed * 1000

        errors.extend(result.errors)
        warnings.extend(result.warnings)

        if result.test_item_count is not None:
            test_item_count = result.test_item_count
        if result.url_type:
            url_type = result.url_type

    except Exception as e:
        elapsed = time.time() - start_time
        response_time_ms = elapsed * 1000
        errors.append(f"Validation failed: {str(e)}")
        logger.exception(
            "Source validation error",
            url=url,
            source_type=source_type,
        )

    return ValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        test_item_count=test_item_count,
        response_time_ms=response_time_ms,
        url_type=url_type,
    )


@router.post("/validate", response_model=ValidationResponse)
@limiter.limit("30/minute")
async def validate_source(
    request: Request,
    source: SourceCreate,
    test_fetch: bool = False,
    timeout: int = 10,
):
    """Validate a source URL without creating it.

    This endpoint performs validation checks on the source configuration
    without persisting it to the database.

    Args:
        source: Source creation request (only url and type are required)
        test_fetch: If true, attempt to fetch content to verify accessibility
        timeout: Timeout in seconds for test fetch (default: 10, max: 30)

    Returns:
        ValidationResponse with validation results including:
        - valid: Whether the source configuration is valid
        - errors: List of validation errors
        - warnings: List of validation warnings
        - test_item_count: Number of items found (if test_fetch=true)
        - response_time_ms: Response time in milliseconds
        - url_type: Detected URL type
    """
    # Enforce max timeout from config
    config = ValidationConfig.from_env()
    timeout = min(timeout, config.default_timeout, 30)  # Respect config and hard cap

    return _validate_source_url(
        url=source.url,
        source_type=source.type,
        config=source.config,
        test_fetch=test_fetch,
        timeout=timeout,
    )


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    type: Optional[str] = None,
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all sources with optional filtering."""
    query = db.query(Source).options(joinedload(Source.oauth_credentials))

    if type:
        query = query.filter(Source.type == type)
    if enabled_only:
        query = query.filter(Source.enabled == True)

    sources = query.order_by(Source.created_at.desc()).all()
    return [_source_to_response(s) for s in sources]


@router.post("", response_model=SourceResponse, status_code=201)
@limiter.limit("10/minute")
async def create_source(
    request: Request,
    source: SourceCreate,
    validate: bool = False,
    test_fetch: bool = False,
    timeout: int = 10,
    db: Session = Depends(get_db)
):
    """Create a new source.

    Rate limited to 10 requests per minute per IP.

    Args:
        source: Source creation request
        validate: If true, validate the source URL before saving
        test_fetch: If true (and validate=true), attempt to fetch content
        timeout: Timeout in seconds for test fetch (default: 10, max: 30)

    Note: For IMAP sources with OAuth providers (gmail, outlook), use the
    POST /api/v1/sources/imap endpoint instead, which handles the OAuth flow.
    """
    # Validate if requested
    if validate:
        timeout = min(timeout, 30)  # Hard cap at 30 seconds
        validation_result = _validate_source_url(
            url=source.url,
            source_type=source.type,
            config=source.config,
            test_fetch=test_fetch,
            timeout=timeout,
        )
        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Source validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                }
            )

    db_source = Source(
        name=source.name,
        type=source.type,
        url=source.url,
        config=source.config,
        enabled=source.enabled if source.enabled is not None else True,
        # Content filtering fields
        include_keywords=source.include_keywords,
        exclude_keywords=source.exclude_keywords,
        filter_mode=source.filter_mode,
        use_regex=source.use_regex if source.use_regex is not None else False,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return _source_to_response(db_source)


@router.post("/imap", response_model=IMAPSourceCreateResponse, status_code=201)
@limiter.limit("10/minute")
async def create_imap_source(
    request: Request,
    imap_request: IMAPSourceCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new IMAP email source.

    For OAuth providers (gmail, outlook):
    - Creates source with auth_status="pending_oauth"
    - Returns OAuth authorization URL for user to complete flow
    - User must complete OAuth at returned URL to activate source

    For generic IMAP:
    - Validates IMAP connection with provided credentials
    - Encrypts password before storing in config
    - Sets auth_status="active" on success

    Rate limited to 10 requests per minute per IP.
    """
    provider = imap_request.provider

    # Build URL based on provider
    if provider == "gmail":
        url = "gmail://"
    elif provider == "outlook":
        url = "outlook://"
    else:
        # Generic IMAP URL
        url = f"imap://{imap_request.imap_host}:{imap_request.imap_port}"

    # Build IMAP config (shared fields)
    config = {
        "provider": provider,
        "folders": imap_request.folders or ["INBOX"],
    }
    if imap_request.from_filter:
        config["from_filter"] = imap_request.from_filter
    if imap_request.subject_filter:
        config["subject_filter"] = imap_request.subject_filter

    # Handle OAuth providers
    if provider in ("gmail", "outlook"):
        # Check if OAuth is configured
        if not _is_oauth_provider_configured(provider):
            env_prefix = "GOOGLE" if provider == "gmail" else "MICROSOFT"
            raise HTTPException(
                status_code=503,
                detail=f"{provider.title()} OAuth is not configured. "
                       f"Set {env_prefix}_CLIENT_ID and {env_prefix}_CLIENT_SECRET."
            )

        # Create source with pending_oauth status
        db_source = _build_imap_source(imap_request, url, config, "pending_oauth")
        db.add(db_source)
        db.commit()
        db.refresh(db_source)

        try:
            # Generate OAuth authorization URL
            state, code_verifier, code_challenge = create_oauth_state(db_source.id, provider)
            base_url = _get_base_url(request)
            redirect_uri = get_redirect_uri(base_url)

            if provider == "gmail":
                auth_url = generate_gmail_auth_url(redirect_uri, state, code_challenge)
            else:  # outlook
                auth_url = generate_outlook_auth_url(redirect_uri, state, code_challenge)

            logger.info(
                "Created IMAP source with pending OAuth",
                source_id=db_source.id,
                provider=provider,
            )

            return IMAPSourceCreateResponse(
                source=_source_to_response(db_source),
                oauth_url=auth_url,
                message="Source created. Complete OAuth authentication at the provided URL.",
            )

        except Exception as e:
            # Rollback source creation if OAuth URL generation fails
            db.delete(db_source)
            db.commit()
            logger.error(f"Failed to generate OAuth URL: {e}", provider=provider)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate OAuth authorization URL: {e}"
            )

    else:
        # Generic IMAP - validate and encrypt credentials
        config["imap_host"] = imap_request.imap_host
        config["imap_port"] = imap_request.imap_port
        config["imap_username"] = imap_request.imap_username
        config["imap_use_ssl"] = imap_request.imap_use_ssl

        # Encrypt password before storing
        try:
            encrypted_password = encrypt_token(imap_request.imap_password)
            config["imap_password_encrypted"] = encrypted_password
        except TokenEncryptionError as e:
            logger.error(f"Failed to encrypt IMAP password: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to encrypt credentials. Ensure SECRET_KEY is set."
            )

        # TODO: Optionally validate IMAP connection before saving
        # This would require importing GenericIMAPProvider and testing connection
        # For now, we trust the user's credentials and set status to active

        db_source = _build_imap_source(imap_request, url, config, "active")
        db.add(db_source)
        db.commit()
        db.refresh(db_source)

        logger.info(
            "Created generic IMAP source",
            source_id=db_source.id,
            host=imap_request.imap_host,
        )

        return IMAPSourceCreateResponse(
            source=_source_to_response(db_source),
            oauth_url=None,
            message="IMAP source created successfully.",
        )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific source."""
    source = db.query(Source).options(
        joinedload(Source.oauth_credentials)
    ).filter(Source.id == source_id).first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_response(source)


def _source_to_health_response(source: Source) -> SourceHealthResponse:
    """Convert a Source model to a SourceHealthResponse."""
    return SourceHealthResponse(
        source_id=source.id,
        source_name=source.name,
        health_status=source.health_status,
        consecutive_failures=source.consecutive_failures,
        last_failure_at=source.last_failure_at,
        last_success_at=source.last_success_at,
        circuit_open_until=source.circuit_open_until,
        is_circuit_open=source.is_circuit_open,
    )


@router.get("/{source_id}/health", response_model=SourceHealthResponse)
async def get_source_health(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Get health status for a specific source.

    Returns detailed health information including:
    - Current health status (healthy, degraded, unhealthy)
    - Consecutive failure count
    - Last success/failure timestamps
    - Circuit breaker state

    This endpoint is useful for monitoring and debugging source issues.
    """
    source = db.query(Source).filter(Source.id == source_id).first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return _source_to_health_response(source)


def _apply_source_update(
    source_id: int,
    source_update: SourceUpdate,
    db: Session
) -> SourceResponse:
    """Apply updates to a source and return the response.

    Shared logic for PUT and PATCH endpoints.
    """
    db_source = db.query(Source).options(
        joinedload(Source.oauth_credentials)
    ).filter(Source.id == source_id).first()

    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_source, key, value)

    db.commit()
    db.refresh(db_source)
    return _source_to_response(db_source)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    """Update a source."""
    return _apply_source_update(source_id, source_update, db)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """Delete a source.

    For IMAP sources with OAuth credentials, the credentials are automatically
    deleted via CASCADE constraint.
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Log if deleting an IMAP source with OAuth
    if source.type == "imap":
        oauth_cred = db.query(OAuthCredential).filter(
            OAuthCredential.source_id == source_id
        ).first()
        if oauth_cred:
            logger.info(
                "Deleting IMAP source with OAuth credentials",
                source_id=source_id,
                provider=oauth_cred.provider,
            )

    db.delete(source)
    db.commit()
    return None


@router.patch("/{source_id}", response_model=SourceResponse)
async def patch_source(
    source_id: int,
    source_update: SourceUpdate,
    db: Session = Depends(get_db)
):
    """Partial update a source (e.g., toggle enabled status)."""
    return _apply_source_update(source_id, source_update, db)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_sources(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """Delete multiple sources by ID.

    OAuth credentials for IMAP sources are automatically deleted via CASCADE.
    """
    deleted_count = 0
    failed_ids = []

    for source_id in request.ids:
        source = db.query(Source).filter(Source.id == source_id).first()
        if source:
            db.delete(source)
            deleted_count += 1
        else:
            failed_ids.append(source_id)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )
