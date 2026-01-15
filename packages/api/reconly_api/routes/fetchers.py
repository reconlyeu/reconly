"""API routes for fetchers."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from reconly_core.fetchers import get_fetcher, is_fetcher_extension, list_fetchers
from reconly_core.services.settings_registry import SETTINGS_REGISTRY
from reconly_core.services.settings_service import SettingsService

from reconly_api.dependencies import get_db
from reconly_api.routes.component_utils import (
    convert_config_fields,
    get_activation_state,
    get_enabled_key,
    get_missing_required_fields,
)
from reconly_api.schemas.fetchers import (
    FetcherConfigSchemaResponse,
    FetcherListResponse,
    FetcherResponse,
    FetcherToggleRequest,
)

router = APIRouter(prefix="/fetchers", tags=["fetchers"])

COMPONENT_TYPE = "fetch"


def _get_oauth_providers_for_fetcher(name: str) -> list[str] | None:
    """Get the list of OAuth providers supported by a fetcher.

    Returns:
        List of provider names or None if fetcher doesn't support OAuth
    """
    # IMAP fetcher supports Gmail and Outlook OAuth
    if name == "imap":
        return ["gmail", "outlook"]
    return None


def _build_fetcher_response(
    name: str,
    settings_service: SettingsService,
    enabled_override: bool = None,
) -> FetcherResponse:
    """Build a FetcherResponse for a given fetcher name.

    Args:
        name: Fetcher name
        settings_service: Settings service instance
        enabled_override: If provided, use this value instead of querying settings

    Returns:
        FetcherResponse with all fields populated
    """
    fetcher = get_fetcher(name)
    schema = fetcher.get_config_schema()

    enabled, is_configured, can_enable = get_activation_state(
        COMPONENT_TYPE, name, schema, settings_service
    )

    if enabled_override is not None:
        enabled = enabled_override

    return FetcherResponse(
        name=name,
        description=fetcher.get_description(),
        config_schema=FetcherConfigSchemaResponse(
            fields=convert_config_fields(schema),
        ),
        enabled=enabled,
        is_configured=is_configured,
        can_enable=can_enable,
        is_extension=is_fetcher_extension(name),
        oauth_providers=_get_oauth_providers_for_fetcher(name),
    )


@router.get("", response_model=FetcherListResponse)
async def list_available_fetchers(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
) -> FetcherListResponse:
    """List all available fetchers with their metadata and configuration schemas.

    Args:
        enabled_only: If True, only return enabled fetchers

    Returns:
        List of fetchers with name, description, configuration schema,
        and activation state.
    """
    settings_service = SettingsService(db)
    fetchers = []

    for name in list_fetchers():
        response = _build_fetcher_response(name, settings_service)
        if enabled_only and not response.enabled:
            continue
        fetchers.append(response)

    return FetcherListResponse(fetchers=fetchers)


@router.get("/{name}", response_model=FetcherResponse)
async def get_fetcher_details(
    name: str,
    db: Session = Depends(get_db),
) -> FetcherResponse:
    """Get details for a specific fetcher.

    Args:
        name: Fetcher name (e.g., 'rss', 'youtube')

    Returns:
        Fetcher details including config schema and activation state

    Raises:
        404: If fetcher not found
    """
    try:
        get_fetcher(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fetcher '{name}' not found")

    settings_service = SettingsService(db)
    return _build_fetcher_response(name, settings_service)


@router.put("/{name}/enabled", response_model=FetcherResponse)
async def toggle_fetcher_enabled(
    name: str,
    request: FetcherToggleRequest,
    db: Session = Depends(get_db),
) -> FetcherResponse:
    """Enable or disable a fetcher.

    Args:
        name: Fetcher name (e.g., 'rss', 'youtube')
        request: Toggle request with enabled state

    Returns:
        Updated fetcher state

    Raises:
        404: If fetcher not found
        400: If trying to enable an unconfigured fetcher with required fields
    """
    try:
        fetcher = get_fetcher(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fetcher '{name}' not found")

    settings_service = SettingsService(db)
    schema = fetcher.get_config_schema()

    _, is_configured, can_enable = get_activation_state(
        COMPONENT_TYPE, name, schema, settings_service
    )

    # Validate: can't enable unconfigured fetcher with required fields
    if request.enabled and not can_enable:
        missing = get_missing_required_fields(
            COMPONENT_TYPE, name, schema, settings_service
        )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot enable fetcher: required field(s) not configured: {', '.join(missing)}",
        )

    # Update enabled state
    enabled_key = get_enabled_key(COMPONENT_TYPE, name)
    if enabled_key not in SETTINGS_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Fetcher '{name}' does not have a configurable enabled state",
        )

    settings_service.set(enabled_key, request.enabled)

    return _build_fetcher_response(name, settings_service, enabled_override=request.enabled)
