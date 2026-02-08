"""API routes for fetchers."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from reconly_core.fetchers import get_fetcher, is_fetcher_extension, list_fetchers
from reconly_core.services.settings_service import SettingsService

from reconly_api.dependencies import get_db
from reconly_api.routes.component_utils import (
    convert_config_fields,
    is_component_configured,
)
from reconly_api.schemas.fetchers import (
    FetcherConfigSchemaResponse,
    FetcherListResponse,
    FetcherResponse,
)
from reconly_api.schemas.components import FetcherMetadataResponse

router = APIRouter(prefix="/fetchers", tags=["fetchers"])

COMPONENT_TYPE = "fetch"


def _fetcher_metadata_to_response(fetcher) -> Optional[FetcherMetadataResponse]:
    """Convert fetcher metadata to API response schema.

    Args:
        fetcher: Fetcher instance with get_metadata() method

    Returns:
        FetcherMetadataResponse or None if metadata not available
    """
    try:
        metadata = fetcher.get_metadata()
        return FetcherMetadataResponse(
            name=metadata.name,
            display_name=metadata.display_name,
            description=metadata.description,
            icon=metadata.icon,
            url_schemes=metadata.url_schemes,
            supports_oauth=metadata.supports_oauth,
            oauth_providers=metadata.oauth_providers,
            supports_incremental=metadata.supports_incremental,
            supports_validation=metadata.supports_validation,
            supports_test_fetch=metadata.supports_test_fetch,
            show_in_settings=metadata.show_in_settings,
            requires_connection=metadata.requires_connection,
            connection_types=metadata.connection_types,
        )
    except (AttributeError, NotImplementedError):
        # Fetcher doesn't have get_metadata() or it's not implemented
        return None


def _build_fetcher_response(
    name: str,
    settings_service: SettingsService,
) -> FetcherResponse:
    """Build a FetcherResponse for a given fetcher name.

    Args:
        name: Fetcher name
        settings_service: Settings service instance

    Returns:
        FetcherResponse with all fields populated
    """
    fetcher = get_fetcher(name)
    schema = fetcher.get_config_schema()

    # Get metadata first - needed for both is_configured check and response
    metadata_response = _fetcher_metadata_to_response(fetcher)

    # Connection-based fetchers are always "configured" - their credentials
    # come from Connection entities, not global settings
    if metadata_response and metadata_response.requires_connection:
        is_configured = True
    else:
        is_configured = is_component_configured(
            COMPONENT_TYPE, name, schema, settings_service
        )
    oauth_providers = None
    if metadata_response and metadata_response.oauth_providers:
        oauth_providers = metadata_response.oauth_providers

    return FetcherResponse(
        name=name,
        description=fetcher.get_description(),
        config_schema=FetcherConfigSchemaResponse(
            fields=convert_config_fields(schema),
        ),
        is_configured=is_configured,
        is_extension=is_fetcher_extension(name),
        oauth_providers=oauth_providers,
        metadata=metadata_response,
    )


@router.get("", response_model=FetcherListResponse)
async def list_available_fetchers(
    db: Session = Depends(get_db),
) -> FetcherListResponse:
    """List all available fetchers with their metadata and configuration schemas.

    Returns:
        List of fetchers with name, description, and configuration schema.
    """
    settings_service = SettingsService(db)
    fetchers = []

    for name in list_fetchers():
        response = _build_fetcher_response(name, settings_service)
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
        Fetcher details including config schema

    Raises:
        404: If fetcher not found
    """
    try:
        get_fetcher(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Fetcher '{name}' not found")

    settings_service = SettingsService(db)
    return _build_fetcher_response(name, settings_service)
