"""Extension installer using pip subprocess.

This module provides functionality to install and uninstall extension
packages using pip. It validates package names and GitHub URLs to ensure
only authorized Reconly extension packages can be installed.

Supported installation sources:
- PyPI package names: reconly-ext-notion
- GitHub URLs: git+https://github.com/user/repo.git
- GitHub subdirectory URLs: git+https://github.com/user/repo.git#subdirectory=path
"""
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Required prefix for extension package names
EXTENSION_PACKAGE_PREFIX = "reconly-ext-"

# GitHub URL prefixes for git-based installations
GITHUB_HTTPS_PREFIX = "git+https://github.com/"
GITHUB_SSH_PREFIX = "git+ssh://git@github.com/"


@dataclass
class InstallResult:
    """Result of an extension installation or uninstallation attempt.

    Attributes:
        success: Whether the operation completed successfully
        package: The package name that was operated on
        version: The installed version (only for install, None for uninstall)
        error: Error message if the operation failed
        requires_restart: Whether a restart is needed for changes to take effect
        stdout: Standard output from pip (for debugging)
        stderr: Standard error from pip (for debugging)
    """
    success: bool
    package: str
    version: Optional[str] = None
    error: Optional[str] = None
    requires_restart: bool = True
    stdout: Optional[str] = None
    stderr: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "package": self.package,
            "version": self.version,
            "error": self.error,
            "requires_restart": self.requires_restart,
        }


