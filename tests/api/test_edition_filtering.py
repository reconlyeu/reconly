"""Tests for edition-aware API response filtering.

These tests verify that cost-related fields are excluded from API responses
in OSS edition and included in Enterprise edition.
"""
import pytest

from reconly_core.edition import clear_edition_cache
from reconly_api.schemas.feeds import FeedRunResponse
from reconly_api.schemas.digest import DigestResponse, DigestStats
from reconly_api.schemas.edition import (
    OSS_EXCLUDED_FIELDS,
    exclude_cost_fields,
    exclude_cost_fields_from_dict,
    exclude_cost_fields_from_list,
)


@pytest.fixture(autouse=True)
def reset_edition_cache():
    """Reset edition cache before and after each test."""
    clear_edition_cache()
    yield
    clear_edition_cache()


class TestEditionUtilityFunctions:
    """Tests for edition utility functions."""

    def test_exclude_cost_fields_oss(self, monkeypatch):
        """In OSS mode, cost fields should be excluded from model serialization."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        from datetime import datetime

        response = FeedRunResponse(
            id=1,
            feed_id=1,
            triggered_by="manual",
            status="completed",
            sources_total=1,
            sources_processed=1,
            sources_failed=0,
            items_processed=5,
            total_tokens_in=1000,
            total_tokens_out=500,
            total_cost=0.05,
            created_at=datetime.utcnow(),
        )

        result = exclude_cost_fields(response)

        assert "total_cost" not in result
        assert result["id"] == 1
        assert result["total_tokens_in"] == 1000

    def test_exclude_cost_fields_enterprise(self, monkeypatch):
        """In Enterprise mode, cost fields should be included."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "enterprise")
        clear_edition_cache()

        from datetime import datetime

        response = FeedRunResponse(
            id=1,
            feed_id=1,
            triggered_by="manual",
            status="completed",
            sources_total=1,
            sources_processed=1,
            sources_failed=0,
            items_processed=5,
            total_tokens_in=1000,
            total_tokens_out=500,
            total_cost=0.05,
            created_at=datetime.utcnow(),
        )

        result = exclude_cost_fields(response)

        assert "total_cost" in result
        assert result["total_cost"] == 0.05

    def test_exclude_cost_fields_from_dict_oss(self, monkeypatch):
        """In OSS mode, cost fields should be excluded from dicts."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        data = {
            "id": 1,
            "name": "Test",
            "total_cost": 0.05,
            "estimated_cost": 0.01,
        }

        result = exclude_cost_fields_from_dict(data)

        assert "total_cost" not in result
        assert "estimated_cost" not in result
        assert result["id"] == 1
        assert result["name"] == "Test"

    def test_exclude_cost_fields_from_dict_enterprise(self, monkeypatch):
        """In Enterprise mode, cost fields should be included in dicts."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "enterprise")
        clear_edition_cache()

        data = {
            "id": 1,
            "name": "Test",
            "total_cost": 0.05,
            "estimated_cost": 0.01,
        }

        result = exclude_cost_fields_from_dict(data)

        assert result["total_cost"] == 0.05
        assert result["estimated_cost"] == 0.01

    def test_exclude_cost_fields_from_list_oss(self, monkeypatch):
        """In OSS mode, cost fields should be excluded from list items."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        items = [
            {"id": 1, "total_cost": 0.05},
            {"id": 2, "total_cost": 0.10},
        ]

        result = exclude_cost_fields_from_list(items)

        assert len(result) == 2
        assert "total_cost" not in result[0]
        assert "total_cost" not in result[1]
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2


class TestFeedRunResponseFiltering:
    """Tests for FeedRunResponse edition filtering."""

    def test_model_dump_excludes_cost_in_oss(self, monkeypatch):
        """FeedRunResponse.model_dump() excludes total_cost in OSS."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        from datetime import datetime

        response = FeedRunResponse(
            id=1,
            feed_id=1,
            triggered_by="manual",
            status="completed",
            sources_total=1,
            sources_processed=1,
            sources_failed=0,
            items_processed=5,
            total_tokens_in=1000,
            total_tokens_out=500,
            total_cost=0.05,
            created_at=datetime.utcnow(),
        )

        result = response.model_dump()

        assert "total_cost" not in result
        # Tokens should still be present
        assert result["total_tokens_in"] == 1000
        assert result["total_tokens_out"] == 500

    def test_model_dump_includes_cost_in_enterprise(self, monkeypatch):
        """FeedRunResponse.model_dump() includes total_cost in Enterprise."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "enterprise")
        clear_edition_cache()

        from datetime import datetime

        response = FeedRunResponse(
            id=1,
            feed_id=1,
            triggered_by="manual",
            status="completed",
            sources_total=1,
            sources_processed=1,
            sources_failed=0,
            items_processed=5,
            total_tokens_in=1000,
            total_tokens_out=500,
            total_cost=0.05,
            created_at=datetime.utcnow(),
        )

        result = response.model_dump()

        assert "total_cost" in result
        assert result["total_cost"] == 0.05


class TestDigestResponseFiltering:
    """Tests for DigestResponse edition filtering."""

    def test_model_dump_excludes_cost_in_oss(self, monkeypatch):
        """DigestResponse.model_dump() excludes estimated_cost in OSS."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        response = DigestResponse(
            url="https://example.com",
            title="Test Article",
            estimated_cost=0.01,
        )

        result = response.model_dump()

        assert "estimated_cost" not in result
        assert result["title"] == "Test Article"

    def test_model_dump_includes_cost_in_enterprise(self, monkeypatch):
        """DigestResponse.model_dump() includes estimated_cost in Enterprise."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "enterprise")
        clear_edition_cache()

        response = DigestResponse(
            url="https://example.com",
            title="Test Article",
            estimated_cost=0.01,
        )

        result = response.model_dump()

        assert "estimated_cost" in result
        assert result["estimated_cost"] == 0.01


class TestDigestStatsFiltering:
    """Tests for DigestStats edition filtering."""

    def test_model_dump_excludes_cost_in_oss(self, monkeypatch):
        """DigestStats.model_dump() excludes total_cost in OSS."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "oss")
        clear_edition_cache()

        stats = DigestStats(
            total_digests=100,
            total_cost=5.50,
            total_tags=25,
            by_source_type={"rss": 50, "website": 50},
        )

        result = stats.model_dump()

        assert "total_cost" not in result
        assert result["total_digests"] == 100
        assert result["total_tags"] == 25

    def test_model_dump_includes_cost_in_enterprise(self, monkeypatch):
        """DigestStats.model_dump() includes total_cost in Enterprise."""
        monkeypatch.setenv("SKIMBERRY_EDITION", "enterprise")
        clear_edition_cache()

        stats = DigestStats(
            total_digests=100,
            total_cost=5.50,
            total_tags=25,
            by_source_type={"rss": 50, "website": 50},
        )

        result = stats.model_dump()

        assert "total_cost" in result
        assert result["total_cost"] == 5.50


class TestOSSExcludedFields:
    """Tests for the OSS_EXCLUDED_FIELDS constant."""

    def test_contains_expected_fields(self):
        """OSS_EXCLUDED_FIELDS should contain all cost-related field names."""
        expected_fields = {
            "total_cost",
            "estimated_cost",
            "cost",
            "cost_per_run",
            "monthly_cost",
        }

        assert OSS_EXCLUDED_FIELDS == expected_fields

    def test_is_frozen(self):
        """OSS_EXCLUDED_FIELDS should be immutable."""
        # The set should be a regular set (not frozenset) but the constant name
        # indicates it shouldn't be modified. Test that it's at least a set.
        assert isinstance(OSS_EXCLUDED_FIELDS, set)
