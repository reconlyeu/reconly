"""Edition detection and feature flags for Reconly.

This module provides a centralized way to detect the current edition
(OSS or Enterprise) and check for edition-specific features.
"""
import os

__all__ = [
    "Edition",
    "get_edition",
    "is_enterprise",
    "is_oss",
    "is_demo_mode",
    "clear_edition_cache",
    "Features",
    "features",
]
import warnings
from enum import Enum
from functools import lru_cache


class Edition(str, Enum):
    """Reconly edition types."""
    OSS = "oss"
    ENTERPRISE = "enterprise"


@lru_cache(maxsize=1)
def get_edition() -> str:
    """
    Get the current Reconly edition.

    Reads from RECONLY_EDITION environment variable.
    Defaults to 'oss' if not set or invalid.

    Returns:
        'oss' or 'enterprise'
    """
    edition = os.getenv("RECONLY_EDITION", "oss").lower()

    if edition not in ("oss", "enterprise"):
        warnings.warn(
            f"Invalid RECONLY_EDITION '{edition}', defaulting to 'oss'"
        )
        return "oss"

    return edition


def is_enterprise() -> bool:
    """Check if running in enterprise mode."""
    return get_edition() == "enterprise"


def is_oss() -> bool:
    """Check if running in OSS mode."""
    return get_edition() == "oss"


def is_demo_mode() -> bool:
    """Check if running in demo mode.

    Demo mode is enabled when RECONLY_DEMO_MODE is set to "true", "1", or "yes"
    (case-insensitive).

    Returns:
        True if demo mode is enabled, False otherwise.
    """
    demo_value = os.getenv("RECONLY_DEMO_MODE", "").lower()
    return demo_value in ("true", "1", "yes")


def clear_edition_cache() -> None:
    """
    Clear the cached edition value.

    Useful for testing when you need to change the edition mid-test.
    """
    get_edition.cache_clear()


class Features:
    """
    Feature flags based on edition.

    Usage:
        >>> from reconly_core.edition import features
        >>> if features.cost_tracking:
        >>>     calculate_cost()
    """

    @property
    def cost_tracking(self) -> bool:
        """Whether cost tracking/estimation is enabled (Enterprise only)."""
        return is_enterprise()

    @property
    def cost_display(self) -> bool:
        """Whether cost display in UI/API responses is enabled (Enterprise only)."""
        return is_enterprise()

    @property
    def billing(self) -> bool:
        """Whether billing features are enabled (Enterprise only)."""
        return is_enterprise()

    @property
    def usage_limits(self) -> bool:
        """Whether usage limits are enforced (Enterprise only)."""
        return is_enterprise()

    @property
    def multi_user(self) -> bool:
        """Whether multi-user features are enabled (Enterprise only)."""
        return is_enterprise()


# Global features instance
features = Features()
