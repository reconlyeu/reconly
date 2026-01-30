"""OAuth2 API routes for email provider authentication.

This module handles OAuth2 flows for Gmail and Outlook email sources,
including authorization URL generation, callback handling, and token revocation.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from reconly_api.dependencies import get_db
from reconly_api.schemas.oauth import (
    OAuthAuthorizeResponse,
    OAuthCredentialResponse,
    OAuthProviderInfo,
    OAuthProvidersResponse,
    OAuthRevokeResponse,
    OAuthStatusResponse,
)
from reconly_core.database.models import OAuthCredential, Source
from reconly_core.email.crypto import (
    TokenEncryptionError,
    decrypt_token,
    encrypt_token,
    encrypt_token_optional,
)
from reconly_core.email.gmail import GmailOAuthError
from reconly_core.email.oauth import (
    OAuthStateError,
    create_oauth_state,
    get_redirect_uri,
    validate_oauth_state,
)
from reconly_core.email.oauth_registry import (
    get_oauth_provider,
    is_provider_configured,
    list_oauth_providers as list_registered_providers,
)
from reconly_core.email.outlook import OutlookOAuthError
from reconly_core.logging import get_logger

# Import to trigger provider registration
import reconly_core.email.gmail  # noqa: F401
import reconly_core.email.outlook  # noqa: F401

logger = get_logger(__name__)

router = APIRouter()


def _get_base_url(request: Request) -> str:
    """Get the base URL from the request.

    Uses X-Forwarded headers if available (for reverse proxy scenarios).
    """
    # Check for forwarded proto/host
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))

    return f"{proto}://{host}"


def _is_provider_configured(provider: str) -> bool:
    """Check if OAuth provider credentials are configured."""
    return is_provider_configured(provider)


@router.get("/oauth/providers", response_model=OAuthProvidersResponse)
async def list_oauth_providers():
    """
    List available OAuth providers and their configuration status.

    Returns information about supported OAuth providers including:
    - Whether credentials are configured
    - Scopes that will be requested
    """
    providers = [
        OAuthProviderInfo(
            provider=meta.name,
            display_name=meta.display_name,
            scopes=meta.scopes,
            configured=meta.is_configured(),
        )
        for meta in list_registered_providers()
    ]

    return OAuthProvidersResponse(providers=providers)


@router.get("/oauth/{provider}/authorize", response_model=OAuthAuthorizeResponse)
async def get_authorization_url(
    provider: str,
    source_id: int = Query(..., description="Source ID to associate with OAuth"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Generate OAuth authorization URL for a provider.

    This initiates the OAuth2 flow by generating a URL to redirect the user
    to the provider's consent screen. The source_id is encoded in the state
    parameter for callback association.

    Args:
        provider: OAuth provider (gmail or outlook)
        source_id: Source ID to connect OAuth to

    Returns:
        Authorization URL to redirect user to
    """
    # Get provider from registry
    provider_meta = get_oauth_provider(provider)
    if not provider_meta:
        raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")

    # Verify source exists and is an email type
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if source.type != "imap":
        raise HTTPException(
            status_code=400,
            detail=f"Source type must be 'imap', got '{source.type}'"
        )

    # Check provider config from source
    source_config = source.config or {}
    expected_provider = source_config.get("provider", provider)
    if expected_provider != provider:
        raise HTTPException(
            status_code=400,
            detail=f"Source is configured for provider '{expected_provider}', not '{provider}'"
        )

    # Check if provider is configured
    if not provider_meta.is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"{provider_meta.display_name} OAuth is not configured. "
                   f"Set {provider_meta.client_id_env_var} and {provider_meta.client_secret_env_var}."
        )

    try:
        # Create OAuth state with PKCE
        state, code_verifier, code_challenge = create_oauth_state(source_id, provider)

        # Build redirect URI
        base_url = _get_base_url(request)
        redirect_uri = get_redirect_uri(base_url)

        # Generate authorization URL using registry
        auth_url = provider_meta.auth_url_generator(redirect_uri, state, code_challenge)

        logger.info(
            "Generated OAuth authorization URL",
            provider=provider,
            source_id=source_id,
        )

        return OAuthAuthorizeResponse(
            authorization_url=auth_url,
            provider=provider,
        )

    except Exception as e:
        logger.error(f"Failed to generate OAuth URL: {e}", provider=provider, source_id=source_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate authorization URL: {e}"
        )


