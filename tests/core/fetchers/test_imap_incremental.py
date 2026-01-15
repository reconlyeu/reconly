"""Tests for IMAP fetcher incremental fetching / deduplication."""
from unittest.mock import MagicMock, patch

import pytest

from reconly_core.fetchers.imap import (
    IMAPFetcher,
    extract_fetch_metadata,
    strip_fetch_metadata,
    FETCH_METADATA_KEY,
    MAX_PROCESSED_MESSAGE_IDS,
)


class TestExtractFetchMetadata:
    """Tests for extract_fetch_metadata helper function."""

    def test_returns_none_for_empty_list(self):
        """Test that empty list returns None."""
        assert extract_fetch_metadata([]) is None

    def test_returns_none_for_none_input(self):
        """Test that None input returns None."""
        assert extract_fetch_metadata(None) is None

    def test_returns_none_when_no_metadata(self):
        """Test returns None when list has no metadata item."""
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"message_id": "msg2", "title": "Email 2"},
        ]
        assert extract_fetch_metadata(items) is None

    def test_extracts_metadata_from_last_item(self):
        """Test extracts metadata when present as last item."""
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {
                FETCH_METADATA_KEY: True,
                "new_processed_ids": ["msg1"],
                "updated_processed_message_ids": ["msg1"],
            },
        ]
        metadata = extract_fetch_metadata(items)
        assert metadata is not None
        assert metadata[FETCH_METADATA_KEY] is True
        assert metadata["new_processed_ids"] == ["msg1"]

    def test_ignores_metadata_key_in_non_last_item(self):
        """Test that metadata key in non-last item is ignored."""
        items = [
            {FETCH_METADATA_KEY: True, "fake": "metadata"},  # Not last
            {"message_id": "msg1", "title": "Email 1"},
        ]
        # Last item doesn't have metadata key
        assert extract_fetch_metadata(items) is None


class TestStripFetchMetadata:
    """Tests for strip_fetch_metadata helper function."""

    def test_returns_empty_for_empty_list(self):
        """Test that empty list returns empty list."""
        assert strip_fetch_metadata([]) == []

    def test_returns_same_list_when_no_metadata(self):
        """Test returns same list when no metadata present."""
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"message_id": "msg2", "title": "Email 2"},
        ]
        result = strip_fetch_metadata(items)
        assert result == items
        assert len(result) == 2

    def test_removes_metadata_from_end(self):
        """Test removes metadata item from end of list."""
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"message_id": "msg2", "title": "Email 2"},
            {
                FETCH_METADATA_KEY: True,
                "new_processed_ids": ["msg1", "msg2"],
            },
        ]
        result = strip_fetch_metadata(items)
        assert len(result) == 2
        assert result[0]["message_id"] == "msg1"
        assert result[1]["message_id"] == "msg2"

    def test_preserves_original_list(self):
        """Test that original list is not modified."""
        items = [
            {"message_id": "msg1"},
            {FETCH_METADATA_KEY: True, "data": "meta"},
        ]
        original_len = len(items)
        strip_fetch_metadata(items)
        # Original should be unchanged (we return new list)
        assert len(items) == original_len


class TestIMAPFetcherGetProcessedIds:
    """Tests for IMAPFetcher._get_processed_ids method."""

    def test_returns_empty_set_when_no_ids(self):
        """Test returns empty set when no processed_message_ids in kwargs."""
        fetcher = IMAPFetcher()
        result = fetcher._get_processed_ids({})
        assert result == set()

    def test_returns_empty_set_for_none(self):
        """Test returns empty set when processed_message_ids is None."""
        fetcher = IMAPFetcher()
        result = fetcher._get_processed_ids({"processed_message_ids": None})
        assert result == set()

    def test_returns_set_from_list(self):
        """Test converts list to set."""
        fetcher = IMAPFetcher()
        result = fetcher._get_processed_ids({
            "processed_message_ids": ["msg1", "msg2", "msg3"]
        })
        assert result == {"msg1", "msg2", "msg3"}

    def test_handles_duplicates(self):
        """Test handles duplicate IDs in input."""
        fetcher = IMAPFetcher()
        result = fetcher._get_processed_ids({
            "processed_message_ids": ["msg1", "msg1", "msg2"]
        })
        assert result == {"msg1", "msg2"}


