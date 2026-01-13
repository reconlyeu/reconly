"""API routes for extensions.

Extensions API handles lifecycle operations only:
- GET /extensions/ - List installed extensions (metadata only)
- GET /extensions/catalog/ - Browse available extensions
- POST /extensions/install/ - Install extension package
- DELETE /extensions/{type}/{name}/ - Uninstall extension
- PUT /extensions/{type}/{name}/enabled - Toggle enabled state

Configuration is handled by component-specific APIs:
- /api/v1/exporters/{name}/ - Exporter configuration
- /api/v1/fetchers/{name}/ - Fetcher configuration
- /api/v1/providers/{name}/ - Provider configuration
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from reconly_core.extensions import (
    ExtensionType,
    get_extension_activation_state,
    set_extension_enabled,
    can_enable_extension,
    register_extension_settings,
    ensure_extensions_loaded,
    # Phase 2: Installer & Catalog
    get_extension_installer,
    get_catalog_fetcher,
    EXTENSION_PACKAGE_PREFIX,
)
from reconly_core.exporters.registry import (
    list_extension_exporters,
    get_exporter_entry,
    is_exporter_extension,
)
from reconly_core.exporters import get_exporter
from reconly_core.fetchers.registry import (
    list_extension_fetchers,
    get_fetcher_entry,
    is_fetcher_extension,
)
from reconly_api.schemas.extensions import (
    ExtensionListResponse,
    ExtensionResponse,
    ExtensionMetadataResponse,
    ExtensionToggleRequest,
    # Phase 2 schemas
    CatalogResponse,
    CatalogEntryResponse,
    ExtensionInstallRequest,
    ExtensionInstallResponse,
)
from reconly_api.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extensions", tags=["extensions"])


def _get_extension_type_enum(type_str: str) -> ExtensionType:
    """Convert string type to ExtensionType enum."""
    type_map = {
        "exporter": ExtensionType.EXPORTER,
        "fetcher": ExtensionType.FETCHER,
        "provider": ExtensionType.PROVIDER,
    }
    if type_str not in type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extension type '{type_str}'. Valid types: exporter, fetcher, provider"
        )
    return type_map[type_str]


def _get_config_api_path(ext_type: ExtensionType, name: str) -> str:
    """Get the component-specific API path for configuration.

    Args:
        ext_type: Extension type
        name: Extension registry name

    Returns:
        API path for configuration (e.g., '/api/v1/exporters/notion/')
    """
    type_to_path = {
        ExtensionType.EXPORTER: "exporters",
        ExtensionType.FETCHER: "fetchers",
        ExtensionType.PROVIDER: "providers",
    }
    return f"/api/v1/{type_to_path[ext_type]}/{name}/"


def _build_extension_response(
    name: str,
    ext_type: ExtensionType,
    db: Session,
) -> ExtensionResponse:
    """Build ExtensionResponse from registry entry.

    Note: config_schema is no longer included in extension responses.
    Configuration should be retrieved via component-specific APIs.
    """
    # Get entry from appropriate registry
    if ext_type == ExtensionType.EXPORTER:
        entry = get_exporter_entry(name)
        # Get required fields for activation state check
        exporter = get_exporter(name)
        schema = exporter.get_config_schema()
        required_fields = [f.key for f in schema.fields if f.required]
    elif ext_type == ExtensionType.FETCHER:
        entry = get_fetcher_entry(name)
        required_fields = []
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported extension type: {ext_type}")

    # Build metadata response
    if entry.metadata:
        metadata = ExtensionMetadataResponse(
            name=entry.metadata.name,
            version=entry.metadata.version,
            author=entry.metadata.author,
            min_reconly=entry.metadata.min_reconly,
            description=entry.metadata.description,
            homepage=entry.metadata.homepage,
            type=entry.metadata.extension_type.value,
            registry_name=entry.metadata.registry_name,
        )
    else:
        # Built-in without metadata
        metadata = ExtensionMetadataResponse(
            name=name.title(),
            version="0.0.0",
            author="Built-in",
            min_reconly="0.0.0",
            description=f"Built-in {ext_type.value}",
            homepage=None,
            type=ext_type.value,
            registry_name=name,
        )

    # Get activation state
    activation = get_extension_activation_state(ext_type, name, db, required_fields)

    return ExtensionResponse(
        name=name,
        type=ext_type.value,
        metadata=metadata,
        is_extension=entry.is_extension,
        enabled=activation["enabled"],
        is_configured=activation["is_configured"],
        can_enable=activation["can_enable"],
        load_error=None,
        config_api=_get_config_api_path(ext_type, name),
    )


@router.get("", response_model=ExtensionListResponse)
async def list_extensions(
    type: Optional[str] = Query(None, description="Filter by type (exporter, fetcher, provider)"),
    extensions_only: bool = Query(True, description="Only show external extensions (not built-ins)"),
    db: Session = Depends(get_db),
):
    """
    List all installed extensions.

    Args:
        type: Optional filter by extension type
        extensions_only: If True (default), only show external extensions

    Returns:
        List of extensions with metadata and activation state
    """
    ensure_extensions_loaded()  # Ensure extensions are discovered
    extensions = []

    # Get exporter extensions
    if type is None or type == "exporter":
        exporter_names = list_extension_exporters()
        for name in exporter_names:
            try:
                ext = _build_extension_response(name, ExtensionType.EXPORTER, db)
                extensions.append(ext)
            except Exception:
                continue

    # Get fetcher extensions
    if type is None or type == "fetcher":
        fetcher_names = list_extension_fetchers()
        for name in fetcher_names:
            try:
                ext = _build_extension_response(name, ExtensionType.FETCHER, db)
                extensions.append(ext)
            except Exception:
                continue

    # TODO: Add provider extensions when implemented

    return ExtensionListResponse(total=len(extensions), items=extensions)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: CATALOG & INSTALLATION ENDPOINTS
# These must be defined BEFORE the /{type}/ parameterized routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/catalog/", response_model=CatalogResponse)
async def get_catalog(
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh catalog"),
):
    """
    Fetch the extension catalog.

    Returns a list of available extensions from the curated catalog,
    with installed status indicated for each.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Extension catalog with available extensions
    """
    try:
        fetcher = get_catalog_fetcher()
        catalog = fetcher.fetch_sync(force_refresh=force_refresh)

        return CatalogResponse(
            version=catalog.version,
            extensions=[
                CatalogEntryResponse(
                    package=e.package,
                    name=e.name,
                    type=e.type,
                    description=e.description,
                    author=e.author,
                    version=e.version,
                    verified=e.verified,
                    homepage=e.homepage,
                    pypi_url=e.pypi_url,
                    installed=e.installed,
                    installed_version=e.installed_version,
                )
                for e in catalog.extensions
            ],
            last_updated=catalog.last_updated,
        )
    except Exception as e:
        logger.error(f"Failed to fetch catalog: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch extension catalog: {str(e)}"
        )


@router.get("/catalog/search/", response_model=CatalogResponse)
async def search_catalog_endpoint(
    q: Optional[str] = Query(None, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type (exporter, fetcher, provider)"),
    verified_only: bool = Query(False, description="Only show verified extensions"),
):
    """
    Search the extension catalog.

    Args:
        q: Search query to match against name and description
        type: Filter by extension type
        verified_only: If True, only return verified extensions

    Returns:
        Filtered catalog entries
    """
    try:
        fetcher = get_catalog_fetcher()
        catalog = fetcher.fetch_sync()
        results = fetcher.search(
            catalog,
            query=q,
            type_filter=type,
            verified_only=verified_only,
        )

        return CatalogResponse(
            version=catalog.version,
            extensions=[
                CatalogEntryResponse(
                    package=e.package,
                    name=e.name,
                    type=e.type,
                    description=e.description,
                    author=e.author,
                    version=e.version,
                    verified=e.verified,
                    homepage=e.homepage,
                    pypi_url=e.pypi_url,
                    installed=e.installed,
                    installed_version=e.installed_version,
                )
                for e in results
            ],
            last_updated=catalog.last_updated,
        )
    except Exception as e:
        logger.error(f"Failed to search catalog: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to search extension catalog: {str(e)}"
        )


@router.post("/install/", response_model=ExtensionInstallResponse)
async def install_extension(
    request: ExtensionInstallRequest,
):
    """
    Install an extension package using pip.

    This endpoint wraps `pip install` to install extension packages.
    Only packages starting with 'reconly-ext-' are allowed.

    After installation, a restart is required for the extension to be loaded.

    Args:
        request: Install request with package name

    Returns:
        Install result with success status and version
    """
    package = request.package

    # Validate package name prefix
    if not package.startswith(EXTENSION_PACKAGE_PREFIX):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid package name. Must start with '{EXTENSION_PACKAGE_PREFIX}'"
        )

    logger.info(f"Installing extension package: {package}")

    installer = get_extension_installer()
    result = installer.install(package, upgrade=request.upgrade)

    if not result.success:
        logger.error(f"Failed to install {package}: {result.error}")
        # Provide helpful error message for dev mode
        error_msg = result.error or "Installation failed"
        if "not found" in error_msg.lower():
            error_msg = (
                f"Package '{package}' not found on PyPI. "
                f"In development mode, install extensions manually with:\n\n"
                f"  pip install -e /path/to/{package}\n\n"
                f"Or from a git repository:\n\n"
                f"  pip install git+https://github.com/reconly/{package}.git"
            )
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )

    logger.info(f"Successfully installed {package} v{result.version}")

    return ExtensionInstallResponse(
        success=True,
        package=result.package,
        version=result.version,
        requires_restart=result.requires_restart,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETERIZED ROUTES - Must come AFTER specific routes like /catalog/
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{type}/", response_model=ExtensionListResponse)
async def list_extensions_by_type(
    type: str,
    db: Session = Depends(get_db),
):
    """
    List extensions of a specific type.

    Args:
        type: Extension type (exporter, fetcher, provider)

    Returns:
        List of extensions of the specified type
    """
    ensure_extensions_loaded()  # Ensure extensions are discovered
    ext_type = _get_extension_type_enum(type)
    extensions = []

    if ext_type == ExtensionType.EXPORTER:
        exporter_names = list_extension_exporters()
        for name in exporter_names:
            try:
                ext = _build_extension_response(name, ext_type, db)
                extensions.append(ext)
            except Exception:
                continue
    elif ext_type == ExtensionType.FETCHER:
        fetcher_names = list_extension_fetchers()
        for name in fetcher_names:
            try:
                ext = _build_extension_response(name, ext_type, db)
                extensions.append(ext)
            except Exception:
                continue

    return ExtensionListResponse(total=len(extensions), items=extensions)


@router.get("/{type}/{name}/", response_model=ExtensionResponse)
async def get_extension(
    type: str,
    name: str,
    db: Session = Depends(get_db),
):
    """
    Get details for a specific extension.

    Args:
        type: Extension type (exporter, fetcher, provider)
        name: Extension registry name (e.g., 'notion')

    Returns:
        Extension details with metadata and activation state
    """
    ensure_extensions_loaded()  # Ensure extensions are discovered
    ext_type = _get_extension_type_enum(type)

    # Verify extension exists and is actually an extension
    if ext_type == ExtensionType.EXPORTER:
        if not is_exporter_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found or is a built-in exporter"
            )
    elif ext_type == ExtensionType.FETCHER:
        if not is_fetcher_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found or is a built-in fetcher"
            )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported extension type: {type}")

    try:
        return _build_extension_response(name, ext_type, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{type}/{name}/enabled", response_model=ExtensionResponse)
async def toggle_extension_enabled(
    type: str,
    name: str,
    request: ExtensionToggleRequest,
    db: Session = Depends(get_db),
):
    """
    Enable or disable an extension.

    Args:
        type: Extension type
        name: Extension registry name
        request: Toggle request with enabled state

    Returns:
        Updated extension state

    Raises:
        400: If trying to enable an unconfigured extension with required fields
        404: If extension not found
    """
    ensure_extensions_loaded()  # Ensure extensions are discovered
    ext_type = _get_extension_type_enum(type)

    # Verify extension exists
    if ext_type == ExtensionType.EXPORTER:
        if not is_exporter_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found"
            )
        exporter = get_exporter(name)
        schema = exporter.get_config_schema()
        required_fields = [f.key for f in schema.fields if f.required]
    elif ext_type == ExtensionType.FETCHER:
        if not is_fetcher_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found"
            )
        required_fields = []
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported extension type: {type}")

    # Validate can enable
    if request.enabled and not can_enable_extension(ext_type, name, db, required_fields):
        raise HTTPException(
            status_code=400,
            detail="Cannot enable extension: required configuration fields not set"
        )

    # Update enabled state
    try:
        set_extension_enabled(ext_type, name, request.enabled, db)
    except KeyError:
        # Setting not registered - register it first
        register_extension_settings(ext_type, name)
        set_extension_enabled(ext_type, name, request.enabled, db)

    return _build_extension_response(name, ext_type, db)


@router.put("/{type}/{name}/settings")
async def update_extension_settings_deprecated(
    type: str,
    name: str,
):
    """
    DEPRECATED: Extension settings endpoint.

    Configuration should now be done via component-specific APIs:
    - Exporters: PUT /api/v1/exporters/{name}/settings
    - Fetchers: PUT /api/v1/fetchers/{name}/settings
    - Providers: PUT /api/v1/providers/{name}/settings

    This endpoint is kept for backwards compatibility but returns an error
    directing clients to use the appropriate component API.
    """
    ext_type = _get_extension_type_enum(type)
    config_api = _get_config_api_path(ext_type, name)

    raise HTTPException(
        status_code=410,  # Gone
        detail=(
            f"This endpoint is deprecated. "
            f"Use the component-specific API for configuration: {config_api}"
        ),
    )


@router.delete("/{type}/{name}/", response_model=ExtensionInstallResponse)
async def uninstall_extension(
    type: str,
    name: str,
    db: Session = Depends(get_db),
):
    """
    Uninstall an extension package.

    This endpoint wraps `pip uninstall` to remove extension packages.
    After uninstallation, a restart is required for changes to take effect.

    Args:
        type: Extension type (exporter, fetcher, provider)
        name: Extension registry name (e.g., 'notion')

    Returns:
        Uninstall result with success status
    """
    ext_type = _get_extension_type_enum(type)

    # Verify extension exists and is actually an extension
    if ext_type == ExtensionType.EXPORTER:
        if not is_exporter_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found or is a built-in exporter"
            )
    elif ext_type == ExtensionType.FETCHER:
        if not is_fetcher_extension(name):
            raise HTTPException(
                status_code=404,
                detail=f"Extension '{name}' not found or is a built-in fetcher"
            )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported extension type: {type}")

    # Construct package name from registry name
    package = f"{EXTENSION_PACKAGE_PREFIX}{name}"

    logger.info(f"Uninstalling extension package: {package}")

    installer = get_extension_installer()
    result = installer.uninstall(package)

    if not result.success:
        logger.error(f"Failed to uninstall {package}: {result.error}")
        raise HTTPException(
            status_code=400,
            detail=result.error or "Uninstallation failed"
        )

    logger.info(f"Successfully uninstalled {package}")

    return ExtensionInstallResponse(
        success=True,
        package=result.package,
        requires_restart=result.requires_restart,
    )
