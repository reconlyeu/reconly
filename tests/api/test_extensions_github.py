"""Integration tests for GitHub-based extension installation."""
import pytest
from unittest.mock import patch, MagicMock

from reconly_core.extensions.catalog import Catalog, CatalogEntry
from reconly_core.extensions.installer import InstallResult


def make_catalog_entry(
    package: str,
    *,
    name: str | None = None,
    verified: bool = False,
    install_source: str = "pypi",
    github_url: str | None = None,
) -> CatalogEntry:
    """Create a CatalogEntry with sensible defaults."""
    return CatalogEntry(
        package=package,
        name=name or package.replace("reconly-ext-", "").title(),
        type="exporter",
        description=f"Description for {package}",
        author="Test Author",
        version="1.0.0",
        verified=verified,
        install_source=install_source,
        github_url=github_url,
        homepage=f"https://github.com/reconlyeu/{package}" if github_url else None,
    )


def make_install_result(
    success: bool,
    package: str = "",
    version: str = "1.0.0",
    error: str | None = None,
) -> InstallResult:
    """Create an InstallResult with sensible defaults."""
    return InstallResult(
        success=success,
        package=package,
        version=version if success else None,
        requires_restart=success,
        error=error,
    )


GITHUB_BASE_URL = "git+https://github.com/reconlyeu/reconly-extensions.git"


def github_url(subdirectory: str) -> str:
    """Build a GitHub URL with subdirectory fragment."""
    return f"{GITHUB_BASE_URL}#subdirectory={subdirectory}"


@pytest.fixture
def mock_installer():
    """Create a mock extension installer."""
    with patch("reconly_api.routes.extensions.get_extension_installer") as mock_getter:
        installer = MagicMock()
        mock_getter.return_value = installer
        yield installer


@pytest.fixture
def mock_catalog_fetcher():
    """Create a mock catalog fetcher."""
    with patch("reconly_api.routes.extensions.get_catalog_fetcher") as mock_getter:
        fetcher = MagicMock()
        mock_getter.return_value = fetcher
        yield fetcher


@pytest.mark.api
class TestGitHubURLValidation:
    """Test GitHub URL validation in extension installation."""

    def test_install_valid_github_url(self, client, mock_installer):
        """Test installing extension via valid GitHub URL."""
        url = github_url("extensions/reconly-ext-txt")
        mock_installer.install.return_value = make_install_result(
            success=True, package="reconly-ext-txt"
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": url},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["package"] == "reconly-ext-txt"
        mock_installer.install.assert_called_once_with(url, upgrade=False)

    def test_install_github_url_with_subdirectory(self, client, mock_installer):
        """Test installing from GitHub monorepo subdirectory."""
        url = github_url("extensions/reconly-ext-hackernews")
        mock_installer.install.return_value = make_install_result(
            success=True, package="reconly-ext-hackernews"
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": url},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_install_github_url_invalid_host(self, client):
        """Test rejecting non-GitHub URLs."""
        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": "git+https://gitlab.com/user/reconly-ext-test.git"},
        )

        assert response.status_code == 400
        assert "github.com" in response.json()["detail"].lower()

    def test_install_github_url_missing_prefix(self, client):
        """Test rejecting URLs without reconly-ext- prefix."""
        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": "git+https://github.com/user/my-extension.git"},
        )

        assert response.status_code == 400
        assert "reconly-ext-" in response.json()["detail"]

    def test_install_github_url_without_git_prefix(self, client):
        """Test rejecting GitHub URLs without git+ prefix."""
        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": "https://github.com/user/reconly-ext-test.git"},
        )

        assert response.status_code == 400


@pytest.mark.api
class TestCatalogWithGitHubExtensions:
    """Test catalog entries with GitHub installation sources."""

    def test_catalog_returns_github_and_pypi_extensions(
        self, client, mock_catalog_fetcher
    ):
        """Test catalog includes install_source and github_url fields."""
        github_ext_url = github_url("extensions/reconly-ext-txt")
        mock_catalog_fetcher.fetch_sync.return_value = Catalog(
            version="2.0",
            extensions=[
                make_catalog_entry(
                    "reconly-ext-txt",
                    verified=True,
                    install_source="github",
                    github_url=github_ext_url,
                ),
                make_catalog_entry(
                    "reconly-ext-notion",
                    install_source="pypi",
                ),
            ],
            last_updated="2026-01-15T00:00:00Z",
        )

        response = client.get("/api/v1/extensions/catalog")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0"
        assert len(data["extensions"]) == 2

        github_ext = data["extensions"][0]
        assert github_ext["install_source"] == "github"
        assert "git+https://github.com/" in github_ext["github_url"]
        assert github_ext["verified"] is True

        pypi_ext = data["extensions"][1]
        assert pypi_ext["install_source"] == "pypi"
        assert pypi_ext["github_url"] is None

    def test_install_from_catalog_github_extension(
        self, client, mock_catalog_fetcher, mock_installer
    ):
        """Test installing GitHub extension from catalog entry."""
        ext_url = github_url("extensions/reconly-ext-txt")
        mock_catalog_fetcher.fetch_sync.return_value = Catalog(
            version="2.0",
            extensions=[
                make_catalog_entry(
                    "reconly-ext-txt",
                    verified=True,
                    install_source="github",
                    github_url=ext_url,
                ),
            ],
        )

        # Fetch catalog to get the github_url
        catalog_response = client.get("/api/v1/extensions/catalog")
        assert catalog_response.status_code == 200
        catalog_github_url = catalog_response.json()["extensions"][0]["github_url"]

        # Install using the URL from catalog
        mock_installer.install.return_value = make_install_result(
            success=True, package="reconly-ext-txt"
        )

        install_response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": catalog_github_url},
        )

        assert install_response.status_code == 200
        assert install_response.json()["success"] is True


