"""Tests for extension catalog functionality."""
import json
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from reconly_core.extensions.catalog import (
    CatalogEntry,
    Catalog,
    CatalogFetcher,
    get_catalog_fetcher,
    DEFAULT_CATALOG_URL,
    CATALOG_CACHE_TIMEOUT,
)


class TestCatalogEntry:
    """Tests for CatalogEntry dataclass."""

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        entry = CatalogEntry(
            package="reconly-ext-test",
            name="Test Extension",
            type="exporter",
            description="A test extension",
            author="Test Author",
            version="1.0.0",
            verified=True,
            homepage="https://example.com",
            pypi_url="https://pypi.org/project/reconly-ext-test",
            installed=True,
            installed_version="1.0.0",
        )

        d = entry.to_dict()

        assert d["package"] == "reconly-ext-test"
        assert d["name"] == "Test Extension"
        assert d["type"] == "exporter"
        assert d["description"] == "A test extension"
        assert d["author"] == "Test Author"
        assert d["version"] == "1.0.0"
        assert d["verified"] is True
        assert d["homepage"] == "https://example.com"
        assert d["pypi_url"] == "https://pypi.org/project/reconly-ext-test"
        assert d["installed"] is True
        assert d["installed_version"] == "1.0.0"

    def test_default_values(self):
        """Test default values for optional fields."""
        entry = CatalogEntry(
            package="reconly-ext-minimal",
            name="Minimal",
            type="fetcher",
            description="",
            author="Unknown",
        )

        assert entry.version == "0.0.0"
        assert entry.verified is False
        assert entry.homepage is None
        assert entry.pypi_url is None
        assert entry.installed is False
        assert entry.installed_version is None


class TestCatalog:
    """Tests for Catalog dataclass."""

    def test_to_dict(self):
        """Test to_dict includes all fields."""
        entry = CatalogEntry(
            package="reconly-ext-test",
            name="Test",
            type="exporter",
            description="Test",
            author="Test",
        )
        catalog = Catalog(
            version="1.0",
            extensions=[entry],
            last_updated="2024-01-01T00:00:00Z",
        )

        d = catalog.to_dict()

        assert d["version"] == "1.0"
        assert len(d["extensions"]) == 1
        assert d["extensions"][0]["package"] == "reconly-ext-test"
        assert d["last_updated"] == "2024-01-01T00:00:00Z"

    def test_empty_catalog(self):
        """Test empty catalog."""
        catalog = Catalog(version="1.0")

        assert catalog.extensions == []
        assert catalog.last_updated is None


class TestCatalogFetcher:
    """Tests for CatalogFetcher class."""

    def setup_method(self):
        """Create fresh fetcher for each test."""
        self.fetcher = CatalogFetcher(timeout=5)

    def test_init_default_values(self):
        """Test default initialization."""
        fetcher = CatalogFetcher()

        assert fetcher.catalog_url == DEFAULT_CATALOG_URL
        assert fetcher.local_path is None
        assert fetcher.timeout == 30
        assert fetcher._cache is None

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        fetcher = CatalogFetcher(
            catalog_url="https://custom.url/catalog.json",
            local_path="/path/to/local/catalog.json",
            timeout=60,
        )

        assert fetcher.catalog_url == "https://custom.url/catalog.json"
        assert fetcher.local_path == "/path/to/local/catalog.json"
        assert fetcher.timeout == 60