class TestIMAPFetcherFilterProcessedEmails:
    """Tests for IMAPFetcher._filter_processed_emails method."""

    def test_returns_all_items_when_no_processed_ids(self):
        """Test returns all items when processed_ids is empty."""
        fetcher = IMAPFetcher()
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"message_id": "msg2", "title": "Email 2"},
        ]
        result = fetcher._filter_processed_emails(items, set())
        assert len(result) == 2

    def test_filters_processed_emails(self):
        """Test filters out emails with processed message IDs."""
        fetcher = IMAPFetcher()
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"message_id": "msg2", "title": "Email 2"},
            {"message_id": "msg3", "title": "Email 3"},
        ]
        processed_ids = {"msg1", "msg3"}
        result = fetcher._filter_processed_emails(items, processed_ids)
        assert len(result) == 1
        assert result[0]["message_id"] == "msg2"

    def test_keeps_items_without_message_id(self):
        """Test keeps items that don't have a message_id field."""
        fetcher = IMAPFetcher()
        items = [
            {"message_id": "msg1", "title": "Email 1"},
            {"title": "Email without ID"},  # No message_id
        ]
        processed_ids = {"msg1"}
        result = fetcher._filter_processed_emails(items, processed_ids)
        # Email without message_id is kept, msg1 is filtered
        assert len(result) == 1
        assert result[0]["title"] == "Email without ID"

    def test_handles_empty_items_list(self):
        """Test handles empty items list."""
        fetcher = IMAPFetcher()
        result = fetcher._filter_processed_emails([], {"msg1"})
        assert result == []


class TestIMAPFetcherBuildUpdatedProcessedIds:
    """Tests for IMAPFetcher._build_updated_processed_ids method."""

    def test_adds_new_ids_to_empty_set(self):
        """Test adds new IDs when starting with empty set."""
        fetcher = IMAPFetcher()
        result = fetcher._build_updated_processed_ids(
            existing_ids=set(),
            new_ids=["msg1", "msg2"]
        )
        assert "msg1" in result
        assert "msg2" in result
        assert len(result) == 2

    def test_merges_existing_and_new_ids(self):
        """Test merges existing and new IDs."""
        fetcher = IMAPFetcher()
        result = fetcher._build_updated_processed_ids(
            existing_ids={"old1", "old2"},
            new_ids=["new1", "new2"]
        )
        assert "old1" in result
        assert "old2" in result
        assert "new1" in result
        assert "new2" in result
        assert len(result) == 4

    def test_deduplicates_ids(self):
        """Test doesn't add duplicate IDs."""
        fetcher = IMAPFetcher()
        result = fetcher._build_updated_processed_ids(
            existing_ids={"msg1", "msg2"},
            new_ids=["msg1", "msg3"]  # msg1 already exists
        )
        assert result.count("msg1") == 1  # Only one occurrence
        assert "msg2" in result
        assert "msg3" in result

    def test_circular_buffer_limit(self):
        """Test that circular buffer limits to MAX_PROCESSED_MESSAGE_IDS."""
        fetcher = IMAPFetcher()
        # Start with MAX - 5 existing IDs
        existing_ids = {f"old_{i}" for i in range(MAX_PROCESSED_MESSAGE_IDS - 5)}
        # Add 10 new IDs (should overflow by 5)
        new_ids = [f"new_{i}" for i in range(10)]

        result = fetcher._build_updated_processed_ids(existing_ids, new_ids)

        # Should be capped at MAX
        assert len(result) == MAX_PROCESSED_MESSAGE_IDS
        # New IDs should all be present
        for new_id in new_ids:
            assert new_id in result

    def test_ignores_none_and_empty_ids(self):
        """Test ignores None and empty string IDs."""
        fetcher = IMAPFetcher()
        result = fetcher._build_updated_processed_ids(
            existing_ids=set(),
            new_ids=["msg1", None, "", "msg2"]
        )
        assert "msg1" in result
        assert "msg2" in result
        assert None not in result
        assert "" not in result


