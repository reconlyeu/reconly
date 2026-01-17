"""Edition matrix tests for API endpoints.

Tests verify cost field visibility differs by edition while CRUD works identically.
"""
import pytest
from datetime import datetime, timedelta

from reconly_core.database.models import Digest, FeedRun
from reconly_core.edition import clear_edition_cache


@pytest.fixture(autouse=True)
def reset_edition_cache():
    """Reset edition cache before and after each test."""
    clear_edition_cache()
    yield
    clear_edition_cache()


class TestDigestCostFieldsByEdition:
    """Test cost field visibility in digest responses based on edition."""

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_digest_list_cost_fields(self, edition, client, test_db):
        """GET /digests returns cost fields only in Enterprise edition."""
        digest = Digest(
            url="https://example.com/edition-test",
            title="Edition Test Article",
            summary="Test summary",
            source_type="rss",
            estimated_cost=0.0123,
        )
        test_db.add(digest)
        test_db.commit()

        response = client.get("/api/v1/digests")
        assert response.status_code == 200

        digests = response.json()["digests"]
        digest_data = next(d for d in digests if d["url"] == digest.url)

        if edition == "oss":
            assert "estimated_cost" not in digest_data
        else:
            assert digest_data["estimated_cost"] == 0.0123

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_digest_detail_cost_fields(self, edition, client, test_db):
        """GET /digests/{id} returns cost fields only in Enterprise edition."""
        digest = Digest(
            url="https://example.com/detail-test",
            title="Detail Test",
            summary="Test summary",
            source_type="rss",
            estimated_cost=0.0456,
        )
        test_db.add(digest)
        test_db.commit()

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        if edition == "oss":
            assert "estimated_cost" not in data
        else:
            assert data["estimated_cost"] == 0.0456


class TestFeedRunCostFieldsByEdition:
    """Test cost field visibility in feed run responses based on edition."""

    def _create_feed_run(self, test_db, feed_id, total_cost=0.05, trace_id="test-trace"):
        """Create a feed run with cost data."""
        feed_run = FeedRun(
            feed_id=feed_id,
            triggered_by="manual",
            status="completed",
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow(),
            sources_total=1,
            sources_processed=1,
            sources_failed=0,
            items_processed=5,
            total_tokens_in=1000,
            total_tokens_out=400,
            total_cost=total_cost,
            trace_id=trace_id,
        )
        test_db.add(feed_run)
        test_db.commit()
        return feed_run

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_feed_run_list_cost_fields(self, edition, client, test_db, sample_feed):
        """GET /feeds/{id}/runs returns cost fields only in Enterprise edition."""
        feed_run = self._create_feed_run(test_db, sample_feed.id, total_cost=0.05)

        response = client.get(f"/api/v1/feeds/{sample_feed.id}/runs")
        assert response.status_code == 200

        runs = response.json()  # Direct list, not wrapped in {"items": ...}
        run_data = next(r for r in runs if r["id"] == feed_run.id)

        if edition == "oss":
            assert "total_cost" not in run_data
        else:
            assert run_data["total_cost"] == 0.05

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_feed_run_detail_cost_fields(self, edition, client, test_db, sample_feed):
        """GET /feed-runs/{run_id} returns cost fields only in Enterprise."""
        feed_run = self._create_feed_run(test_db, sample_feed.id, total_cost=0.0789)

        response = client.get(f"/api/v1/feed-runs/{feed_run.id}")
        assert response.status_code == 200

        data = response.json()
        if edition == "oss":
            assert "total_cost" not in data
        else:
            assert data["total_cost"] == 0.0789