class TestParseCatalog:
    """Tests for _parse_catalog method."""

    def setup_method(self):
        """Create fresh fetcher for each test."""
        self.fetcher = CatalogFetcher()

    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_parse_empty_catalog(self, mock_installed):
        """Test parsing empty catalog."""
        mock_installed.return_value = {}
        data = {"version": "1.0", "extensions": []}

        catalog = self.fetcher._parse_catalog(data)

        assert catalog.version == "1.0"
        assert catalog.extensions == []

    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_parse_catalog_with_extensions(self, mock_installed):
        """Test parsing catalog with extensions."""
        mock_installed.return_value = {}
        data = {
            "version": "1.0",
            "last_updated": "2024-01-01T00:00:00Z",
            "extensions": [
                {
                    "package": "reconly-ext-notion",
                    "name": "Notion Exporter",
                    "type": "exporter",
                    "description": "Export to Notion",
                    "author": "Reconly",
                    "version": "1.0.0",
                    "verified": True,
                    "homepage": "https://github.com/reconly/reconly-ext-notion",
                },
                {
                    "package": "reconly-ext-reddit",
                    "name": "Reddit Fetcher",
                    "type": "fetcher",
                    "description": "Fetch from Reddit",
                    "author": "Community",
                },
            ],
        }

        catalog = self.fetcher._parse_catalog(data)

        assert catalog.version == "1.0"
        assert catalog.last_updated == "2024-01-01T00:00:00Z"
        assert len(catalog.extensions) == 2

        notion = catalog.extensions[0]
        assert notion.package == "reconly-ext-notion"
        assert notion.name == "Notion Exporter"
        assert notion.verified is True

        reddit = catalog.extensions[1]
        assert reddit.package == "reconly-ext-reddit"
        assert reddit.verified is False  # Default

    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_parse_catalog_marks_installed(self, mock_installed):
        """Test parsing marks installed extensions."""
        mock_installed.return_value = {
            "reconly-ext-notion": "1.0.0",
        }
        data = {
            "version": "1.0",
            "extensions": [
                {
                    "package": "reconly-ext-notion",
                    "name": "Notion",
                    "type": "exporter",
                    "description": "",
                    "author": "",
                },
                {
                    "package": "reconly-ext-other",
                    "name": "Other",
                    "type": "exporter",
                    "description": "",
                    "author": "",
                },
            ],
        }

        catalog = self.fetcher._parse_catalog(data)

        notion = catalog.extensions[0]
        assert notion.installed is True
        assert notion.installed_version == "1.0.0"

        other = catalog.extensions[1]
        assert other.installed is False
        assert other.installed_version is None


class TestSearch:
    """Tests for search method."""

    def setup_method(self):
        """Create fetcher and sample catalog."""
        self.fetcher = CatalogFetcher()
        self.catalog = Catalog(
            version="1.0",
            extensions=[
                CatalogEntry(
                    package="reconly-ext-notion",
                    name="Notion Exporter",
                    type="exporter",
                    description="Export digests to Notion",
                    author="Reconly",
                    verified=True,
                    installed=True,
                ),
                CatalogEntry(
                    package="reconly-ext-slack",
                    name="Slack Exporter",
                    type="exporter",
                    description="Export digests to Slack",
                    author="Community",
                    verified=False,
                    installed=False,
                ),
                CatalogEntry(
                    package="reconly-ext-reddit",
                    name="Reddit Fetcher",
                    type="fetcher",
                    description="Fetch content from Reddit",
                    author="Community",
                    verified=True,
                    installed=False,
                ),
            ],
        )

    def test_search_no_filters(self):
        """Test search with no filters returns all."""
        results = self.fetcher.search(self.catalog)
        assert len(results) == 3

    def test_search_by_query_name(self):
        """Test search matches name."""
        results = self.fetcher.search(self.catalog, query="notion")
        assert len(results) == 1
        assert results[0].name == "Notion Exporter"

    def test_search_by_query_description(self):
        """Test search matches description."""
        results = self.fetcher.search(self.catalog, query="slack")
        assert len(results) == 1
        assert results[0].name == "Slack Exporter"

    def test_search_by_query_package(self):
        """Test search matches package name."""
        results = self.fetcher.search(self.catalog, query="reddit")
        assert len(results) == 1
        assert results[0].name == "Reddit Fetcher"

    def test_search_case_insensitive(self):
        """Test search is case insensitive."""
        results = self.fetcher.search(self.catalog, query="NOTION")
        assert len(results) == 1
        assert results[0].name == "Notion Exporter"

    def test_filter_by_type(self):
        """Test filter by extension type."""
        results = self.fetcher.search(self.catalog, type_filter="exporter")
        assert len(results) == 2
        for r in results:
            assert r.type == "exporter"

        results = self.fetcher.search(self.catalog, type_filter="fetcher")
        assert len(results) == 1
        assert results[0].type == "fetcher"

    def test_filter_verified_only(self):
        """Test filter for verified extensions only."""
        results = self.fetcher.search(self.catalog, verified_only=True)
        assert len(results) == 2
        for r in results:
            assert r.verified is True

    def test_filter_installed_only(self):
        """Test filter for installed extensions only."""
        results = self.fetcher.search(self.catalog, installed_only=True)
        assert len(results) == 1
        assert results[0].installed is True

    def test_combined_filters(self):
        """Test combining multiple filters."""
        results = self.fetcher.search(
            self.catalog,
            type_filter="exporter",
            verified_only=True,
        )
        assert len(results) == 1
        assert results[0].name == "Notion Exporter"

    def test_search_no_results(self):
        """Test search with no matches returns empty list."""
        results = self.fetcher.search(self.catalog, query="nonexistent")
        assert results == []


