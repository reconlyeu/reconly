"""Tests for Extensions API routes."""
import pytest
from unittest.mock import patch, MagicMock

from reconly_core.extensions.types import ExtensionType, ExtensionMetadata
from reconly_core.extensions.catalog import Catalog, CatalogEntry


@pytest.mark.api
class TestExtensionsListAPI:
    """Test suite for GET /api/v1/extensions endpoints."""

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.list_extension_exporters')
    @patch('reconly_api.routes.extensions.list_extension_fetchers')
    def test_list_extensions_empty(
        self, mock_fetchers, mock_exporters, mock_ensure, client
    ):
        """Test listing extensions when none installed."""
        mock_exporters.return_value = []
        mock_fetchers.return_value = []

        response = client.get("/api/v1/extensions")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.list_extension_exporters')
    @patch('reconly_api.routes.extensions.list_extension_fetchers')
    def test_list_extensions_filter_by_type(
        self, mock_fetchers, mock_exporters, mock_ensure, client
    ):
        """Test filtering extensions by type."""
        mock_exporters.return_value = []
        mock_fetchers.return_value = []

        response = client.get("/api/v1/extensions?type=exporter")
        assert response.status_code == 200

        response = client.get("/api/v1/extensions?type=fetcher")
        assert response.status_code == 200


@pytest.mark.api
class TestExtensionsByTypeAPI:
    """Test suite for GET /api/v1/extensions/{type}/ endpoints."""

    def test_invalid_type_returns_400(self, client):
        """Test invalid extension type returns 400."""
        response = client.get("/api/v1/extensions/invalid")
        assert response.status_code == 400
        assert "Invalid extension type" in response.json()["detail"]

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.list_extension_exporters')
    def test_list_exporter_extensions(self, mock_exporters, mock_ensure, client):
        """Test listing exporter extensions."""
        mock_exporters.return_value = []

        response = client.get("/api/v1/extensions/exporter")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.list_extension_fetchers')
    def test_list_fetcher_extensions(self, mock_fetchers, mock_ensure, client):
        """Test listing fetcher extensions."""
        mock_fetchers.return_value = []

        response = client.get("/api/v1/extensions/fetcher")
        assert response.status_code == 200


