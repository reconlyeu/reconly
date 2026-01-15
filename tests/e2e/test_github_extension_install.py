"""E2E tests for GitHub extension installation.

These tests perform REAL installations from GitHub and require:
1. Network access to GitHub
2. SSH key configured for git@github.com OR GH_TOKEN environment variable
3. The reconly-extensions repo to exist at github.com/reconlyeu/reconly-extensions

Run with: pytest tests/e2e/test_github_extension_install.py -v -s

Skip in CI by marking with @pytest.mark.e2e
"""
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Mark all tests in this module as e2e (can be skipped in CI)
pytestmark = [pytest.mark.e2e, pytest.mark.slow]

# GitHub repo configuration
GITHUB_REPO = "reconlyeu/reconly-extensions"
GITHUB_HTTPS_BASE = f"https://github.com/{GITHUB_REPO}.git"
# SSH URL format: git@github.com/org/repo.git (NOT git@github.com:org/repo.git for pip URLs)
GITHUB_SSH_BASE = f"git@github.com/{GITHUB_REPO}.git"

# Extensions to test
TEST_EXTENSIONS = [
    {
        "name": "reconly-ext-txt",
        "type": "exporter",
        "subdirectory": "exporters/reconly-ext-txt",
        "module": "reconly_ext_txt",
        "class": "TxtExporter",
    },
    {
        "name": "reconly-ext-hackernews",
        "type": "fetcher",
        "subdirectory": "fetchers/reconly-ext-hackernews",
        "module": "reconly_ext_hackernews",
        "class": "HackerNewsFetcher",
    },
]