class TestIMAPFetcherIntegration:
    """Integration tests for IMAP fetcher incremental fetching."""

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetch_filters_processed_emails(self, mock_provider_class):
        """Test that fetch() filters out already-processed emails."""
        # Setup mock
        mock_email1 = MagicMock()
        mock_email1.message_id = "msg1"
        mock_email1.subject = "Email 1"
        mock_email1.sender = "sender@example.com"
        mock_email1.sender_name = "Sender"
        mock_email1.content = "Content 1"
        mock_email1.date = None
        mock_email1.folder = "INBOX"
        mock_email1.recipients = []

        mock_email2 = MagicMock()
        mock_email2.message_id = "msg2"
        mock_email2.subject = "Email 2"
        mock_email2.sender = "sender@example.com"
        mock_email2.sender_name = "Sender"
        mock_email2.content = "Content 2"
        mock_email2.date = None
        mock_email2.folder = "INBOX"
        mock_email2.recipients = []

        mock_provider = MagicMock()
        mock_provider.fetch_emails.return_value = [mock_email1, mock_email2]
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider_class.return_value = mock_provider

        # Fetch with msg1 already processed
        fetcher = IMAPFetcher()
        items = fetcher.fetch(
            url="imap://test.example.com",
            imap_username="user@example.com",
            imap_password="password",
            imap_host="test.example.com",
            processed_message_ids=["msg1"],  # msg1 already processed
        )

        # Strip metadata to get only email items
        email_items = strip_fetch_metadata(items)

        # Should only have msg2 (msg1 filtered out)
        assert len(email_items) == 1
        assert email_items[0]["message_id"] == "msg2"

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetch_returns_metadata_with_new_ids(self, mock_provider_class):
        """Test that fetch() returns metadata with new processed IDs."""
        mock_email = MagicMock()
        mock_email.message_id = "new_msg"
        mock_email.subject = "New Email"
        mock_email.sender = "sender@example.com"
        mock_email.sender_name = "Sender"
        mock_email.content = "Content"
        mock_email.date = None
        mock_email.folder = "INBOX"
        mock_email.recipients = []

        mock_provider = MagicMock()
        mock_provider.fetch_emails.return_value = [mock_email]
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()
        items = fetcher.fetch(
            url="imap://test.example.com",
            imap_username="user@example.com",
            imap_password="password",
            imap_host="test.example.com",
            processed_message_ids=["old_msg"],
        )

        # Extract metadata
        metadata = extract_fetch_metadata(items)

        assert metadata is not None
        assert "new_msg" in metadata["new_processed_ids"]
        assert "new_msg" in metadata["updated_processed_message_ids"]
        assert "old_msg" in metadata["updated_processed_message_ids"]

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetch_empty_result_still_has_metadata(self, mock_provider_class):
        """Test that empty fetch result still includes metadata when processed_ids present."""
        mock_email = MagicMock()
        mock_email.message_id = "msg1"
        mock_email.subject = "Email"
        mock_email.sender = "sender@example.com"
        mock_email.sender_name = "Sender"
        mock_email.content = "Content"
        mock_email.date = None
        mock_email.folder = "INBOX"
        mock_email.recipients = []

        mock_provider = MagicMock()
        mock_provider.fetch_emails.return_value = [mock_email]
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()
        items = fetcher.fetch(
            url="imap://test.example.com",
            imap_username="user@example.com",
            imap_password="password",
            imap_host="test.example.com",
            processed_message_ids=["msg1"],  # Already processed, will filter out
        )

        # All emails filtered, but metadata should still be present
        email_items = strip_fetch_metadata(items)
        assert len(email_items) == 0

        metadata = extract_fetch_metadata(items)
        assert metadata is not None
        assert metadata["new_processed_ids"] == []
        assert "msg1" in metadata["updated_processed_message_ids"]

    @patch("reconly_core.fetchers.imap.GenericIMAPProvider")
    def test_fetch_no_metadata_when_no_tracking(self, mock_provider_class):
        """Test no metadata appended when not using incremental tracking."""
        mock_provider = MagicMock()
        mock_provider.fetch_emails.return_value = []
        mock_provider.__enter__ = MagicMock(return_value=mock_provider)
        mock_provider.__exit__ = MagicMock(return_value=False)
        mock_provider_class.return_value = mock_provider

        fetcher = IMAPFetcher()
        items = fetcher.fetch(
            url="imap://test.example.com",
            imap_username="user@example.com",
            imap_password="password",
            imap_host="test.example.com",
            # No processed_message_ids provided
        )

        # No metadata when no tracking data
        metadata = extract_fetch_metadata(items)
        assert metadata is None