@pytest.mark.api
class TestExtensionDetailsAPI:
    """Test suite for GET /api/v1/extensions/{type}/{name}/ endpoints."""

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.is_exporter_extension')
    def test_get_nonexistent_extension(self, mock_is_ext, mock_ensure, client):
        """Test getting non-existent extension returns 404."""
        mock_is_ext.return_value = False

        response = client.get("/api/v1/extensions/exporter/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.is_fetcher_extension')
    def test_get_nonexistent_fetcher(self, mock_is_ext, mock_ensure, client):
        """Test getting non-existent fetcher returns 404."""
        mock_is_ext.return_value = False

        response = client.get("/api/v1/extensions/fetcher/nonexistent")
        assert response.status_code == 404


@pytest.mark.api
class TestExtensionToggleAPI:
    """Test suite for PUT /api/v1/extensions/{type}/{name}/enabled endpoints."""

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.is_exporter_extension')
    def test_toggle_nonexistent_extension(self, mock_is_ext, mock_ensure, client):
        """Test toggling non-existent extension returns 404."""
        mock_is_ext.return_value = False

        response = client.put(
            "/api/v1/extensions/exporter/nonexistentenabled",
            json={"enabled": True}
        )
        assert response.status_code == 404

    @patch('reconly_api.routes.extensions.ensure_extensions_loaded')
    @patch('reconly_api.routes.extensions.is_exporter_extension')
    @patch('reconly_api.routes.extensions.get_exporter')
    @patch('reconly_api.routes.extensions.can_enable_extension')
    def test_toggle_unconfigured_extension(
        self, mock_can, mock_exporter, mock_is_ext, mock_ensure, client
    ):
        """Test enabling unconfigured extension returns 400."""
        mock_is_ext.return_value = True
        mock_exporter.return_value.get_config_schema.return_value.fields = [
            MagicMock(required=True, key="api_key")
        ]
        mock_can.return_value = False

        response = client.put(
            "/api/v1/extensions/exporter/testenabled",
            json={"enabled": True}
        )
        assert response.status_code == 400
        assert "required configuration" in response.json()["detail"].lower()


@pytest.mark.api
class TestCatalogAPI:
    """Test suite for /api/v1/extensions/catalog endpoints."""

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_get_catalog_success(self, mock_get_fetcher, client):
        """Test successful catalog fetch."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_sync.return_value = Catalog(
            version="1.0",
            extensions=[
                CatalogEntry(
                    package="reconly-ext-test",
                    name="Test Extension",
                    type="exporter",
                    description="A test extension",
                    author="Test Author",
                    version="1.0.0",
                    verified=True,
                )
            ],
            last_updated="2024-01-01T00:00:00Z",
        )
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalog")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "1.0"
        assert len(data["extensions"]) == 1
        assert data["extensions"][0]["package"] == "reconly-ext-test"
        assert data["extensions"][0]["verified"] is True

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_get_catalog_force_refresh(self, mock_get_fetcher, client):
        """Test catalog fetch with force_refresh parameter."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_sync.return_value = Catalog(version="1.0")
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalog?force_refresh=true")
        assert response.status_code == 200

        mock_fetcher.fetch_sync.assert_called_once_with(force_refresh=True)

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_get_catalog_error(self, mock_get_fetcher, client):
        """Test catalog fetch error handling."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_sync.side_effect = Exception("Network error")
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalog")
        assert response.status_code == 503
        assert "Failed to fetch" in response.json()["detail"]


@pytest.mark.api
class TestCatalogSearchAPI:
    """Test suite for GET /api/v1/extensions/catalogsearch/ endpoint."""

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_search_catalog_by_query(self, mock_get_fetcher, client):
        """Test searching catalog by query."""
        mock_fetcher = MagicMock()
        catalog = Catalog(
            version="1.0",
            extensions=[
                CatalogEntry(
                    package="reconly-ext-notion",
                    name="Notion Exporter",
                    type="exporter",
                    description="Export to Notion",
                    author="Test",
                ),
            ],
        )
        mock_fetcher.fetch_sync.return_value = catalog
        mock_fetcher.search.return_value = catalog.extensions
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalogsearch/?q=notion")
        assert response.status_code == 200

        mock_fetcher.search.assert_called_once()

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_search_catalog_by_type(self, mock_get_fetcher, client):
        """Test searching catalog by type."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_sync.return_value = Catalog(version="1.0")
        mock_fetcher.search.return_value = []
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalogsearch/?type=exporter")
        assert response.status_code == 200

        mock_fetcher.search.assert_called_once()
        call_args = mock_fetcher.search.call_args
        assert call_args[1]["type_filter"] == "exporter"

    @patch('reconly_api.routes.extensions.get_catalog_fetcher')
    def test_search_catalog_verified_only(self, mock_get_fetcher, client):
        """Test searching catalog for verified only."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_sync.return_value = Catalog(version="1.0")
        mock_fetcher.search.return_value = []
        mock_get_fetcher.return_value = mock_fetcher

        response = client.get("/api/v1/extensions/catalogsearch/?verified_only=true")
        assert response.status_code == 200

        call_args = mock_fetcher.search.call_args
        assert call_args[1]["verified_only"] is True


@pytest.mark.api
class TestInstallAPI:
    """Test suite for POST /api/v1/extensions/install endpoint."""

    def test_install_invalid_package_name(self, client):
        """Test install with invalid package name."""
        response = client.post(
            "/api/v1/extensions/install",
            json={"package": "invalid-package"}
        )
        assert response.status_code == 400
        assert "reconly-ext-" in response.json()["detail"]

    @patch('reconly_api.routes.extensions.get_extension_installer')
    def test_install_success(self, mock_get_installer, client):
        """Test successful installation."""
        mock_installer = MagicMock()
        mock_installer.install.return_value = MagicMock(
            success=True,
            package="reconly-ext-test",
            version="1.0.0",
            requires_restart=True,
        )
        mock_get_installer.return_value = mock_installer

        response = client.post(
            "/api/v1/extensions/install",
            json={"package": "reconly-ext-test"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["package"] == "reconly-ext-test"
        assert data["version"] == "1.0.0"
        assert data["requires_restart"] is True

    @patch('reconly_api.routes.extensions.get_extension_installer')
    def test_install_failure(self, mock_get_installer, client):
        """Test installation failure."""
        mock_installer = MagicMock()
        mock_installer.install.return_value = MagicMock(
            success=False,
            package="reconly-ext-missing",
            error="Package not found on PyPI",
        )
        mock_get_installer.return_value = mock_installer

        response = client.post(
            "/api/v1/extensions/install",
            json={"package": "reconly-ext-missing"}
        )
        assert response.status_code == 400

    @patch('reconly_api.routes.extensions.get_extension_installer')
    def test_install_with_upgrade(self, mock_get_installer, client):
        """Test installation with upgrade flag."""
        mock_installer = MagicMock()
        mock_installer.install.return_value = MagicMock(
            success=True,
            package="reconly-ext-test",
            version="2.0.0",
            requires_restart=True,
        )
        mock_get_installer.return_value = mock_installer

        response = client.post(
            "/api/v1/extensions/install",
            json={"package": "reconly-ext-test", "upgrade": True}
        )
        assert response.status_code == 200

        mock_installer.install.assert_called_once_with(
            "reconly-ext-test", upgrade=True
        )


@pytest.mark.api
class TestUninstallAPI:
    """Test suite for DELETE /api/v1/extensions/{type}/{name}/ endpoint."""

    @patch('reconly_api.routes.extensions.is_exporter_extension')
    def test_uninstall_nonexistent_extension(self, mock_is_ext, client):
        """Test uninstalling non-existent extension."""
        mock_is_ext.return_value = False

        response = client.delete("/api/v1/extensions/exporter/nonexistent")
        assert response.status_code == 404

    @patch('reconly_api.routes.extensions.is_exporter_extension')
    @patch('reconly_api.routes.extensions.get_extension_installer')
    def test_uninstall_success(self, mock_get_installer, mock_is_ext, client):
        """Test successful uninstallation."""
        mock_is_ext.return_value = True
        mock_installer = MagicMock()
        mock_installer.uninstall.return_value = MagicMock(
            success=True,
            package="reconly-ext-test",
            requires_restart=True,
        )
        mock_get_installer.return_value = mock_installer

        response = client.delete("/api/v1/extensions/exporter/test")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["requires_restart"] is True

    @patch('reconly_api.routes.extensions.is_exporter_extension')
    @patch('reconly_api.routes.extensions.get_extension_installer')
    def test_uninstall_failure(self, mock_get_installer, mock_is_ext, client):
        """Test uninstallation failure."""
        mock_is_ext.return_value = True
        mock_installer = MagicMock()
        mock_installer.uninstall.return_value = MagicMock(
            success=False,
            package="reconly-ext-test",
            error="Package not installed",
        )
        mock_get_installer.return_value = mock_installer

        response = client.delete("/api/v1/extensions/exporter/test")
        assert response.status_code == 400


@pytest.mark.api
class TestDeprecatedSettingsAPI:
    """Test suite for deprecated settings endpoint."""

    def test_settings_endpoint_returns_410(self, client):
        """Test deprecated settings endpoint returns 410 Gone."""
        response = client.put(
            "/api/v1/extensions/exporter/testsettings",
            json={"settings": {}}
        )
        assert response.status_code == 410
        assert "deprecated" in response.json()["detail"].lower()
        assert "exporters" in response.json()["detail"]  # Points to correct API
