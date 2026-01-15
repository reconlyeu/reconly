"""IMAP email fetcher module.

This module provides a fetcher for retrieving emails from IMAP servers,
enabling users to ingest, filter, and summarize emails from their inboxes.

Incremental Fetching:
    The fetcher supports deduplication via processed_message_ids stored in
    the source config. When processed_message_ids is passed via kwargs,
    emails with matching message IDs are filtered out. The fetcher returns
    metadata about newly processed IDs via a special _fetch_metadata item.
"""
import logging
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, urlencode

from reconly_core.config_types import ConfigField
from reconly_core.email import (
    EmailMessage,
    GenericIMAPProvider,
    IMAPConfig,
    IMAPError,
)
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema
from reconly_core.fetchers.registry import register_fetcher

logger = logging.getLogger(__name__)


# Default age limit for first run (when no tracking data exists)
# Prevents fetching hundreds of old emails on first run
DEFAULT_FIRST_RUN_MAX_AGE_DAYS = 7

# Maximum number of processed message IDs to retain (circular buffer)
MAX_PROCESSED_MESSAGE_IDS = 1000

# Key used for fetch metadata in return value
FETCH_METADATA_KEY = "_fetch_metadata"


def _is_metadata_item(item: Dict[str, Any]) -> bool:
    """Check if an item is the fetch metadata marker."""
    return isinstance(item, dict) and item.get(FETCH_METADATA_KEY, False)


