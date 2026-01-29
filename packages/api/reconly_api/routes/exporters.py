"""API routes for exporters."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from reconly_core.exporters import get_exporter, is_exporter_extension, list_exporters
from reconly_core.services.settings_registry import SETTINGS_REGISTRY
from reconly_core.services.settings_service import SettingsService

from reconly_api.dependencies import get_db
from reconly_api.routes.component_utils import (
    convert_config_fields,
    get_activation_state,
    get_enabled_key,
    get_missing_required_fields,
)
from reconly_api.schemas.exporters import (
    ExporterConfigSchemaResponse,
    ExporterListResponse,
    ExporterResponse,
    ExporterToggleRequest,
)
from reconly_api.schemas.components import ExporterMetadataResponse

router = APIRouter(prefix="/exporters", tags=["exporters"])

COMPONENT_TYPE = "export"


def _exporter_metadata_to_response(exporter) -> Optional[ExporterMetadataResponse]:
    """Convert exporter metadata to API response schema.

    Args:
        exporter: Exporter instance with get_metadata() method

    Returns:
        ExporterMetadataResponse or None if metadata not available
    """
    try:
        metadata = exporter.get_metadata()
        return ExporterMetadataResponse(
            name=metadata.name,
            display_name=metadata.display_name,
            description=metadata.description,
            icon=metadata.icon,
            file_extension=metadata.file_extension,
            mime_type=metadata.mime_type,
            path_setting_key=metadata.path_setting_key,
            ui_color=metadata.ui_color,
            requires_connection=metadata.requires_connection,
            connection_types=metadata.connection_types,
        )
    except (AttributeError, NotImplementedError):
        # Exporter doesn't have get_metadata() or it's not implemented
        return None


def _build_exporter_response(
    name: str,
    settings_service: SettingsService,
    enabled_override: Optional[bool] = None,
) -> ExporterResponse:
    """Build an ExporterResponse for a given exporter name.

    Args:
        name: Exporter name
        settings_service: Settings service instance
        enabled_override: If provided, use this value instead of querying settings

    Returns:
        ExporterResponse with all fields populated
    """
    exporter = get_exporter(name)
    schema = exporter.get_config_schema()

    enabled, is_configured, can_enable = get_activation_state(
        COMPONENT_TYPE, name, schema, settings_service
    )

    if enabled_override is not None:
        enabled = enabled_override

    config_fields = convert_config_fields(schema)

    return ExporterResponse(
        name=name,
        description=exporter.get_description(),
        content_type=exporter.get_content_type(),
        file_extension=exporter.get_file_extension(),
        supports_direct_export=schema.supports_direct_export,
        config_schema=ExporterConfigSchemaResponse(
            fields=config_fields,
            supports_direct_export=schema.supports_direct_export,
        ),
        enabled=enabled,
        is_configured=is_configured,
        can_enable=can_enable,
        is_extension=is_exporter_extension(name),
        metadata=_exporter_metadata_to_response(exporter),
    )


@router.get("", response_model=ExporterListResponse)
async def list_available_exporters(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
) -> ExporterListResponse:
    """List all available exporters with their metadata and configuration schemas.

    Args:
        enabled_only: If True, only return enabled exporters

    Returns:
        List of exporters with name, description, content type, file extension,
        configuration schema, and activation state.
    """
    settings_service = SettingsService(db)
    exporters = []

    for name in list_exporters():
        response = _build_exporter_response(name, settings_service)
        if enabled_only and not response.enabled:
            continue
        exporters.append(response)

    return ExporterListResponse(exporters=exporters)


@router.put("/{name}/enabled", response_model=ExporterResponse)
async def toggle_exporter_enabled(
    name: str,
    request: ExporterToggleRequest,
    db: Session = Depends(get_db),
) -> ExporterResponse:
    """Enable or disable an exporter.

    Args:
        name: Exporter name (e.g., 'json', 'obsidian')
        request: Toggle request with enabled state

    Returns:
        Updated exporter state

    Raises:
        404: If exporter not found
        400: If trying to enable an unconfigured exporter with required fields
    """
    try:
        exporter = get_exporter(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Exporter '{name}' not found")

    settings_service = SettingsService(db)
    schema = exporter.get_config_schema()

    _, is_configured, can_enable = get_activation_state(
        COMPONENT_TYPE, name, schema, settings_service
    )

    # Validate: can't enable unconfigured exporter with required fields
    if request.enabled and not can_enable:
        missing = get_missing_required_fields(
            COMPONENT_TYPE, name, schema, settings_service
        )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot enable exporter: required field(s) not configured: {', '.join(missing)}",
        )

    # Update enabled state
    enabled_key = get_enabled_key(COMPONENT_TYPE, name)
    if enabled_key not in SETTINGS_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Exporter '{name}' does not have a configurable enabled state",
        )

    settings_service.set(enabled_key, request.enabled)

    return _build_exporter_response(name, settings_service, enabled_override=request.enabled)