@router.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None, description="Authorization code from provider"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error code if authorization failed"),
    error_description: Optional[str] = Query(None, description="Error description"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Handle OAuth callback from provider.

    This endpoint receives the authorization code or error from the OAuth provider
    after the user consents (or denies). It exchanges the code for tokens and
    stores them encrypted in the database.

    For browser flows, this redirects to the UI with status.
    For API flows, returns JSON response.
    """
    # Handle error response from provider
    if error:
        logger.warning(
            "OAuth callback received error",
            error=error,
            error_description=error_description,
        )
        # Redirect to UI with error
        return RedirectResponse(
            url=f"/sources?oauth_error={error}&oauth_error_description={error_description or ''}",
            status_code=302,
        )

    # Validate required parameters
    if not code or not state:
        logger.warning("OAuth callback missing required parameters")
        return RedirectResponse(
            url="/sources?oauth_error=invalid_request&oauth_error_description=Missing+code+or+state",
            status_code=302,
        )

    try:
        # Validate and decrypt state
        oauth_state = validate_oauth_state(state)
        provider = oauth_state.provider
        source_id = oauth_state.source_id
        code_verifier = oauth_state.code_verifier

        logger.info(
            "Processing OAuth callback",
            provider=provider,
            source_id=source_id,
        )

        # Get provider from registry
        provider_meta = get_oauth_provider(provider)
        if not provider_meta:
            # This shouldn't happen if state was valid, but handle gracefully
            return RedirectResponse(
                url="/sources?oauth_error=invalid_provider&oauth_error_description=Unknown+provider",
                status_code=302,
            )

        # Verify source still exists
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            logger.warning("OAuth callback for non-existent source", source_id=source_id)
            return RedirectResponse(
                url="/sources?oauth_error=invalid_request&oauth_error_description=Source+not+found",
                status_code=302,
            )

        # Build redirect URI (must match authorize request)
        base_url = _get_base_url(request)
        redirect_uri = get_redirect_uri(base_url)

        # Exchange code for tokens using registry
        tokens = provider_meta.token_exchanger(code, redirect_uri, code_verifier)

        # Encrypt tokens for storage
        access_token_encrypted = encrypt_token(tokens.access_token)
        refresh_token_encrypted = encrypt_token_optional(tokens.refresh_token)

        # Store or update credentials
        existing_cred = db.query(OAuthCredential).filter(
            OAuthCredential.source_id == source_id
        ).first()

        if existing_cred:
            # Update existing credential
            existing_cred.provider = provider
            existing_cred.access_token_encrypted = access_token_encrypted
            existing_cred.refresh_token_encrypted = refresh_token_encrypted
            existing_cred.expires_at = tokens.expires_at
            existing_cred.scopes = tokens.scopes
            existing_cred.updated_at = datetime.utcnow()
        else:
            # Create new credential
            new_cred = OAuthCredential(
                source_id=source_id,
                provider=provider,
                access_token_encrypted=access_token_encrypted,
                refresh_token_encrypted=refresh_token_encrypted,
                expires_at=tokens.expires_at,
                scopes=tokens.scopes,
            )
            db.add(new_cred)

        # Update source auth_status to active
        source.auth_status = "active"

        db.commit()

        logger.info(
            "OAuth credentials stored successfully",
            provider=provider,
            source_id=source_id,
            has_refresh_token=tokens.refresh_token is not None,
        )

        # Redirect to UI with success
        return RedirectResponse(
            url=f"/sources/{source_id}?oauth_success=true&oauth_provider={provider}",
            status_code=302,
        )

    except OAuthStateError as e:
        logger.warning(f"OAuth state validation failed: {e}")
        return RedirectResponse(
            url="/sources?oauth_error=invalid_state&oauth_error_description=Invalid+or+expired+state",
            status_code=302,
        )
    except (GmailOAuthError, OutlookOAuthError) as e:
        logger.error(f"OAuth token exchange failed: {e}")
        return RedirectResponse(
            url=f"/sources?oauth_error=token_exchange_failed&oauth_error_description={str(e)[:100]}",
            status_code=302,
        )
    except TokenEncryptionError as e:
        logger.error(f"Failed to encrypt OAuth tokens: {e}")
        return RedirectResponse(
            url="/sources?oauth_error=encryption_failed&oauth_error_description=Token+encryption+failed",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        return RedirectResponse(
            url="/sources?oauth_error=internal_error&oauth_error_description=Unexpected+error",
            status_code=302,
        )


@router.get("/oauth/{source_id}/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    source_id: int,
    db: Session = Depends(get_db),
):
    """
    Get OAuth connection status for a source.

    Returns whether OAuth is connected, when tokens expire, and if refresh is needed.
    """
    # Verify source exists
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Get OAuth credential
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.source_id == source_id
    ).first()

    if not cred:
        return OAuthStatusResponse(
            connected=False,
            provider=None,
            expires_at=None,
            needs_refresh=False,
            has_refresh_token=False,
        )

    # Check if token needs refresh (expires within 5 minutes)
    needs_refresh = False
    if cred.expires_at:
        needs_refresh = cred.expires_at <= datetime.utcnow() + timedelta(minutes=5)

    return OAuthStatusResponse(
        connected=True,
        provider=cred.provider,
        expires_at=cred.expires_at,
        needs_refresh=needs_refresh,
        has_refresh_token=cred.refresh_token_encrypted is not None,
    )


@router.delete("/oauth/{source_id}", response_model=OAuthRevokeResponse)
async def revoke_oauth(
    source_id: int,
    db: Session = Depends(get_db),
):
    """
    Revoke OAuth tokens and delete credentials for a source.

    This attempts to revoke the tokens with the provider and then deletes
    the stored credentials from the database.
    """
    # Verify source exists
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Get OAuth credential
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.source_id == source_id
    ).first()

    if not cred:
        raise HTTPException(status_code=404, detail="No OAuth credentials found for this source")

    provider = cred.provider
    revocation_success = True

    try:
        # Try to decrypt and revoke the token
        access_token = decrypt_token(cred.access_token_encrypted)

        # Get provider from registry
        provider_meta = get_oauth_provider(provider)
        if provider_meta and provider_meta.token_revoker:
            revocation_success = provider_meta.token_revoker(access_token)
        else:
            revocation_success = False

    except TokenEncryptionError as e:
        logger.warning(f"Could not decrypt token for revocation: {e}")
        revocation_success = False
    except Exception as e:
        logger.warning(f"Token revocation failed: {e}")
        revocation_success = False

    # Always delete credentials from database
    db.delete(cred)
    db.commit()

    logger.info(
        "OAuth credentials revoked",
        provider=provider,
        source_id=source_id,
        revocation_success=revocation_success,
    )

    message = "OAuth credentials revoked successfully"
    if not revocation_success:
        message += " (token revocation with provider may have failed, but credentials are deleted)"

    return OAuthRevokeResponse(
        success=True,
        source_id=source_id,
        provider=provider,
        message=message,
    )


@router.get("/oauth/{source_id}/credential", response_model=OAuthCredentialResponse)
async def get_oauth_credential(
    source_id: int,
    db: Session = Depends(get_db),
):
    """
    Get OAuth credential information for a source.

    Returns credential metadata without sensitive token data.
    """
    # Verify source exists
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Get OAuth credential
    cred = db.query(OAuthCredential).filter(
        OAuthCredential.source_id == source_id
    ).first()

    if not cred:
        raise HTTPException(status_code=404, detail="No OAuth credentials found for this source")

    return OAuthCredentialResponse(
        id=cred.id,
        source_id=cred.source_id,
        provider=cred.provider,
        expires_at=cred.expires_at,
        scopes=cred.scopes,
        has_refresh_token=cred.refresh_token_encrypted is not None,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )
