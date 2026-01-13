"""Tests for batch delete API endpoints."""
import pytest


@pytest.mark.api
class TestBatchDeleteDigests:
    """Test suite for /api/v1/digests/batch-delete endpoint."""

    def test_batch_delete_digests_success(self, client, test_db):
        """Test batch deleting multiple digests."""
        from reconly_core.database.models import Digest

        # Create multiple digests
        digests = []
        for i in range(3):
            digest = Digest(
                url=f"https://example.com/article{i}",
                title=f"Test Article {i}",
                summary=f"Summary {i}",
                source_type="website"
            )
            test_db.add(digest)
            digests.append(digest)
        test_db.commit()

        digest_ids = [d.id for d in digests]

        # Batch delete
        response = client.post("/api/v1/digests/batch-delete", json={"ids": digest_ids})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert data["failed_ids"] == []

        # Verify all deleted
        for digest_id in digest_ids:
            response = client.get(f"/api/v1/digests/{digest_id}")
            assert response.status_code == 404

    def test_batch_delete_digests_partial(self, client, test_db):
        """Test batch delete with some non-existent IDs."""
        from reconly_core.database.models import Digest

        # Create one digest
        digest = Digest(
            url="https://example.com/article",
            title="Test Article",
            summary="Summary",
            source_type="website"
        )
        test_db.add(digest)
        test_db.commit()

        # Try to delete existing and non-existing
        response = client.post("/api/v1/digests/batch-delete", json={
            "ids": [digest.id, 99998, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert set(data["failed_ids"]) == {99998, 99999}

    def test_batch_delete_digests_empty_list(self, client):
        """Test batch delete with empty list."""
        response = client.post("/api/v1/digests/batch-delete", json={"ids": []})
        assert response.status_code == 422  # Validation error

    def test_batch_delete_digests_all_nonexistent(self, client):
        """Test batch delete with all non-existent IDs."""
        response = client.post("/api/v1/digests/batch-delete", json={
            "ids": [99997, 99998, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert set(data["failed_ids"]) == {99997, 99998, 99999}


@pytest.mark.api
class TestBatchDeleteSources:
    """Test suite for /api/v1/sources/batch-delete endpoint."""

    def test_batch_delete_sources_success(self, client, test_db):
        """Test batch deleting multiple sources."""
        from reconly_core.database.models import Source

        # Create multiple sources
        sources = []
        for i in range(3):
            source = Source(
                name=f"Test Source {i}",
                type="rss",
                url=f"https://example.com/feed{i}.xml",
                enabled=True
            )
            test_db.add(source)
            sources.append(source)
        test_db.commit()

        source_ids = [s.id for s in sources]

        # Batch delete
        response = client.post("/api/v1/sources/batch-delete", json={"ids": source_ids})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert data["failed_ids"] == []

        # Verify all deleted
        for source_id in source_ids:
            response = client.get(f"/api/v1/sources/{source_id}")
            assert response.status_code == 404

    def test_batch_delete_sources_partial(self, client, sample_source):
        """Test batch delete with some non-existent IDs."""
        response = client.post("/api/v1/sources/batch-delete", json={
            "ids": [sample_source.id, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["failed_ids"] == [99999]


@pytest.mark.api
class TestBatchDeleteFeeds:
    """Test suite for /api/v1/feeds/batch-delete endpoint."""

    def test_batch_delete_feeds_success(self, client, test_db):
        """Test batch deleting multiple feeds."""
        from reconly_core.database.models import Feed

        # Create multiple feeds
        feeds = []
        for i in range(3):
            feed = Feed(
                name=f"Test Feed {i}",
                schedule_cron="0 8 * * *",
                schedule_enabled=True
            )
            test_db.add(feed)
            feeds.append(feed)
        test_db.commit()

        feed_ids = [f.id for f in feeds]

        # Batch delete
        response = client.post("/api/v1/feeds/batch-delete", json={"ids": feed_ids})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert data["failed_ids"] == []

        # Verify all deleted
        for feed_id in feed_ids:
            response = client.get(f"/api/v1/feeds/{feed_id}")
            assert response.status_code == 404

    def test_batch_delete_feeds_partial(self, client, sample_feed):
        """Test batch delete with some non-existent IDs."""
        response = client.post("/api/v1/feeds/batch-delete", json={
            "ids": [sample_feed.id, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["failed_ids"] == [99999]


@pytest.mark.api
class TestBatchDeletePromptTemplates:
    """Test suite for /api/v1/templates/prompt/batch-delete endpoint."""

    def test_batch_delete_prompt_templates_success(self, client, test_db):
        """Test batch deleting multiple prompt templates."""
        from reconly_core.database.models import PromptTemplate

        # Create multiple templates
        templates = []
        for i in range(3):
            template = PromptTemplate(
                name=f"Test Template {i}",
                description=f"Description {i}",
                system_prompt="System prompt",
                user_prompt_template="User prompt",
                origin="user",
                is_active=True
            )
            test_db.add(template)
            templates.append(template)
        test_db.commit()

        template_ids = [t.id for t in templates]

        # Batch delete
        response = client.post("/api/v1/templates/prompt/batch-delete", json={"ids": template_ids})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert data["failed_ids"] == []

        # Verify all deleted
        for template_id in template_ids:
            response = client.get(f"/api/v1/templates/prompt/{template_id}")
            assert response.status_code == 404

    def test_batch_delete_prompt_templates_partial(self, client, test_db):
        """Test batch delete with some non-existent IDs."""
        from reconly_core.database.models import PromptTemplate

        template = PromptTemplate(
            name="Test Template",
            description="Description",
            system_prompt="System prompt",
            user_prompt_template="User prompt",
            origin="user",
            is_active=True
        )
        test_db.add(template)
        test_db.commit()

        response = client.post("/api/v1/templates/prompt/batch-delete", json={
            "ids": [template.id, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["failed_ids"] == [99999]


@pytest.mark.api
class TestBatchDeleteReportTemplates:
    """Test suite for /api/v1/templates/report/batch-delete endpoint."""

    def test_batch_delete_report_templates_success(self, client, test_db):
        """Test batch deleting multiple report templates."""
        from reconly_core.database.models import ReportTemplate

        # Create multiple templates
        templates = []
        for i in range(3):
            template = ReportTemplate(
                name=f"Test Report {i}",
                description=f"Description {i}",
                format="markdown",
                template_content="Template content",
                origin="user",
                is_active=True
            )
            test_db.add(template)
            templates.append(template)
        test_db.commit()

        template_ids = [t.id for t in templates]

        # Batch delete
        response = client.post("/api/v1/templates/report/batch-delete", json={"ids": template_ids})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3
        assert data["failed_ids"] == []

        # Verify all deleted
        for template_id in template_ids:
            response = client.get(f"/api/v1/templates/report/{template_id}")
            assert response.status_code == 404

    def test_batch_delete_report_templates_partial(self, client, test_db):
        """Test batch delete with some non-existent IDs."""
        from reconly_core.database.models import ReportTemplate

        template = ReportTemplate(
            name="Test Report",
            description="Description",
            format="markdown",
            template_content="Template content",
            origin="user",
            is_active=True
        )
        test_db.add(template)
        test_db.commit()

        response = client.post("/api/v1/templates/report/batch-delete", json={
            "ids": [template.id, 99999]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["failed_ids"] == [99999]