def extract_fetch_metadata(items: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Extract fetch metadata from a list of fetched items.

    The IMAP fetcher appends metadata as the last item in the list when
    incremental fetching is enabled. This helper extracts that metadata.

    Args:
        items: List of items returned from fetch()

    Returns:
        Metadata dict if present, None otherwise. The metadata contains:
        - new_processed_ids: List of message IDs from this fetch
        - updated_processed_message_ids: Full updated list for storage
    """
    if not items:
        return None

    last_item = items[-1]
    return last_item if _is_metadata_item(last_item) else None


def strip_fetch_metadata(items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Remove fetch metadata from a list of fetched items.

    Use this to get only the actual email items, without the metadata entry.

    Args:
        items: List of items returned from fetch()

    Returns:
        List of items without the metadata entry
    """
    if not items:
        return []

    return items[:-1] if _is_metadata_item(items[-1]) else items


def get_first_run_max_age_days() -> int:
    """Get the max age in days for first run from env or default."""
    env_value = os.environ.get("IMAP_FIRST_RUN_MAX_AGE_DAYS")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass
    return DEFAULT_FIRST_RUN_MAX_AGE_DAYS


@register_fetcher("imap")
class IMAPFetcher(BaseFetcher):
    """Fetches emails from IMAP servers.

    This fetcher connects to IMAP email servers and retrieves emails
    in read-only mode. It supports Gmail, Outlook, and generic IMAP servers.

    Example:
        >>> fetcher = IMAPFetcher()
        >>> items = fetcher.fetch(
        ...     url="imap://imap.gmail.com",
        ...     imap_username="user@gmail.com",
        ...     imap_password="app_password",
        ...     imap_folders=["INBOX"],
        ... )
    """

    def __init__(self):
        pass

    def _get_processed_ids(self, kwargs: Dict[str, Any]) -> Set[str]:
        """Extract processed message IDs from kwargs/config.

        Args:
            kwargs: Keyword arguments containing source config

        Returns:
            Set of already-processed message IDs
        """
        processed_ids = kwargs.get("processed_message_ids") or []
        return set(processed_ids)

    def _filter_processed_emails(
        self,
        items: List[Dict[str, Any]],
        processed_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """Filter out already-processed emails based on message ID.

        Args:
            items: List of email items from fetch
            processed_ids: Set of already-processed message IDs

        Returns:
            List of items that haven't been processed yet
        """
        if not processed_ids:
            return items

        new_items = []
        for item in items:
            message_id = item.get("message_id")
            if message_id and message_id in processed_ids:
                logger.debug(f"Skipping already-processed email: {message_id}")
                continue
            new_items.append(item)

        filtered_count = len(items) - len(new_items)
        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} already-processed emails")

        return new_items

    def _build_updated_processed_ids(
        self,
        existing_ids: Set[str],
        new_ids: List[str],
    ) -> List[str]:
        """Build updated processed message IDs list with circular buffer.

        Maintains a maximum of MAX_PROCESSED_MESSAGE_IDS entries, keeping
        the most recently processed IDs.

        Args:
            existing_ids: Set of existing processed message IDs
            new_ids: List of new message IDs to add

        Returns:
            Updated list of processed message IDs (max MAX_PROCESSED_MESSAGE_IDS)
        """
        # Use deque for efficient circular buffer behavior
        buffer = deque(existing_ids, maxlen=MAX_PROCESSED_MESSAGE_IDS)

        # Add new IDs (deque automatically removes oldest if at maxlen)
        for msg_id in new_ids:
            if msg_id and msg_id not in buffer:
                buffer.append(msg_id)

        return list(buffer)

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Fetch emails from an IMAP server with incremental deduplication.

        Args:
            url: IMAP server URL (e.g., "imap://imap.gmail.com" or just config identifier)
            since: Only return emails received after this datetime (optional).
                   If None (first run), defaults to IMAP_FIRST_RUN_MAX_AGE_DAYS ago.
            max_items: Maximum number of emails to return (optional).
                       Applied after date filtering, newest first.
            **kwargs: IMAP configuration options:
                - imap_provider: Provider type ("gmail", "outlook", "generic")
                - imap_host: IMAP server hostname (required for generic)
                - imap_port: IMAP server port (default 993)
                - imap_username: Email account username
                - imap_password: Email account password/app password
                - imap_use_ssl: Use SSL/TLS (default True)
                - imap_folders: List of folders to fetch from (default ["INBOX"])
                - imap_from_filter: Filter by sender pattern
                - imap_subject_filter: Filter by subject pattern
                - processed_message_ids: List of already-processed message IDs
                  (for incremental fetching / deduplication)

        Returns:
            List of email dictionaries, each containing:
            - url: mailto: URL with message details
            - title: Email subject
            - content: Email body text
            - published: Email date (ISO format string)
            - author: Sender email address
            - source_type: 'imap'
            - email_folder: Folder the email was fetched from
            - message_id: Unique message ID
            - recipients: List of recipient addresses

            The last item may be a metadata dict with key "_fetch_metadata"
            containing:
            - new_processed_ids: List of message IDs from this fetch
            - updated_processed_message_ids: Full updated list for storage

        Raises:
            Exception: If IMAP connection or fetch fails
        """
        try:
            # Apply default age limit for first run (when since=None)
            if since is None:
                max_age_days = get_first_run_max_age_days()
                if max_age_days > 0:
                    since = datetime.now() - timedelta(days=max_age_days)

            # Get existing processed IDs for deduplication
            processed_ids = self._get_processed_ids(kwargs)

            # Build IMAP config from kwargs
            config = self._build_config(url, **kwargs)

            # Fetch emails from all configured folders
            all_emails: List[EmailMessage] = []

            with GenericIMAPProvider(config) as provider:
                for folder in config.folders:
                    try:
                        emails = provider.fetch_emails(
                            folder=folder,
                            since=since,
                            max_items=max_items,
                        )
                        all_emails.extend(emails)
                        logger.debug(f"Fetched {len(emails)} emails from {folder}")
                    except IMAPError as e:
                        logger.warning(f"Failed to fetch from folder '{folder}': {e}")
                        continue

            # Convert to standard item format
            items = [self._email_to_item(email) for email in all_emails]

            # Filter out already-processed emails (deduplication)
            items = self._filter_processed_emails(items, processed_ids)

            # Sort by date (newest first) and apply max_items limit
            items.sort(
                key=lambda a: a.get("published") or "",
                reverse=True
            )

            if max_items and len(items) > max_items:
                items = items[:max_items]

            # Extract message IDs from new items for tracking
            new_message_ids = [
                item.get("message_id")
                for item in items
                if item.get("message_id")
            ]

            # Build updated processed IDs list with circular buffer
            updated_processed_ids = self._build_updated_processed_ids(
                processed_ids, new_message_ids
            )

            logger.info(
                f"Fetched {len(items)} new emails from IMAP "
                f"(filtered {len(processed_ids)} already-processed)"
            )

            # Append metadata for the caller to persist
            if new_message_ids or processed_ids:
                items.append({
                    FETCH_METADATA_KEY: True,
                    "new_processed_ids": new_message_ids,
                    "updated_processed_message_ids": updated_processed_ids,
                })

            return items

        except Exception as e:
            raise Exception(f"Failed to fetch emails: {e}")

    def _build_config(self, url: str, **kwargs) -> IMAPConfig:
        """Build IMAPConfig from URL and kwargs.

        Args:
            url: IMAP URL or config identifier
            **kwargs: Configuration options

        Returns:
            IMAPConfig instance
        """
        # Extract provider type
        provider = kwargs.get("imap_provider", "generic")

        # Map provider to host if not specified
        host = kwargs.get("imap_host")
        if not host:
            if provider == "gmail":
                host = "imap.gmail.com"
            elif provider == "outlook":
                host = "outlook.office365.com"
            elif url.startswith("imap://"):
                # Extract host from URL
                host = url.replace("imap://", "").split("/")[0].split(":")[0]

        # Get password - either plaintext or decrypt from encrypted storage
        password = kwargs.get("imap_password", "")
        if not password and kwargs.get("imap_password_encrypted"):
            try:
                from reconly_core.email.crypto import decrypt_token
                password = decrypt_token(kwargs["imap_password_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt IMAP password: {e}")
                password = ""

        # Build config
        return IMAPConfig(
            provider=provider,
            host=host,
            port=int(kwargs.get("imap_port", 993)),
            username=kwargs.get("imap_username", ""),
            password=password,
            use_ssl=kwargs.get("imap_use_ssl", True),
            folders=kwargs.get("imap_folders", ["INBOX"]),
            from_filter=kwargs.get("imap_from_filter"),
            subject_filter=kwargs.get("imap_subject_filter"),
            timeout=int(kwargs.get("imap_timeout", 30)),
        )

    def _email_to_item(self, email: EmailMessage) -> Dict[str, Any]:
        """Convert EmailMessage to FetchedItem-compatible dict.

        Args:
            email: EmailMessage object

        Returns:
            Dictionary compatible with FetchedItem format
        """
        # Build mailto: URL with message details
        # Format: mailto:sender@example.com?subject=Subject&message-id=<id>
        url_params = {}
        if email.subject:
            url_params["subject"] = email.subject
        if email.message_id:
            url_params["message-id"] = f"<{email.message_id}>"

        if url_params:
            mailto_url = f"mailto:{quote(email.sender)}?{urlencode(url_params)}"
        else:
            mailto_url = f"mailto:{quote(email.sender)}"

        # Build item dictionary
        item = {
            "url": mailto_url,
            "title": email.subject or "(No subject)",
            "content": email.content or "",
            "published": email.date.isoformat() if email.date else None,
            "author": email.sender_name or email.sender,
            "source_type": "imap",
            # Email-specific metadata
            "email_folder": email.folder,
            "message_id": email.message_id,
            "sender_email": email.sender,
            "recipients": email.recipients,
        }

        return item

    def get_source_type(self) -> str:
        """Get the source type identifier."""
        return "imap"

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the given URL.

        Args:
            url: URL to check

        Returns:
            True if URL appears to be an IMAP configuration
        """
        return url.startswith("imap://") or url.startswith("imaps://")

    def get_description(self) -> str:
        """Get a human-readable description of this fetcher."""
        return "IMAP email fetcher for Gmail, Outlook, and generic IMAP servers"

    def get_config_schema(self) -> FetcherConfigSchema:
        """Get the configuration schema for this fetcher.

        Returns:
            FetcherConfigSchema with IMAP configuration fields
        """
        return FetcherConfigSchema(
            fields=[
                ConfigField(
                    key="imap_provider",
                    type="string",
                    label="Email Provider",
                    description="Email provider type",
                    default="generic",
                    placeholder="generic",
                ),
                ConfigField(
                    key="imap_host",
                    type="string",
                    label="IMAP Server",
                    description="IMAP server hostname (e.g., imap.gmail.com)",
                    required=True,
                    placeholder="imap.example.com",
                ),
                ConfigField(
                    key="imap_port",
                    type="integer",
                    label="IMAP Port",
                    description="IMAP server port (993 for SSL)",
                    default=993,
                ),
                ConfigField(
                    key="imap_username",
                    type="string",
                    label="Username",
                    description="Email account username/address",
                    required=True,
                    placeholder="user@example.com",
                    env_var="IMAP_USERNAME",
                ),
                ConfigField(
                    key="imap_password",
                    type="string",
                    label="Password",
                    description="Email account password or app-specific password",
                    required=True,
                    secret=True,
                    editable=False,
                    env_var="IMAP_PASSWORD",
                ),
                ConfigField(
                    key="imap_use_ssl",
                    type="boolean",
                    label="Use SSL/TLS",
                    description="Connect using SSL/TLS encryption",
                    default=True,
                ),
                ConfigField(
                    key="imap_folders",
                    type="string",
                    label="Folders",
                    description="Comma-separated list of folders to fetch (e.g., INBOX,Sent)",
                    default="INBOX",
                    placeholder="INBOX",
                ),
                ConfigField(
                    key="imap_from_filter",
                    type="string",
                    label="From Filter",
                    description="Filter emails by sender (supports * wildcard)",
                    placeholder="*@newsletter.example.com",
                ),
                ConfigField(
                    key="imap_subject_filter",
                    type="string",
                    label="Subject Filter",
                    description="Filter emails by subject (supports * wildcard)",
                    placeholder="*Weekly Report*",
                ),
            ]
        )