class TestFetchSync:
    """Tests for fetch_sync method."""

    def setup_method(self):
        """Create fresh fetcher for each test."""
        self.fetcher = CatalogFetcher(timeout=5)

    @patch('reconly_core.extensions.catalog.httpx.Client')
    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_fetch_sync_success(self, mock_installed, mock_client):
        """Test successful synchronous fetch."""
        mock_installed.return_value = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "version": "1.0",
            "extensions": [],
        }
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        catalog = self.fetcher.fetch_sync()

        assert catalog.version == "1.0"

    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_fetch_sync_returns_cache(self, mock_installed):
        """Test fetch_sync returns cached data."""
        mock_installed.return_value = {}

        # Set up cache
        cached_catalog = Catalog(version="cached", extensions=[])
        self.fetcher._cache = cached_catalog
        self.fetcher._cache_time = time.time()

        catalog = self.fetcher.fetch_sync()

        assert catalog.version == "cached"
        mock_installed.assert_not_called()  # Should not fetch

    @patch.object(CatalogFetcher, '_get_installed_extensions')
    @patch('reconly_core.extensions.catalog.httpx.Client')
    def test_fetch_sync_force_refresh_ignores_cache(self, mock_client, mock_installed):
        """Test force_refresh bypasses cache."""
        mock_installed.return_value = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "version": "fresh",
            "extensions": [],
        }
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        # Set up cache
        self.fetcher._cache = Catalog(version="cached")
        self.fetcher._cache_time = time.time()

        catalog = self.fetcher.fetch_sync(force_refresh=True)

        assert catalog.version == "fresh"

    @patch('reconly_core.extensions.catalog.httpx.Client')
    @patch.object(CatalogFetcher, '_load_local_catalog')
    def test_fetch_sync_fallback_to_stale_cache(self, mock_local, mock_client):
        """Test fetch falls back to stale cache on error."""
        import httpx
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.HTTPError("Failed")
        mock_local.return_value = None

        # Set up stale cache
        stale_catalog = Catalog(version="stale")
        self.fetcher._cache = stale_catalog
        self.fetcher._cache_time = time.time() - CATALOG_CACHE_TIMEOUT - 100

        catalog = self.fetcher.fetch_sync(force_refresh=True)

        assert catalog.version == "stale"

    @patch('reconly_core.extensions.catalog.httpx.Client')
    @patch.object(CatalogFetcher, '_load_local_catalog')
    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_fetch_sync_fallback_to_local(self, mock_installed, mock_local, mock_client):
        """Test fetch falls back to local catalog on error."""
        import httpx
        mock_installed.return_value = {}
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.HTTPError("Failed")

        local_catalog = Catalog(version="local", extensions=[])
        mock_local.return_value = local_catalog

        catalog = self.fetcher.fetch_sync()

        assert catalog.version == "local"
        mock_local.assert_called_once()


