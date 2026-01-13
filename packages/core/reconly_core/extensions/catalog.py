"""Extension catalog for browsing available extensions.

This module provides functionality to fetch and search a curated catalog
of available Reconly extensions. The catalog is hosted as a JSON file
in the Reconly repository.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from reconly_core.extensions.types import ExtensionType
from reconly_core.extensions.loader import get_extension_loader

logger = logging.getLogger(__name__)

# Default catalog URL (GitHub raw content)
DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/reconly/reconly/main/extensions-catalog.json"
)

# Local fallback catalog path (relative to project root)
LOCAL_CATALOG_PATH = "extensions-catalog.json"

# Cache timeout in seconds
CATALOG_CACHE_TIMEOUT = 300  # 5 minutes


@dataclass
class CatalogEntry:
    """Entry in the extension catalog.

    Attributes:
        package: PyPI package name (e.g., 'reconly-ext-notion')
        name: Human-readable name (e.g., 'Notion Exporter')
        type: Extension type (exporter, fetcher, provider)
        description: Brief description of what the extension does
        author: Author name or organization
        version: Latest available version on PyPI
        verified: Whether this extension is verified/curated by maintainers
        homepage: URL to extension homepage or repository
        pypi_url: URL to PyPI page
        installed: Whether this extension is currently installed (computed)
        installed_version: Currently installed version if installed
    """
    package: str
    name: str
    type: str
    description: str
    author: str
    version: str = "0.0.0"
    verified: bool = False
    homepage: Optional[str] = None
    pypi_url: Optional[str] = None
    installed: bool = False
    installed_version: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "package": self.package,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "verified": self.verified,
            "homepage": self.homepage,
            "pypi_url": self.pypi_url,
            "installed": self.installed,
            "installed_version": self.installed_version,
        }


@dataclass
class Catalog:
    """The extension catalog.

    Attributes:
        version: Catalog schema version
        extensions: List of available extensions
        last_updated: When the catalog was last updated (ISO timestamp)
    """
    version: str
    extensions: List[CatalogEntry] = field(default_factory=list)
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "extensions": [e.to_dict() for e in self.extensions],
            "last_updated": self.last_updated,
        }


class CatalogFetcher:
    """Fetches and manages the extension catalog.

    Usage:
        fetcher = CatalogFetcher()
        catalog = await fetcher.fetch()
        for ext in catalog.extensions:
            print(f"{ext.name}: {ext.description}")
    """

    def __init__(
        self,
        catalog_url: Optional[str] = None,
        local_path: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize the catalog fetcher.

        Args:
            catalog_url: URL to fetch catalog from (defaults to GitHub)
            local_path: Path to local catalog file for fallback/development
            timeout: HTTP request timeout in seconds
        """
        self.catalog_url = catalog_url or DEFAULT_CATALOG_URL
        self.local_path = local_path
        self.timeout = timeout
        self._cache: Optional[Catalog] = None
        self._cache_time: float = 0

    def _find_local_catalog(self) -> Optional[Path]:
        """Find the local catalog file.

        Searches in order:
        1. Explicitly configured local_path
        2. Environment variable RECONLY_CATALOG_PATH
        3. extensions-catalog.json in current directory and parent directories

        Returns:
            Path to catalog file if found, None otherwise
        """
        # Check explicit path
        if self.local_path:
            path = Path(self.local_path)
            if path.exists():
                return path

        # Check environment variable
        env_path = os.environ.get("RECONLY_CATALOG_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path

        # Search current directory and parents
        search_dir = Path.cwd()
        for _ in range(5):  # Search up to 5 levels
            catalog_path = search_dir / LOCAL_CATALOG_PATH
            if catalog_path.exists():
                return catalog_path
            parent = search_dir.parent
            if parent == search_dir:
                break
            search_dir = parent

        return None

    def _load_local_catalog(self) -> Optional[Catalog]:
        """Load catalog from local file.

        Returns:
            Catalog if file found and parsed, None otherwise
        """
        path = self._find_local_catalog()
        if not path:
            return None

        try:
            logger.info(f"Loading local catalog from {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._parse_catalog(data)
        except Exception as e:
            logger.warning(f"Failed to load local catalog: {e}")
            return None

    def _get_installed_extensions(self) -> Dict[str, str]:
        """Get a mapping of installed extension package names to versions.

        Returns:
            Dict mapping package name to installed version
        """
        installed = {}
        loader = get_extension_loader()

        for ext_type in ExtensionType:
            for name in loader.discover_extensions(ext_type):
                # Construct package name from entry point name
                package_name = f"reconly-ext-{name}"
                # Try to get version from importlib.metadata
                try:
                    from importlib.metadata import version
                    installed[package_name] = version(package_name)
                except Exception:
                    installed[package_name] = "unknown"

        return installed

    def _parse_catalog(self, data: Dict) -> Catalog:
        """Parse catalog JSON data into a Catalog object.

        Args:
            data: Raw JSON catalog data

        Returns:
            Parsed Catalog object
        """
        extensions = []
        installed = self._get_installed_extensions()

        for ext_data in data.get("extensions", []):
            package = ext_data.get("package", "")
            entry = CatalogEntry(
                package=package,
                name=ext_data.get("name", package),
                type=ext_data.get("type", "exporter"),
                description=ext_data.get("description", ""),
                author=ext_data.get("author", "Unknown"),
                version=ext_data.get("version", "0.0.0"),
                verified=ext_data.get("verified", False),
                homepage=ext_data.get("homepage"),
                pypi_url=ext_data.get("pypi_url"),
                installed=package in installed,
                installed_version=installed.get(package),
            )
            extensions.append(entry)

        return Catalog(
            version=data.get("version", "1.0"),
            extensions=extensions,
            last_updated=data.get("last_updated"),
        )

    async def fetch(self, force_refresh: bool = False) -> Catalog:
        """Fetch the extension catalog.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            The extension catalog

        Raises:
            httpx.HTTPError: If the fetch fails
        """
        import time

        # Check cache
        if not force_refresh and self._cache is not None:
            if time.time() - self._cache_time < CATALOG_CACHE_TIMEOUT:
                logger.debug("Returning cached catalog")
                return self._cache

        logger.info(f"Fetching extension catalog from {self.catalog_url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.catalog_url,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()

            catalog = self._parse_catalog(data)
            self._cache = catalog
            self._cache_time = time.time()

            logger.info(f"Fetched catalog with {len(catalog.extensions)} extensions")
            return catalog

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch catalog: {e}")
            # Try cached data first
            if self._cache is not None:
                logger.warning("Returning stale cached catalog due to fetch failure")
                return self._cache
            # Fall back to local catalog file
            local_catalog = self._load_local_catalog()
            if local_catalog is not None:
                logger.info("Using local catalog file as fallback")
                self._cache = local_catalog
                self._cache_time = time.time()
                return local_catalog
            raise

    def fetch_sync(self, force_refresh: bool = False) -> Catalog:
        """Fetch the extension catalog synchronously.

        This is a convenience wrapper for sync contexts.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            The extension catalog
        """
        import time

        # Check cache
        if not force_refresh and self._cache is not None:
            if time.time() - self._cache_time < CATALOG_CACHE_TIMEOUT:
                logger.debug("Returning cached catalog")
                return self._cache

        logger.info(f"Fetching extension catalog from {self.catalog_url}")

        try:
            with httpx.Client() as client:
                response = client.get(
                    self.catalog_url,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()

            catalog = self._parse_catalog(data)
            self._cache = catalog
            self._cache_time = time.time()

            logger.info(f"Fetched catalog with {len(catalog.extensions)} extensions")
            return catalog

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch catalog: {e}")
            # Try cached data first
            if self._cache is not None:
                logger.warning("Returning stale cached catalog due to fetch failure")
                return self._cache
            # Fall back to local catalog file
            local_catalog = self._load_local_catalog()
            if local_catalog is not None:
                logger.info("Using local catalog file as fallback")
                self._cache = local_catalog
                self._cache_time = time.time()
                return local_catalog
            raise

    def search(
        self,
        catalog: Catalog,
        query: Optional[str] = None,
        type_filter: Optional[str] = None,
        verified_only: bool = False,
        installed_only: bool = False,
    ) -> List[CatalogEntry]:
        """Search and filter the catalog.

        Args:
            catalog: The catalog to search
            query: Search query to match against name and description
            type_filter: Filter by extension type (exporter, fetcher, provider)
            verified_only: If True, only return verified extensions
            installed_only: If True, only return installed extensions

        Returns:
            List of matching catalog entries
        """
        results = catalog.extensions

        # Filter by type
        if type_filter:
            results = [e for e in results if e.type == type_filter]

        # Filter by verified status
        if verified_only:
            results = [e for e in results if e.verified]

        # Filter by installed status
        if installed_only:
            results = [e for e in results if e.installed]

        # Search by query
        if query:
            query = query.lower()
            results = [
                e for e in results
                if query in e.name.lower()
                or query in e.description.lower()
                or query in e.package.lower()
            ]

        return results

    def clear_cache(self) -> None:
        """Clear the cached catalog."""
        self._cache = None
        self._cache_time = 0


# Module-level singleton for convenience
_fetcher: Optional[CatalogFetcher] = None


def get_catalog_fetcher() -> CatalogFetcher:
    """Get the global catalog fetcher singleton.

    Returns:
        CatalogFetcher instance
    """
    global _fetcher
    if _fetcher is None:
        _fetcher = CatalogFetcher()
    return _fetcher


async def fetch_catalog(force_refresh: bool = False) -> Catalog:
    """Fetch the extension catalog using the global fetcher.

    Args:
        force_refresh: If True, bypass cache

    Returns:
        The extension catalog
    """
    return await get_catalog_fetcher().fetch(force_refresh)


def fetch_catalog_sync(force_refresh: bool = False) -> Catalog:
    """Fetch the extension catalog synchronously.

    Args:
        force_refresh: If True, bypass cache

    Returns:
        The extension catalog
    """
    return get_catalog_fetcher().fetch_sync(force_refresh)


def search_catalog(
    query: Optional[str] = None,
    type_filter: Optional[str] = None,
    verified_only: bool = False,
) -> List[CatalogEntry]:
    """Search the catalog synchronously.

    Fetches the catalog if not cached, then searches it.

    Args:
        query: Search query
        type_filter: Filter by type
        verified_only: Only return verified extensions

    Returns:
        List of matching catalog entries
    """
    fetcher = get_catalog_fetcher()
    catalog = fetcher.fetch_sync()
    return fetcher.search(catalog, query, type_filter, verified_only)