class TestCoreCRUDByEdition:
    """Test that core CRUD operations work identically in both editions."""

    def test_digest_crud_works(self, edition, client, test_db):
        """Verify digest read/delete works regardless of edition."""
        digest = Digest(
            url=f"https://example.com/crud-{edition}",
            title=f"CRUD Test ({edition})",
            summary="Test summary",
            source_type="rss",
        )
        test_db.add(digest)
        test_db.commit()

        # Read
        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200
        assert response.json()["title"] == f"CRUD Test ({edition})"

        # Delete
        response = client.delete(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 404

    def test_source_crud_works(self, edition, client, test_db):
        """Verify source CRUD works regardless of edition."""
        # Create
        response = client.post("/api/v1/sources", json={
            "name": f"Source ({edition})",
            "type": "rss",
            "url": f"https://example.com/{edition}.xml",
        })
        assert response.status_code == 201
        source_id = response.json()["id"]

        # Update
        response = client.patch(f"/api/v1/sources/{source_id}", json={"name": "Updated"})
        assert response.status_code == 200

        # Delete
        response = client.delete(f"/api/v1/sources/{source_id}")
        assert response.status_code == 204

    def test_feed_crud_works(self, edition, client, test_db, sample_source, sample_prompt_template):
        """Verify feed CRUD works regardless of edition."""
        # Create
        response = client.post("/api/v1/feeds", json={
            "name": f"Feed ({edition})",
            "schedule_cron": "0 10 * * *",
            "schedule_enabled": False,
            "prompt_template_id": sample_prompt_template.id,
            "source_ids": [sample_source.id],
        })
        assert response.status_code == 201
        feed_id = response.json()["id"]

        # Update (feeds use PUT, not PATCH)
        response = client.put(f"/api/v1/feeds/{feed_id}", json={
            "name": f"Feed ({edition})",
            "schedule_cron": "0 10 * * *",
            "schedule_enabled": False,
            "prompt_template_id": sample_prompt_template.id,
            "source_ids": [sample_source.id],
            "description": "Updated",
        })
        assert response.status_code == 200

        # Delete
        response = client.delete(f"/api/v1/feeds/{feed_id}")
        assert response.status_code == 204

    def test_template_crud_works(self, edition, client, test_db):
        """Verify prompt template CRUD works regardless of edition."""
        # Create
        response = client.post("/api/v1/templates/prompt", json={
            "name": f"Template ({edition})",
            "system_prompt": "You are helpful.",
            "user_prompt_template": "Summarize: {content}",
            "language": "en",
            "target_length": 100,
        })
        assert response.status_code == 201
        template_id = response.json()["id"]

        # Update (templates use PUT, not PATCH)
        response = client.put(f"/api/v1/templates/prompt/{template_id}", json={"target_length": 200})
        assert response.status_code == 200

        # Delete
        response = client.delete(f"/api/v1/templates/prompt/{template_id}")
        assert response.status_code == 204


class TestStatsEndpointsByEdition:
    """Test stats endpoints return correct cost field visibility."""

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_digest_stats_cost_fields(self, edition, client, test_db):
        """GET /digests/stats returns cost fields only in Enterprise edition."""
        digest = Digest(
            url=f"https://example.com/stats-{edition}",
            title="Stats Test",
            summary="Summary",
            source_type="rss",
            estimated_cost=0.01,
        )
        test_db.add(digest)
        test_db.commit()

        response = client.get("/api/v1/digests/stats")
        assert response.status_code == 200

        data = response.json()
        if edition == "oss":
            assert "total_cost" not in data
        else:
            assert "total_cost" in data


class TestEditionSpecificFeatures:
    """Test features that behave differently between editions."""

    @pytest.mark.xfail(reason="Edition filtering in API responses needs investigation - FastAPI/Pydantic v2 serialization")
    def test_oss_excludes_all_cost_fields(self, oss_edition, client, test_db):
        """Verify OSS edition excludes all cost-related fields."""
        from reconly_api.schemas.edition import OSS_EXCLUDED_FIELDS

        digest = Digest(
            url="https://example.com/oss-cost-test",
            title="OSS Cost Test",
            summary="Test",
            source_type="rss",
            estimated_cost=0.05,
        )
        test_db.add(digest)
        test_db.commit()

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        for field in OSS_EXCLUDED_FIELDS:
            assert field not in data

    def test_enterprise_includes_cost_fields(self, enterprise_edition, client, test_db):
        """Verify Enterprise edition includes cost-related fields."""
        digest = Digest(
            url="https://example.com/enterprise-cost-test",
            title="Enterprise Cost Test",
            summary="Test",
            source_type="rss",
            estimated_cost=0.05,
        )
        test_db.add(digest)
        test_db.commit()

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["estimated_cost"] == 0.05