def get_github_token() -> str | None:
    """Get GitHub token from environment or gh CLI."""
    # Check environment variable first
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Try to get token from gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def can_access_github_ssh() -> bool:
    """Check if SSH access to GitHub is configured."""
    try:
        result = subprocess.run(
            ["ssh", "-T", "git@github.com"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # SSH returns 1 but with "successfully authenticated" message
        return "successfully authenticated" in result.stderr.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_install_url(subdirectory: str) -> str | None:
    """Get the appropriate install URL based on available authentication.

    Returns None if no authentication method is available.
    """
    # Try SSH first (most common for developers)
    if can_access_github_ssh():
        return f"git+ssh://{GITHUB_SSH_BASE}#subdirectory={subdirectory}"

    # Try HTTPS with token
    token = get_github_token()
    if token:
        return f"git+https://{token}@github.com/{GITHUB_REPO}.git#subdirectory={subdirectory}"

    return None


def skip_if_no_github_auth():
    """Skip test if no GitHub authentication is available."""
    if not can_access_github_ssh() and not get_github_token():
        pytest.skip(
            "No GitHub authentication available. "
            "Configure SSH key for git@github.com or set GH_TOKEN environment variable."
        )


class TestGitHubCatalogFetch:
    """Test fetching the catalog from GitHub (requires auth for private repo)."""

    def test_fetch_catalog_via_gh_cli(self):
        """Fetch catalog.json using gh CLI (works with private repos)."""
        skip_if_no_github_auth()

        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_REPO}/contents/catalog.json", "-q", ".content"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            pytest.fail(f"Failed to fetch catalog: {result.stderr}")

        # Decode base64 content
        import base64
        import json

        content = base64.b64decode(result.stdout).decode("utf-8")
        catalog = json.loads(content)

        assert catalog["version"] == "2.0"
        assert len(catalog["extensions"]) >= 2

        # Verify extension entries have required fields
        for ext in catalog["extensions"]:
            assert "package" in ext
            assert "install_source" in ext
            assert "github_url" in ext
            assert ext["install_source"] == "github"

    def test_catalog_contains_txt_exporter(self):
        """Verify catalog contains the txt exporter."""
        skip_if_no_github_auth()

        result = subprocess.run(
            ["gh", "api", f"repos/{GITHUB_REPO}/contents/catalog.json", "-q", ".content"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        import base64
        import json

        content = base64.b64decode(result.stdout).decode("utf-8")
        catalog = json.loads(content)

        txt_ext = next(
            (e for e in catalog["extensions"] if e["package"] == "reconly-ext-txt"),
            None
        )

        assert txt_ext is not None
        assert txt_ext["type"] == "exporter"
        assert "exporters/reconly-ext-txt" in txt_ext["github_url"]


class TestGitHubExtensionInstall:
    """Test actual extension installation from GitHub."""

    @pytest.fixture
    def temp_venv(self, tmp_path):
        """Create a temporary virtual environment for isolated testing."""
        venv_path = tmp_path / "test_venv"

        # Create virtual environment
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            timeout=60,
        )

        # Get pip path
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip.exe"
            python_path = venv_path / "Scripts" / "python.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
            python_path = venv_path / "bin" / "python"

        # Upgrade pip
        subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip"],
            capture_output=True,
            timeout=120,
        )

        # Install reconly-core as a peer dependency (from local path)
        # This is required for extensions to be fully importable
        reconly_core_path = Path(__file__).parent.parent.parent / "packages" / "core"
        if reconly_core_path.exists():
            subprocess.run(
                [str(pip_path), "install", "-e", str(reconly_core_path)],
                capture_output=True,
                timeout=300,
            )

        yield {
            "path": venv_path,
            "pip": str(pip_path),
            "python": str(python_path),
        }

        # Cleanup
        shutil.rmtree(venv_path, ignore_errors=True)

    @pytest.mark.parametrize("extension", TEST_EXTENSIONS, ids=lambda e: e["name"])
    def test_install_extension_from_github(self, temp_venv, extension):
        """Test installing an extension from GitHub into a temp venv."""
        skip_if_no_github_auth()

        install_url = get_install_url(extension["subdirectory"])
        if not install_url:
            pytest.skip("No install URL available")

        # Install the extension
        result = subprocess.run(
            [temp_venv["pip"], "install", install_url],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for git clone + install
        )

        if result.returncode != 0:
            pytest.fail(
                f"Failed to install {extension['name']}:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Verify the package is installed
        result = subprocess.run(
            [temp_venv["pip"], "show", extension["name"]],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Package {extension['name']} not found after install"
        assert extension["name"] in result.stdout

    @pytest.mark.parametrize("extension", TEST_EXTENSIONS, ids=lambda e: e["name"])
    def test_extension_is_importable(self, temp_venv, extension):
        """Test that installed extension can be imported."""
        skip_if_no_github_auth()

        install_url = get_install_url(extension["subdirectory"])
        if not install_url:
            pytest.skip("No install URL available")

        # Install the extension
        subprocess.run(
            [temp_venv["pip"], "install", install_url],
            capture_output=True,
            timeout=300,
        )

        # Try to import the module
        import_code = f"from {extension['module']} import {extension['class']}; print('OK')"
        result = subprocess.run(
            [temp_venv["python"], "-c", import_code],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Failed to import {extension['module']}.{extension['class']}:\n"
            f"stderr: {result.stderr}"
        )
        assert "OK" in result.stdout


class TestExtensionInstallerWithGitHub:
    """Test the ExtensionInstaller class with real GitHub URLs."""

    def test_installer_validates_github_url(self):
        """Test that installer properly validates GitHub URLs."""
        from reconly_core.extensions.installer import ExtensionInstaller

        installer = ExtensionInstaller()

        # Valid GitHub URL should pass validation
        error = installer._validate_install_target(
            "git+https://github.com/reconlyeu/reconly-extensions.git"
            "#subdirectory=exporters/reconly-ext-txt"
        )
        assert error is None

        # Invalid host should fail
        error = installer._validate_install_target(
            "git+https://gitlab.com/user/reconly-ext-test.git"
        )
        assert error is not None
        assert "github" in error.lower()

    def test_installer_with_real_github_url(self):
        """Test installer with a real GitHub URL (requires auth)."""
        skip_if_no_github_auth()

        from reconly_core.extensions.installer import ExtensionInstaller

        installer = ExtensionInstaller()

        # Get authenticated URL
        install_url = get_install_url("exporters/reconly-ext-txt")
        if not install_url:
            pytest.skip("No install URL available")

        # Just test validation, don't actually install
        error = installer._validate_install_target(install_url)
        assert error is None, f"Validation failed: {error}"


class TestCatalogFetcherWithGitHub:
    """Test the CatalogFetcher with real GitHub URLs (for public repos)."""

    def test_catalog_fetcher_url_configured(self):
        """Verify catalog fetcher is configured with correct GitHub URL."""
        from reconly_core.extensions.catalog import DEFAULT_CATALOG_URL

        assert "githubusercontent.com" in DEFAULT_CATALOG_URL or "github.com" in DEFAULT_CATALOG_URL
        assert "reconlyeu/reconly-extensions" in DEFAULT_CATALOG_URL
        assert "catalog.json" in DEFAULT_CATALOG_URL


# Convenience function to run tests manually
if __name__ == "__main__":
    print("GitHub Extension E2E Tests")
    print("=" * 50)

    print("\nChecking authentication methods...")

    if can_access_github_ssh():
        print("  [OK] SSH access to GitHub configured")
    else:
        print("  [--] SSH access not available")

    token = get_github_token()
    if token:
        print("  [OK] GitHub token available")
    else:
        print("  [--] GitHub token not available")

    if not can_access_github_ssh() and not token:
        print("\n[ERROR] No authentication method available!")
        print("Configure SSH key or set GH_TOKEN environment variable.")
        sys.exit(1)

    print("\nRunning tests...")
    pytest.main([__file__, "-v", "-s"])