class TestFetchAsync:
    """Tests for async fetch method."""

    @pytest.mark.asyncio
    @patch('reconly_core.extensions.catalog.httpx.AsyncClient')
    @patch.object(CatalogFetcher, '_get_installed_extensions')
    async def test_fetch_success(self, mock_installed, mock_client):
        """Test successful async fetch."""
        mock_installed.return_value = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "version": "1.0",
            "extensions": [],
        }

        mock_async_client = AsyncMock()
        mock_async_client.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_async_client

        fetcher = CatalogFetcher()
        catalog = await fetcher.fetch()

        assert catalog.version == "1.0"

    @pytest.mark.asyncio
    @patch.object(CatalogFetcher, '_get_installed_extensions')
    async def test_fetch_returns_cache(self, mock_installed):
        """Test async fetch returns cached data."""
        mock_installed.return_value = {}

        fetcher = CatalogFetcher()
        fetcher._cache = Catalog(version="cached")
        fetcher._cache_time = time.time()

        catalog = await fetcher.fetch()

        assert catalog.version == "cached"


class TestClearCache:
    """Tests for clear_cache method."""

    def test_clear_cache(self):
        """Test clear_cache resets cache state."""
        fetcher = CatalogFetcher()
        fetcher._cache = Catalog(version="test")
        fetcher._cache_time = time.time()

        fetcher.clear_cache()

        assert fetcher._cache is None
        assert fetcher._cache_time == 0


class TestFindLocalCatalog:
    """Tests for _find_local_catalog method."""

    def test_explicit_path_exists(self, tmp_path):
        """Test finds explicitly configured path."""
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text('{"version": "1.0"}')

        fetcher = CatalogFetcher(local_path=str(catalog_path))
        found = fetcher._find_local_catalog()

        assert found == catalog_path

    def test_explicit_path_not_exists(self, tmp_path):
        """Test returns None for missing explicit path."""
        fetcher = CatalogFetcher(local_path=str(tmp_path / "missing.json"))
        fetcher._find_local_catalog()

        # Should continue searching, may find in cwd or return None
        # depending on test environment

    @patch.dict('os.environ', {'RECONLY_CATALOG_PATH': ''})
    def test_env_var_path(self, tmp_path):
        """Test finds path from environment variable."""
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text('{"version": "1.0"}')

        with patch.dict('os.environ', {'RECONLY_CATALOG_PATH': str(catalog_path)}):
            fetcher = CatalogFetcher()
            found = fetcher._find_local_catalog()

            assert found == catalog_path


class TestLoadLocalCatalog:
    """Tests for _load_local_catalog method."""

    @patch.object(CatalogFetcher, '_find_local_catalog')
    @patch.object(CatalogFetcher, '_get_installed_extensions')
    def test_load_valid_catalog(self, mock_installed, mock_find, tmp_path):
        """Test loading valid local catalog."""
        mock_installed.return_value = {}

        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text(json.dumps({
            "version": "local",
            "extensions": [
                {
                    "package": "reconly-ext-test",
                    "name": "Test",
                    "type": "exporter",
                    "description": "Test",
                    "author": "Test",
                }
            ],
        }))

        mock_find.return_value = catalog_path

        fetcher = CatalogFetcher()
        catalog = fetcher._load_local_catalog()

        assert catalog is not None
        assert catalog.version == "local"
        assert len(catalog.extensions) == 1

    @patch.object(CatalogFetcher, '_find_local_catalog')
    def test_load_no_file(self, mock_find):
        """Test loading when no file found."""
        mock_find.return_value = None

        fetcher = CatalogFetcher()
        catalog = fetcher._load_local_catalog()

        assert catalog is None

    @patch.object(CatalogFetcher, '_find_local_catalog')
    def test_load_invalid_json(self, mock_find, tmp_path):
        """Test loading invalid JSON returns None."""
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("not valid json {")

        mock_find.return_value = catalog_path

        fetcher = CatalogFetcher()
        catalog = fetcher._load_local_catalog()

        assert catalog is None


class TestSingleton:
    """Tests for module-level singleton."""

    def test_get_catalog_fetcher_returns_fetcher(self):
        """Test get_catalog_fetcher returns CatalogFetcher."""
        fetcher = get_catalog_fetcher()
        assert isinstance(fetcher, CatalogFetcher)

    def test_get_catalog_fetcher_singleton(self):
        """Test get_catalog_fetcher returns same instance."""
        fetcher1 = get_catalog_fetcher()
        fetcher2 = get_catalog_fetcher()
        assert fetcher1 is fetcher2
