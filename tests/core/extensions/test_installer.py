"""Tests for extension installer functionality."""
from unittest.mock import patch, MagicMock

from reconly_core.extensions.installer import (
    ExtensionInstaller,
    InstallResult,
    EXTENSION_PACKAGE_PREFIX,
    get_extension_installer,
)


class TestInstallResult:
    """Tests for InstallResult dataclass."""

    def test_to_dict_success(self):
        """Test to_dict for successful result."""
        result = InstallResult(
            success=True,
            package="reconly-ext-test",
            version="1.0.0",
            requires_restart=True,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert d["package"] == "reconly-ext-test"
        assert d["version"] == "1.0.0"
        assert d["error"] is None
        assert d["requires_restart"] is True

    def test_to_dict_failure(self):
        """Test to_dict for failed result."""
        result = InstallResult(
            success=False,
            package="reconly-ext-bad",
            error="Package not found",
            requires_restart=False,
        )
        d = result.to_dict()

        assert d["success"] is False
        assert d["error"] == "Package not found"
        assert d["requires_restart"] is False


class TestExtensionInstaller:
    """Tests for ExtensionInstaller class."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller(pip_timeout=60)

    def test_init_default_timeout(self):
        """Test default pip timeout."""
        installer = ExtensionInstaller()
        assert installer.pip_timeout == 300

    def test_init_custom_timeout(self):
        """Test custom pip timeout."""
        installer = ExtensionInstaller(pip_timeout=120)
        assert installer.pip_timeout == 120


class TestPackageNameValidation:
    """Tests for package name validation."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_valid_package_name(self):
        """Test valid package name passes validation."""
        error = self.installer._validate_package_name("reconly-ext-notion")
        assert error is None

    def test_valid_package_name_with_numbers(self):
        """Test valid package name with numbers."""
        error = self.installer._validate_package_name("reconly-ext-v2test")
        assert error is None

    def test_valid_package_name_with_underscores(self):
        """Test valid package name with underscores."""
        error = self.installer._validate_package_name("reconly-ext-my_extension")
        assert error is None

    def test_empty_package_name(self):
        """Test empty package name fails."""
        error = self.installer._validate_package_name("")
        assert error is not None
        assert "empty" in error.lower()

    def test_missing_prefix(self):
        """Test package without required prefix fails."""
        error = self.installer._validate_package_name("notion-exporter")
        assert error is not None
        assert EXTENSION_PACKAGE_PREFIX in error

    def test_wrong_prefix(self):
        """Test package with wrong prefix fails."""
        error = self.installer._validate_package_name("reconly-notion")
        assert error is not None
        assert EXTENSION_PACKAGE_PREFIX in error

    def test_invalid_characters(self):
        """Test package name with invalid characters fails."""
        error = self.installer._validate_package_name("reconly-ext-test;rm -rf /")
        assert error is not None
        assert "invalid characters" in error.lower()

    def test_special_characters_rejected(self):
        """Test various special characters are rejected."""
        invalid_names = [
            "reconly-ext-test$",
            "reconly-ext-test@",
            "reconly-ext-test!",
            "reconly-ext-test#",
            "reconly-ext-test%",
            "reconly-ext-test&",
            "reconly-ext-test*",
            "reconly-ext-test(",
            "reconly-ext-test)",
        ]
        for name in invalid_names:
            error = self.installer._validate_package_name(name)
            assert error is not None, f"Expected {name} to be invalid"


class TestInstall:
    """Tests for install method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_install_invalid_package_name(self):
        """Test install with invalid package name."""
        result = self.installer.install("invalid-package")

        assert result.success is False
        assert result.package == "invalid-package"
        assert result.error is not None
        assert EXTENSION_PACKAGE_PREFIX in result.error
        assert result.requires_restart is False

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_success(self, mock_run_pip):
        """Test successful installation."""
        mock_run_pip.return_value = (
            0,
            "Successfully installed reconly-ext-test-1.0.0",
            ""
        )

        result = self.installer.install("reconly-ext-test")

        assert result.success is True
        assert result.package == "reconly-ext-test"
        assert result.version == "1.0.0"
        assert result.requires_restart is True
        mock_run_pip.assert_called_once_with(["install", "reconly-ext-test"])

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_with_upgrade(self, mock_run_pip):
        """Test installation with upgrade flag."""
        mock_run_pip.return_value = (
            0,
            "Successfully installed reconly-ext-test-2.0.0",
            ""
        )

        result = self.installer.install("reconly-ext-test", upgrade=True)

        assert result.success is True
        mock_run_pip.assert_called_once_with(
            ["install", "--upgrade", "reconly-ext-test"]
        )

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_failure_not_found(self, mock_run_pip):
        """Test installation failure when package not found."""
        mock_run_pip.return_value = (
            1,
            "",
            "Could not find a version that satisfies the requirement"
        )

        result = self.installer.install("reconly-ext-nonexistent")

        assert result.success is False
        assert result.package == "reconly-ext-nonexistent"
        assert "not found" in result.error.lower()
        assert result.requires_restart is False

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_failure_no_matching(self, mock_run_pip):
        """Test installation failure with no matching distribution."""
        mock_run_pip.return_value = (
            1,
            "",
            "No matching distribution found"
        )

        result = self.installer.install("reconly-ext-incompatible")

        assert result.success is False
        assert "not found or incompatible" in result.error.lower()

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_timeout(self, mock_run_pip):
        """Test installation timeout handling."""
        mock_run_pip.return_value = (
            -1,
            "",
            "pip command timed out after 300 seconds"
        )

        result = self.installer.install("reconly-ext-slow")

        assert result.success is False
        assert "timed out" in result.error.lower()


class TestUninstall:
    """Tests for uninstall method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_uninstall_invalid_package_name(self):
        """Test uninstall with invalid package name."""
        result = self.installer.uninstall("invalid-package")

        assert result.success is False
        assert EXTENSION_PACKAGE_PREFIX in result.error

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_uninstall_success(self, mock_run_pip):
        """Test successful uninstallation."""
        mock_run_pip.return_value = (
            0,
            "Successfully uninstalled reconly-ext-test-1.0.0",
            ""
        )

        result = self.installer.uninstall("reconly-ext-test")

        assert result.success is True
        assert result.package == "reconly-ext-test"
        assert result.requires_restart is True
        mock_run_pip.assert_called_once_with(
            ["uninstall", "-y", "reconly-ext-test"]
        )

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_uninstall_not_installed(self, mock_run_pip):
        """Test uninstall when package not installed."""
        mock_run_pip.return_value = (
            1,
            "WARNING: Skipping reconly-ext-test as it is not installed",
            ""
        )

        result = self.installer.uninstall("reconly-ext-test")

        assert result.success is False
        assert "not installed" in result.error.lower()


class TestIsInstalled:
    """Tests for is_installed method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_is_installed_true(self, mock_run_pip):
        """Test is_installed returns True for installed package."""
        mock_run_pip.return_value = (0, "Name: reconly-ext-test\nVersion: 1.0.0", "")

        assert self.installer.is_installed("reconly-ext-test") is True
        mock_run_pip.assert_called_once_with(["show", "reconly-ext-test"])

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_is_installed_false(self, mock_run_pip):
        """Test is_installed returns False for non-installed package."""
        mock_run_pip.return_value = (1, "", "Package not found")

        assert self.installer.is_installed("reconly-ext-missing") is False


class TestGetInstalledVersion:
    """Tests for get_installed_version method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_get_version_success(self, mock_run_pip):
        """Test getting version of installed package."""
        mock_run_pip.return_value = (
            0,
            "Name: reconly-ext-test\nVersion: 1.2.3\nSummary: Test",
            ""
        )

        version = self.installer.get_installed_version("reconly-ext-test")

        assert version == "1.2.3"

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_get_version_not_installed(self, mock_run_pip):
        """Test getting version of non-installed package."""
        mock_run_pip.return_value = (1, "", "Package not found")

        version = self.installer.get_installed_version("reconly-ext-missing")

        assert version is None

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_get_version_no_version_line(self, mock_run_pip):
        """Test getting version when Version line is missing."""
        mock_run_pip.return_value = (0, "Name: reconly-ext-test\nSummary: Test", "")

        version = self.installer.get_installed_version("reconly-ext-test")

        assert version is None


class TestExtractInstalledVersion:
    """Tests for _extract_installed_version method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_extract_single_package(self):
        """Test extracting version from single package install output."""
        stdout = "Successfully installed reconly-ext-test-1.0.0"
        version = self.installer._extract_installed_version(stdout, "reconly-ext-test")
        assert version == "1.0.0"

    def test_extract_multiple_packages(self):
        """Test extracting version when multiple packages installed."""
        stdout = "Successfully installed dep1-0.1 reconly-ext-test-2.0.0 dep2-0.2"
        version = self.installer._extract_installed_version(stdout, "reconly-ext-test")
        assert version == "2.0.0"

    def test_extract_no_success_line(self):
        """Test extracting version when no success line."""
        stdout = "Requirement already satisfied: reconly-ext-test"
        version = self.installer._extract_installed_version(stdout, "reconly-ext-test")
        assert version is None

    def test_extract_different_package(self):
        """Test extracting version for different package returns None."""
        stdout = "Successfully installed other-package-1.0.0"
        version = self.installer._extract_installed_version(stdout, "reconly-ext-test")
        assert version is None


class TestRunPip:
    """Tests for _run_pip method."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller(pip_timeout=5)

    @patch('reconly_core.extensions.installer.subprocess.run')
    def test_run_pip_success(self, mock_subprocess):
        """Test successful pip command execution."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="output",
            stderr=""
        )

        returncode, stdout, stderr = self.installer._run_pip(["show", "test"])

        assert returncode == 0
        assert stdout == "output"
        assert stderr == ""

    @patch('reconly_core.extensions.installer.subprocess.run')
    def test_run_pip_timeout(self, mock_subprocess):
        """Test pip command timeout."""
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="pip", timeout=5)

        returncode, stdout, stderr = self.installer._run_pip(["install", "slow-pkg"])

        assert returncode == -1
        assert "timed out" in stderr.lower()

    @patch('reconly_core.extensions.installer.subprocess.run')
    def test_run_pip_exception(self, mock_subprocess):
        """Test pip command exception handling."""
        mock_subprocess.side_effect = Exception("Unexpected error")

        returncode, stdout, stderr = self.installer._run_pip(["install", "test"])

        assert returncode == -1
        assert "Unexpected error" in stderr


class TestSingleton:
    """Tests for module-level singleton."""

    def test_get_extension_installer_returns_installer(self):
        """Test get_extension_installer returns ExtensionInstaller."""
        installer = get_extension_installer()
        assert isinstance(installer, ExtensionInstaller)

    def test_get_extension_installer_singleton(self):
        """Test get_extension_installer returns same instance."""
        installer1 = get_extension_installer()
        installer2 = get_extension_installer()
        assert installer1 is installer2


class TestGitHubUrlValidation:
    """Tests for GitHub URL validation."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_valid_github_url_simple(self):
        """Test valid simple GitHub URL passes validation."""
        url = "git+https://github.com/reconlyeu/reconly-ext-reddit.git"
        error = self.installer._validate_github_url(url)
        assert error is None

    def test_valid_github_url_with_subdirectory(self):
        """Test valid GitHub URL with subdirectory passes validation."""
        url = "git+https://github.com/reconlyeu/reconly-extensions.git#subdirectory=extensions/reconly-ext-reddit"
        error = self.installer._validate_github_url(url)
        assert error is None

    def test_valid_github_url_with_version(self):
        """Test valid GitHub URL with version tag passes validation."""
        url = "git+https://github.com/reconlyeu/reconly-ext-reddit.git@v1.0.0"
        error = self.installer._validate_github_url(url)
        assert error is None

    def test_invalid_github_url_wrong_host(self):
        """Test non-GitHub URL fails validation."""
        url = "git+https://gitlab.com/user/reconly-ext-test.git"
        error = self.installer._validate_github_url(url)
        assert error is not None
        assert "github" in error.lower()

    def test_invalid_github_url_missing_ext_prefix(self):
        """Test GitHub URL without reconly-ext- fails validation."""
        url = "git+https://github.com/user/some-other-package.git"
        error = self.installer._validate_github_url(url)
        assert error is not None
        assert EXTENSION_PACKAGE_PREFIX in error

    def test_invalid_github_url_malformed(self):
        """Test malformed GitHub URL fails validation."""
        url = "git+https://github.com/invalid-url"
        error = self.installer._validate_github_url(url)
        assert error is not None
        # Malformed URLs fail either for missing reconly-ext- or invalid format
        assert "reconly-ext" in error.lower() or "invalid" in error.lower()

    def test_invalid_github_url_http_not_https(self):
        """Test HTTP (not HTTPS) URL fails validation."""
        url = "git+http://github.com/user/reconly-ext-test.git"
        error = self.installer._validate_github_url(url)
        assert error is not None


class TestInstallTargetValidation:
    """Tests for install target validation (package name or GitHub URL)."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_validate_package_name(self):
        """Test validation routes package names correctly."""
        error = self.installer._validate_install_target("reconly-ext-test")
        assert error is None

    def test_validate_github_url(self):
        """Test validation routes GitHub URLs correctly."""
        url = "git+https://github.com/reconlyeu/reconly-ext-test.git"
        error = self.installer._validate_install_target(url)
        assert error is None

    def test_validate_empty_target(self):
        """Test empty target fails validation."""
        error = self.installer._validate_install_target("")
        assert error is not None
        assert "empty" in error.lower()

    def test_validate_invalid_package_name(self):
        """Test invalid package name fails."""
        error = self.installer._validate_install_target("invalid-package")
        assert error is not None

    def test_validate_invalid_github_url(self):
        """Test invalid GitHub URL fails."""
        error = self.installer._validate_install_target("git+https://github.com/invalid")
        assert error is not None


class TestExtractPackageNameFromUrl:
    """Tests for extracting package name from GitHub URL."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_extract_from_simple_repo(self):
        """Test extracting package name from simple repo URL."""
        url = "git+https://github.com/user/reconly-ext-reddit.git"
        name = self.installer._extract_package_name_from_url(url)
        assert name == "reconly-ext-reddit"

    def test_extract_from_subdirectory(self):
        """Test extracting package name from subdirectory URL."""
        url = "git+https://github.com/user/repo.git#subdirectory=extensions/reconly-ext-notion"
        name = self.installer._extract_package_name_from_url(url)
        assert name == "reconly-ext-notion"

    def test_extract_from_nested_subdirectory(self):
        """Test extracting package name from nested subdirectory."""
        url = "git+https://github.com/user/repo.git#subdirectory=packages/extensions/reconly-ext-test"
        name = self.installer._extract_package_name_from_url(url)
        assert name == "reconly-ext-test"

    def test_extract_with_version_tag(self):
        """Test extracting package name when URL has version tag."""
        url = "git+https://github.com/user/reconly-ext-test.git@v1.0.0"
        name = self.installer._extract_package_name_from_url(url)
        assert name == "reconly-ext-test"


class TestInstallFromGitHub:
    """Tests for installing from GitHub URLs."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_install_invalid_github_url(self):
        """Test install with invalid GitHub URL."""
        result = self.installer.install("git+https://github.com/invalid-url")

        assert result.success is False
        assert result.error is not None

    def test_install_github_url_missing_ext_prefix(self):
        """Test install with GitHub URL missing reconly-ext- prefix."""
        result = self.installer.install("git+https://github.com/user/other-package.git")

        assert result.success is False
        assert EXTENSION_PACKAGE_PREFIX in result.error

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_github_url_success(self, mock_run_pip):
        """Test successful installation from GitHub URL."""
        mock_run_pip.return_value = (
            0,
            "Successfully installed reconly-ext-reddit-0.3.0",
            ""
        )

        url = "git+https://github.com/reconlyeu/reconly-ext-reddit.git"
        result = self.installer.install(url)

        assert result.success is True
        assert result.package == "reconly-ext-reddit"
        assert result.version == "0.3.0"
        assert result.requires_restart is True
        mock_run_pip.assert_called_once_with(["install", url])

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_github_url_with_subdirectory(self, mock_run_pip):
        """Test installation from GitHub URL with subdirectory."""
        mock_run_pip.return_value = (
            0,
            "Successfully installed reconly-ext-notion-1.0.0",
            ""
        )

        url = "git+https://github.com/reconlyeu/reconly-extensions.git#subdirectory=extensions/reconly-ext-notion"
        result = self.installer.install(url)

        assert result.success is True
        assert result.package == "reconly-ext-notion"
        assert result.version == "1.0.0"
        mock_run_pip.assert_called_once_with(["install", url])

    @patch.object(ExtensionInstaller, '_run_pip')
    def test_install_github_url_with_upgrade(self, mock_run_pip):
        """Test upgrade installation from GitHub URL."""
        mock_run_pip.return_value = (
            0,
            "Successfully installed reconly-ext-test-2.0.0",
            ""
        )

        url = "git+https://github.com/user/reconly-ext-test.git"
        result = self.installer.install(url, upgrade=True)

        assert result.success is True
        mock_run_pip.assert_called_once_with(["install", "--upgrade", url])


class TestGitHubErrorFormatting:
    """Tests for GitHub-specific error message formatting."""

    def setup_method(self):
        """Create fresh installer for each test."""
        self.installer = ExtensionInstaller()

    def test_format_clone_failed_error(self):
        """Test formatting of git clone failure error."""
        stderr = "fatal: repository not found"
        error = self.installer._format_github_error(stderr)

        assert "repository" in error.lower()
        assert "private" in error.lower() or "unavailable" in error.lower()

    def test_format_access_denied_error(self):
        """Test formatting of access denied error."""
        stderr = "fatal: unable to access 'https://github.com/...'"
        error = self.installer._format_github_error(stderr)

        assert "download" in error.lower() or "connection" in error.lower()

    def test_format_subdirectory_not_found_error(self):
        """Test formatting of subdirectory not found error."""
        stderr = "does not appear to be a python project"
        error = self.installer._format_github_error(stderr)

        assert "not found" in error.lower() or "subdirectory" in error.lower()

    def test_format_tag_not_found_error(self):
        """Test formatting of tag/branch not found error."""
        stderr = "could not find a tag or branch 'v999.0.0'"
        error = self.installer._format_github_error(stderr)

        assert "version" in error.lower() or "tag" in error.lower() or "branch" in error.lower()

    def test_format_generic_error_passes_through(self):
        """Test that unknown errors pass through."""
        stderr = "Some unexpected error message"
        error = self.installer._format_github_error(stderr)

        assert error == "Some unexpected error message"
