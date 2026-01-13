"""Tests for FeedService._export_if_configured() method."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from reconly_core.database.models import Feed, FeedRun, Digest
from reconly_core.services.feed_service import FeedService
from reconly_core.exporters.base import ExporterConfigSchema, ExportToPathResult


def create_feed_run(feed_id=1, run_id=1):
    """Helper to create a FeedRun with required fields."""
    return FeedRun(
        id=run_id,
        feed_id=feed_id,
        triggered_by="manual",
        status="completed",
    )


class TestExportIfConfigured:
    """Tests for FeedService._export_if_configured() method."""

    def test_no_export_when_no_output_config(self, db_session):
        """Export should not run when feed has no output_config."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config=None,
        )
        feed_run = create_feed_run()

        # Should not raise, just return early
        service._export_if_configured(feed, feed_run, db_session)

    def test_no_export_when_no_exports_config(self, db_session):
        """Export should not run when output_config has no exports key."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"email_recipients": "test@example.com"},
        )
        feed_run = create_feed_run()

        # Should not raise, just return early
        service._export_if_configured(feed, feed_run, db_session)

    def test_no_export_when_no_digests(self, db_session):
        """Export should not run when feed run has no digests."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"obsidian": {"enabled": True}}},
        )
        feed_run = create_feed_run()
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.commit()

        # Should not raise, just return early (no digests in this feed run)
        service._export_if_configured(feed, feed_run, db_session)

    def test_export_skipped_when_disabled(self, db_session):
        """Export should skip exporter when enabled=False."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"obsidian": {"enabled": False}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        with patch('reconly_core.exporters.registry.get_exporter_class') as mock_get:
            service._export_if_configured(feed, feed_run, db_session)
            # Exporter class should not be fetched since it's disabled
            mock_get.assert_not_called()

    def test_export_runs_when_enabled(self, db_session):
        """Export should run exporter when enabled=True."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"obsidian": {"enabled": True, "path": "/test/vault"}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        # Mock the exporter
        mock_exporter = Mock()
        mock_exporter.get_config_schema.return_value = ExporterConfigSchema(
            fields=[],
            supports_direct_export=True,
        )
        mock_exporter.export_to_path.return_value = ExportToPathResult(
            success=True,
            files_written=1,
            target_path="/test/vault",
            filenames=["test-article.md"],
        )

        mock_exporter_class = Mock(return_value=mock_exporter)

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=True):
            with patch('reconly_core.exporters.registry.get_exporter_class', return_value=mock_exporter_class):
                service._export_if_configured(feed, feed_run, db_session)

        # Verify exporter was called
        mock_exporter.export_to_path.assert_called_once()
        call_args = mock_exporter.export_to_path.call_args
        assert call_args.kwargs['base_path'] == "/test/vault"

    def test_export_uses_path_override(self, db_session):
        """Export should use per-feed path override over global setting."""
        service = FeedService()
        service._session = db_session

        custom_path = "/custom/vault/path"
        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"obsidian": {"enabled": True, "path": custom_path}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        mock_exporter = Mock()
        mock_exporter.get_config_schema.return_value = ExporterConfigSchema(
            fields=[],
            supports_direct_export=True,
        )
        mock_exporter.export_to_path.return_value = ExportToPathResult(
            success=True,
            files_written=1,
            target_path=custom_path,
            filenames=["article.md"],
        )

        mock_exporter_class = Mock(return_value=mock_exporter)

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=True):
            with patch('reconly_core.exporters.registry.get_exporter_class', return_value=mock_exporter_class):
                service._export_if_configured(feed, feed_run, db_session)

        # Verify custom path was used
        call_args = mock_exporter.export_to_path.call_args
        assert call_args.kwargs['base_path'] == custom_path

    def test_export_skipped_when_exporter_not_registered(self, db_session):
        """Export should skip unknown exporter names."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"unknown_exporter": {"enabled": True}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=False):
            with patch('reconly_core.exporters.registry.get_exporter_class') as mock_get:
                service._export_if_configured(feed, feed_run, db_session)
                # Should not attempt to get unknown exporter
                mock_get.assert_not_called()

    def test_export_skipped_when_no_direct_export_support(self, db_session):
        """Export should skip exporters that don't support direct export."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"csv": {"enabled": True, "path": "/test/path"}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        mock_exporter = Mock()
        mock_exporter.get_config_schema.return_value = ExporterConfigSchema(
            fields=[],
            supports_direct_export=False,  # CSV doesn't support direct export
        )

        mock_exporter_class = Mock(return_value=mock_exporter)

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=True):
            with patch('reconly_core.exporters.registry.get_exporter_class', return_value=mock_exporter_class):
                service._export_if_configured(feed, feed_run, db_session)

        # export_to_path should not be called
        mock_exporter.export_to_path.assert_not_called()

    def test_export_failure_does_not_raise(self, db_session):
        """Export failure should be logged but not raise exception."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={"exports": {"obsidian": {"enabled": True, "path": "/test/vault"}}},
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        mock_exporter = Mock()
        mock_exporter.get_config_schema.return_value = ExporterConfigSchema(
            fields=[],
            supports_direct_export=True,
        )
        mock_exporter.export_to_path.side_effect = Exception("Export failed!")

        mock_exporter_class = Mock(return_value=mock_exporter)

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=True):
            with patch('reconly_core.exporters.registry.get_exporter_class', return_value=mock_exporter_class):
                # Should not raise, error is caught and logged
                service._export_if_configured(feed, feed_run, db_session)

    def test_multiple_exporters_run_sequentially(self, db_session):
        """Multiple enabled exporters should run sequentially."""
        service = FeedService()
        service._session = db_session

        feed = Feed(
            id=1,
            name="Test Feed",
            output_config={
                "exports": {
                    "obsidian": {"enabled": True, "path": "/vault"},
                    "json": {"enabled": True, "path": "/json"},
                }
            },
        )
        feed_run = create_feed_run()
        digest = Digest(
            id=1,
            url="https://example.com/article",
            title="Test Article",
            feed_run_id=1,
        )
        db_session.add(feed)
        db_session.add(feed_run)
        db_session.add(digest)
        db_session.commit()

        call_order = []

        def create_mock_exporter(name):
            mock = Mock()
            mock.get_config_schema.return_value = ExporterConfigSchema(
                fields=[],
                supports_direct_export=True,
            )
            mock.export_to_path.return_value = ExportToPathResult(
                success=True,
                files_written=1,
                target_path=f"/{name}",
                filenames=["test.md"],
            )
            mock.export_to_path.side_effect = lambda **kwargs: (
                call_order.append(name),
                ExportToPathResult(success=True, files_written=1, target_path=f"/{name}", filenames=["test.md"]),
            )[1]
            return mock

        exporter_mocks = {
            "obsidian": create_mock_exporter("obsidian"),
            "json": create_mock_exporter("json"),
        }

        def get_mock_class(name):
            return Mock(return_value=exporter_mocks[name])

        with patch('reconly_core.exporters.registry.is_exporter_registered', return_value=True):
            with patch('reconly_core.exporters.registry.get_exporter_class', side_effect=get_mock_class):
                service._export_if_configured(feed, feed_run, db_session)

        # Both exporters should have been called
        assert len(call_order) == 2