@pytest.mark.api
class TestGitHubInstallErrorHandling:
    """Test error handling with GitHub installations."""

    def test_install_github_url_clone_failure(self, client, mock_installer):
        """Test error handling when git clone fails."""
        mock_installer.install.return_value = make_install_result(
            success=False,
            package="reconly-ext-test",
            error="Failed to install from GitHub: git clone failed with exit code 128",
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": github_url("extensions/reconly-ext-nonexistent")},
        )

        assert response.status_code == 400
        assert "Failed to install from GitHub" in response.json()["detail"]

    def test_install_github_url_network_failure(self, client, mock_installer):
        """Test error handling for network failures."""
        mock_installer.install.return_value = make_install_result(
            success=False,
            error="Network error: Could not resolve host: github.com",
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": github_url("extensions/reconly-ext-txt")},
        )

        assert response.status_code == 400
        assert "Network error" in response.json()["detail"]

    def test_install_github_url_invalid_subdirectory(self, client, mock_installer):
        """Test error handling for invalid subdirectory."""
        mock_installer.install.return_value = make_install_result(
            success=False,
            error="Subdirectory 'invalid/path' does not exist in repository",
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": f"{GITHUB_BASE_URL}#subdirectory=invalid/path"},
        )

        assert response.status_code == 400
        assert "does not exist" in response.json()["detail"]

    def test_catalog_fetch_network_failure(self, client, mock_catalog_fetcher):
        """Test catalog fetch with network failure."""
        mock_catalog_fetcher.fetch_sync.side_effect = Exception(
            "Failed to fetch catalog from GitHub: Network error"
        )

        response = client.get("/api/v1/extensions/catalog")

        assert response.status_code == 503
        assert "Failed to fetch" in response.json()["detail"]

    def test_catalog_fetch_invalid_json(self, client, mock_catalog_fetcher):
        """Test catalog fetch with invalid JSON."""
        mock_catalog_fetcher.fetch_sync.side_effect = ValueError(
            "Invalid catalog JSON format"
        )

        response = client.get("/api/v1/extensions/catalog")

        assert response.status_code == 503


@pytest.mark.api
class TestGitHubInstallWithUpgrade:
    """Test upgrading GitHub-based extensions."""

    def test_upgrade_github_extension(self, client, mock_installer):
        """Test upgrading an already installed GitHub extension."""
        url = github_url("extensions/reconly-ext-txt")
        mock_installer.install.return_value = make_install_result(
            success=True, package="reconly-ext-txt", version="0.2.0"
        )

        response = client.post(
            "/api/v1/extensions/install",
            json={"github_url": url, "upgrade": True},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["version"] == "0.2.0"
        mock_installer.install.assert_called_once_with(url, upgrade=True)


@pytest.mark.api
class TestCatalogSearch:
    """Test searching catalog with GitHub extensions."""

    def test_search_verified_github_extensions(self, client, mock_catalog_fetcher):
        """Test searching for verified GitHub extensions only."""
        verified_ext = make_catalog_entry(
            "reconly-ext-txt",
            verified=True,
            install_source="github",
            github_url=github_url("extensions/reconly-ext-txt"),
        )
        unverified_ext = make_catalog_entry(
            "reconly-ext-custom",
            verified=False,
            install_source="github",
            github_url="git+https://github.com/user/reconly-ext-custom.git",
        )

        mock_catalog_fetcher.fetch_sync.return_value = Catalog(
            version="2.0",
            extensions=[verified_ext, unverified_ext],
        )
        mock_catalog_fetcher.search.return_value = [verified_ext]

        response = client.get("/api/v1/extensions/catalog/search?verified_only=true")

        assert response.status_code == 200
        call_args = mock_catalog_fetcher.search.call_args
        assert call_args[1]["verified_only"] is True
