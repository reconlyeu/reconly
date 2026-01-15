"""Edition-aware test fixtures for OSS/Enterprise testing."""
import pytest

from reconly_core.edition import clear_edition_cache


def _set_edition(monkeypatch, edition_value: str) -> str:
    """Set edition environment variable and clear cache."""
    monkeypatch.setenv("RECONLY_EDITION", edition_value)
    clear_edition_cache()
    return edition_value


@pytest.fixture(params=["oss", "enterprise"])
def edition(request, monkeypatch):
    """Run test in both OSS and Enterprise editions."""
    yield _set_edition(monkeypatch, request.param)
    clear_edition_cache()


@pytest.fixture
def oss_edition(monkeypatch):
    """Force OSS edition for the test."""
    yield _set_edition(monkeypatch, "oss")
    clear_edition_cache()


@pytest.fixture
def enterprise_edition(monkeypatch):
    """Force Enterprise edition for the test."""
    yield _set_edition(monkeypatch, "enterprise")
    clear_edition_cache()


@pytest.fixture
def reset_edition_after_test():
    """Reset edition cache after test (for manual edition manipulation)."""
    yield
    clear_edition_cache()
