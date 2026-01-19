"""Tests for edition detection and feature flags."""
import pytest
import warnings

from reconly_core.edition import (
    Edition,
    get_edition,
    is_enterprise,
    is_oss,
    features,
    clear_edition_cache,
)


@pytest.fixture(autouse=True)
def reset_edition_cache():
    """Reset edition cache before and after each test."""
    clear_edition_cache()
    yield
    clear_edition_cache()


class TestGetEdition:
    """Tests for get_edition() function."""

    def test_default_is_oss(self, monkeypatch):
        """When RECONLY_EDITION is not set, default to 'oss'."""
        monkeypatch.delenv("RECONLY_EDITION", raising=False)
        clear_edition_cache()

        assert get_edition() == "oss"

    def test_oss_edition(self, monkeypatch):
        """When RECONLY_EDITION=oss, return 'oss'."""
        monkeypatch.setenv("RECONLY_EDITION", "oss")
        clear_edition_cache()

        assert get_edition() == "oss"

    def test_enterprise_edition(self, monkeypatch):
        """When RECONLY_EDITION=enterprise, return 'enterprise'."""
        monkeypatch.setenv("RECONLY_EDITION", "enterprise")
        clear_edition_cache()

        assert get_edition() == "enterprise"

    def test_case_insensitive(self, monkeypatch):
        """Edition value should be case-insensitive."""
        monkeypatch.setenv("RECONLY_EDITION", "ENTERPRISE")
        clear_edition_cache()

        assert get_edition() == "enterprise"

        monkeypatch.setenv("RECONLY_EDITION", "OSS")
        clear_edition_cache()

        assert get_edition() == "oss"

    def test_invalid_value_defaults_to_oss(self, monkeypatch):
        """Invalid edition values should default to 'oss' with a warning."""
        monkeypatch.setenv("RECONLY_EDITION", "invalid")
        clear_edition_cache()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_edition()

            assert result == "oss"
            assert len(w) == 1
            assert "Invalid RECONLY_EDITION" in str(w[0].message)

    def test_caching(self, monkeypatch):
        """get_edition() should cache its result."""
        monkeypatch.setenv("RECONLY_EDITION", "enterprise")
        clear_edition_cache()

        # First call
        result1 = get_edition()
        assert result1 == "enterprise"

        # Change env var (shouldn't affect cached result)
        monkeypatch.setenv("RECONLY_EDITION", "oss")
        result2 = get_edition()
        assert result2 == "enterprise"  # Still cached

        # Clear cache and re-read
        clear_edition_cache()
        result3 = get_edition()
        assert result3 == "oss"


class TestEditionHelpers:
    """Tests for is_enterprise() and is_oss() helpers."""

    def test_is_enterprise_true(self, monkeypatch):
        """is_enterprise() returns True when edition is enterprise."""
        monkeypatch.setenv("RECONLY_EDITION", "enterprise")
        clear_edition_cache()

        assert is_enterprise() is True
        assert is_oss() is False

    def test_is_oss_true(self, monkeypatch):
        """is_oss() returns True when edition is oss."""
        monkeypatch.setenv("RECONLY_EDITION", "oss")
        clear_edition_cache()

        assert is_oss() is True
        assert is_enterprise() is False


class TestFeatures:
    """Tests for feature flags."""

    def test_features_oss(self, monkeypatch):
        """In OSS mode, enterprise features are disabled."""
        monkeypatch.setenv("RECONLY_EDITION", "oss")
        clear_edition_cache()

        assert features.cost_tracking is False
        assert features.cost_display is False
        assert features.billing is False
        assert features.usage_limits is False
        assert features.multi_user is False

    def test_features_enterprise(self, monkeypatch):
        """In Enterprise mode, enterprise features are enabled."""
        monkeypatch.setenv("RECONLY_EDITION", "enterprise")
        clear_edition_cache()

        assert features.cost_tracking is True
        assert features.cost_display is True
        assert features.billing is True
        assert features.usage_limits is True
        assert features.multi_user is True


class TestEditionEnum:
    """Tests for Edition enum."""

    def test_edition_values(self):
        """Edition enum has correct values."""
        assert Edition.OSS.value == "oss"
        assert Edition.ENTERPRISE.value == "enterprise"

    def test_edition_is_string(self):
        """Edition enum values are strings."""
        assert isinstance(Edition.OSS.value, str)
        assert isinstance(Edition.ENTERPRISE.value, str)