class ExtensionInstaller:
    """Installs and uninstalls Reconly extensions via pip.

    This class wraps pip subprocess calls to install and uninstall extension
    packages. Only packages with the 'reconly-ext-' prefix are allowed.

    Usage:
        installer = ExtensionInstaller()
        result = installer.install("reconly-ext-notion")
        if result.success:
            print(f"Installed {result.package} v{result.version}")
        else:
            print(f"Failed: {result.error}")
    """

    def __init__(self, pip_timeout: int = 300):
        """Initialize the installer.

        Args:
            pip_timeout: Timeout in seconds for pip operations (default: 5 minutes)
        """
        self.pip_timeout = pip_timeout

    def _validate_install_target(self, target: str) -> Optional[str]:
        """Validate an install target (package name or GitHub URL).

        Routes to the appropriate validation based on target format.

        Args:
            target: Package name or GitHub URL to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not target:
            return "Install target cannot be empty"

        # GitHub URL (HTTPS or SSH)
        if target.startswith("git+https://") or target.startswith("git+ssh://"):
            return self._validate_github_url(target)

        # Package name (PyPI)
        return self._validate_package_name(target)

    def _validate_github_url(self, url: str) -> Optional[str]:
        """Validate that a GitHub URL is a valid extension source.

        Args:
            url: GitHub URL to validate. Supported formats:
                - git+https://github.com/user/repo.git
                - git+ssh://git@github.com/user/repo.git

        Returns:
            Error message if invalid, None if valid
        """
        # Must be GitHub URL (HTTPS or SSH)
        is_https = url.startswith(GITHUB_HTTPS_PREFIX)
        is_ssh = url.startswith(GITHUB_SSH_PREFIX)
        if not is_https and not is_ssh:
            return (
                "Only GitHub URLs are supported. URL must start with "
                "'git+https://github.com/' or 'git+ssh://git@github.com/'"
            )

        # Must reference reconly-ext-* package (security check)
        if EXTENSION_PACKAGE_PREFIX not in url:
            return (
                f"GitHub URL must reference a '{EXTENSION_PACKAGE_PREFIX}*' package. "
                f"The URL should contain '{EXTENSION_PACKAGE_PREFIX}' in the repository name or subdirectory."
            )

        # Basic URL structure validation
        # Pattern: git+https://github.com/user/repo.git or git+ssh://git@github.com/user/repo.git
        if is_https:
            url_pattern = r"^git\+https://github\.com/[\w\-\.]+/[\w\-\.]+\.git"
        else:
            url_pattern = r"^git\+ssh://git@github\.com/[\w\-\.]+/[\w\-\.]+\.git"

        if not re.match(url_pattern, url):
            return (
                "Invalid GitHub URL format. Expected: "
                "git+https://github.com/user/repo.git or "
                "git+ssh://git@github.com/user/repo.git"
            )

        # Validate subdirectory fragment if present
        if "#" in url:
            fragment = url.split("#", 1)[1]
            # Fragment should be subdirectory=path or @version (or both)
            if fragment and not fragment.startswith("subdirectory=") and "@" not in url:
                return (
                    "Invalid URL fragment. Use '#subdirectory=path' for monorepo installations."
                )

        return None

    def _validate_package_name(self, package_name: str) -> Optional[str]:
        """Validate that a package name is a valid Reconly extension.

        Args:
            package_name: Package name to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not package_name:
            return "Package name cannot be empty"

        if not package_name.startswith(EXTENSION_PACKAGE_PREFIX):
            return (
                f"Invalid extension package name '{package_name}'. "
                f"Extension packages must start with '{EXTENSION_PACKAGE_PREFIX}'"
            )

        # Check for suspicious characters that could be used for injection
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
        if not set(package_name.lower()).issubset(allowed_chars):
            return f"Package name contains invalid characters: {package_name}"

        return None

    def _run_pip(self, args: list[str]) -> tuple[int, str, str]:
        """Run a pip command as a subprocess.

        Args:
            args: Arguments to pass to pip (excluding 'pip' itself)

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = [sys.executable, "-m", "pip"] + args
        logger.debug(f"Running pip command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.pip_timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"pip command timed out after {self.pip_timeout} seconds"
        except Exception as e:
            return -1, "", str(e)

    def _extract_installed_version(self, stdout: str, package_name: str) -> Optional[str]:
        """Extract the installed version from pip output.

        Args:
            stdout: Standard output from pip install
            package_name: Name of the package that was installed

        Returns:
            Version string if found, None otherwise
        """
        # Look for "Successfully installed package-name-X.Y.Z" pattern
        for line in stdout.split("\n"):
            if "Successfully installed" in line:
                # Parse "Successfully installed pkg1-1.0 pkg2-2.0" format
                parts = line.replace("Successfully installed", "").strip().split()
                for part in parts:
                    if part.startswith(package_name):
                        # Extract version after package name
                        version_part = part[len(package_name):]
                        if version_part.startswith("-"):
                            return version_part[1:]
        return None

    def _is_github_url(self, target: str) -> bool:
        """Check if target is a GitHub URL (HTTPS or SSH)."""
        return target.startswith("git+https://") or target.startswith("git+ssh://")

    def _extract_package_name_from_url(self, url: str) -> str:
        """Extract package name from GitHub URL for result reporting.

        Args:
            url: GitHub URL (git+https://github.com/user/repo.git#subdirectory=path)

        Returns:
            Package name extracted from URL, or the URL itself if extraction fails
        """
        # Try to extract from subdirectory first (monorepo pattern)
        if "#subdirectory=" in url:
            # git+https://github.com/user/repo.git#subdirectory=extensions/reconly-ext-reddit
            subdir = url.split("#subdirectory=")[1].split("@")[0]  # Remove version if present
            # Get the last part of the path which should be the package name
            parts = subdir.rstrip("/").split("/")
            for part in reversed(parts):
                if part.startswith(EXTENSION_PACKAGE_PREFIX):
                    return part
            return parts[-1] if parts else url

        # Try to extract from repository name
        # git+https://github.com/user/reconly-ext-reddit.git
        match = re.search(r"/([^/]+)\.git", url)
        if match:
            return match.group(1)

        return url

    def _format_github_error(self, stderr: str) -> str:
        """Format GitHub-specific error messages into user-friendly text.

        Args:
            stderr: Standard error from pip

        Returns:
            User-friendly error message
        """
        if not stderr:
            return "Installation failed"

        error_lower = stderr.lower()

        # Map error patterns to user-friendly messages
        # Each tuple: (patterns_list, message, match_mode)
        # match_mode: "any" = OR logic, "all" = AND logic (default)
        error_mappings = [
            # Git clone / repository access failures (any pattern matches)
            (["git clone", "repository not found"],
             "Failed to download extension. Repository may be private or unavailable.",
             "any"),
            (["fatal: unable to access"],
             "Failed to download extension. Check your internet connection or repository URL.",
             "any"),
            (["permission denied"],
             "Failed to download extension. Repository may be private.",
             "any"),
            # Subdirectory issues
            (["does not appear to be a python project"],
             "Extension not found in repository. The subdirectory may be incorrect.",
             "any"),
            (["subdirectory", "not exist"],
             "Extension not found in repository. The specified subdirectory does not exist.",
             "all"),
            # Version/tag issues
            (["could not find a tag or branch"],
             "Specified version not found. Check the tag or branch name.",
             "any"),
            (["could not find a version"],
             "Extension package not found or has no valid version.",
             "any"),
            (["no matching distribution"],
             "Extension not found or incompatible with your Python version.",
             "any"),
        ]

        for patterns, message, match_mode in error_mappings:
            matcher = any if match_mode == "any" else all
            if matcher(pattern in error_lower for pattern in patterns):
                return message

        return stderr.strip()

    def install(self, target: str, upgrade: bool = False) -> InstallResult:
        """Install an extension package using pip.

        Supports both PyPI package names and GitHub URLs.

        Args:
            target: Package name (reconly-ext-*) or GitHub URL (git+https://github.com/...)
            upgrade: If True, upgrade the package if already installed

        Returns:
            InstallResult with success status and details

        Examples:
            # Install from PyPI
            installer.install("reconly-ext-notion")

            # Install from GitHub
            installer.install("git+https://github.com/reconlyeu/reconly-ext-notion.git")

            # Install from GitHub monorepo subdirectory
            installer.install("git+https://github.com/reconlyeu/reconly-extensions.git#subdirectory=extensions/reconly-ext-reddit")
        """
        is_github = self._is_github_url(target)

        # Validate install target
        error = self._validate_install_target(target)
        if error:
            return InstallResult(
                success=False,
                package=target,
                error=error,
                requires_restart=False,
            )

        # Extract package name for logging and results
        if is_github:
            package_name = self._extract_package_name_from_url(target)
        else:
            package_name = target

        # Build pip install command
        args = ["install"]
        if upgrade:
            args.append("--upgrade")
        args.append(target)

        logger.info(f"Installing extension: {package_name}" + (f" from {target}" if is_github else ""))

        # Run pip install
        returncode, stdout, stderr = self._run_pip(args)

        if returncode == 0:
            version = self._extract_installed_version(stdout, package_name)
            logger.info(f"Successfully installed {package_name}" +
                       (f" v{version}" if version else ""))
            return InstallResult(
                success=True,
                package=package_name,
                version=version,
                requires_restart=True,
                stdout=stdout,
                stderr=stderr,
            )
        else:
            # Format error message based on source type
            if is_github:
                error_msg = self._format_github_error(stderr)
            else:
                error_msg = stderr.strip() if stderr else "Installation failed"
                # Simplify common PyPI error messages
                if "Could not find a version" in error_msg:
                    error_msg = f"Package '{package_name}' not found on PyPI"
                elif "No matching distribution" in error_msg:
                    error_msg = f"Package '{package_name}' not found or incompatible"

            logger.error(f"Failed to install {package_name}: {error_msg}")
            return InstallResult(
                success=False,
                package=package_name,
                error=error_msg,
                requires_restart=False,
                stdout=stdout,
                stderr=stderr,
            )

    def uninstall(self, package_name: str) -> InstallResult:
        """Uninstall an extension package using pip.

        Args:
            package_name: Name of the package to uninstall

        Returns:
            InstallResult with success status and details
        """
        # Validate package name
        error = self._validate_package_name(package_name)
        if error:
            return InstallResult(
                success=False,
                package=package_name,
                error=error,
                requires_restart=False,
            )

        logger.info(f"Uninstalling extension package: {package_name}")

        # Run pip uninstall with -y to skip confirmation
        returncode, stdout, stderr = self._run_pip(["uninstall", "-y", package_name])

        if returncode == 0:
            logger.info(f"Successfully uninstalled {package_name}")
            return InstallResult(
                success=True,
                package=package_name,
                requires_restart=True,
                stdout=stdout,
                stderr=stderr,
            )
        else:
            error_msg = stderr.strip() if stderr else "Uninstallation failed"
            # Check if package wasn't installed
            if "not installed" in error_msg.lower() or "not installed" in stdout.lower():
                error_msg = f"Package '{package_name}' is not installed"

            logger.error(f"Failed to uninstall {package_name}: {error_msg}")
            return InstallResult(
                success=False,
                package=package_name,
                error=error_msg,
                requires_restart=False,
                stdout=stdout,
                stderr=stderr,
            )

    def is_installed(self, package_name: str) -> bool:
        """Check if a package is installed.

        Args:
            package_name: Name of the package to check

        Returns:
            True if installed, False otherwise
        """
        returncode, _, _ = self._run_pip(["show", package_name])
        return returncode == 0

    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package.

        Args:
            package_name: Name of the package

        Returns:
            Version string if installed, None otherwise
        """
        returncode, stdout, _ = self._run_pip(["show", package_name])
        if returncode != 0:
            return None

        for line in stdout.split("\n"):
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
        return None


# Module-level singleton for convenience
_installer: Optional[ExtensionInstaller] = None


def get_extension_installer() -> ExtensionInstaller:
    """Get the global extension installer singleton.

    Returns:
        ExtensionInstaller instance
    """
    global _installer
    if _installer is None:
        _installer = ExtensionInstaller()
    return _installer
