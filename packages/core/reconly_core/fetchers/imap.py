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
import time
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
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema, ValidationResult
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
                if not password:
                    raise ValueError("Decrypted password is empty")
            except Exception as e:
                logger.error(f"Failed to decrypt IMAP password: {e}")
                raise IMAPError(
                    f"Cannot decrypt IMAP password. Ensure SECRET_KEY is set correctly. "
                    f"Error: {e}"
                )

        # Validate we have a password
        if not password:
            logger.error("No IMAP password provided (neither plaintext nor encrypted)")
            raise IMAPError(
                "IMAP password not configured. Please reconfigure the source with credentials."
            )

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

    def _extract_image_from_html(self, html_content: Optional[str]) -> Optional[str]:
        """Extract the first meaningful image URL from HTML content.

        Filters out tracking pixels, spacers, and other non-content images.

        Args:
            html_content: HTML string to parse

        Returns:
            URL of the first content image, or None
        """
        if not html_content:
            return None

        import re

        # Find all img tags with src attribute
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        matches = re.findall(img_pattern, html_content, re.IGNORECASE)

        # Filter out tracking pixels and tiny images
        skip_patterns = [
            r'tracking',
            r'pixel',
            r'spacer',
            r'\.gif$',  # Most tracking pixels are GIFs
            r'1x1',
            r'beacon',
            r'open\.gif',
            r'mail\.google\.com',  # Gmail tracking
            r'email-open',
            r'cid:',  # Embedded content IDs (not URLs)
            r'^data:',  # Data URIs (inline images)
        ]

        for img_url in matches:
            # Skip if matches any skip pattern
            if any(re.search(pattern, img_url, re.IGNORECASE) for pattern in skip_patterns):
                continue

            # Skip very short URLs (likely tracking)
            if len(img_url) < 20:
                continue

            # Ensure it's a proper URL
            if img_url.startswith(('http://', 'https://')):
                return img_url

        return None

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

        # Extract preview image from HTML content
        image_url = self._extract_image_from_html(email.html_content)

        # Build item dictionary
        item = {
            "url": mailto_url,
            "title": email.subject or "(No subject)",
            "content": email.content or "",
            "published": email.date.isoformat() if email.date else None,
            "author": email.sender_name or email.sender,
            "source_type": "imap",
            "image_url": image_url,
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

    def validate(
        self,
        url: str,
        config: Optional[Dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate IMAP configuration and optionally test connection.

        Validates:
        - Required fields are present (host, username, password)
        - IMAP URL format is correct
        - Connection to IMAP server succeeds (if test_fetch=True)
        - Authentication succeeds (if test_fetch=True)
        - Configured folders exist (if test_fetch=True)

        Args:
            url: IMAP URL (e.g., "imap://imap.gmail.com") or identifier
            config: IMAP configuration dictionary with:
                - imap_host: IMAP server hostname
                - imap_port: IMAP server port (default: 993)
                - imap_username: Email account username
                - imap_password: Email account password
                - imap_use_ssl: Use SSL/TLS (default: True)
                - imap_folders: List of folders to fetch
                - imap_provider: Provider type (gmail, outlook, generic)
            test_fetch: If True, attempt IMAP connection
            timeout: Connection timeout in seconds

        Returns:
            ValidationResult with:
            - valid: True if configuration is valid
            - errors: List of error messages
            - warnings: List of warning messages
            - test_item_count: Number of folders accessible (if test_fetch=True)
            - response_time_ms: Connection time in milliseconds (if test_fetch=True)
        """
        result = ValidationResult()
        result.url_type = 'imap'
        config = config or {}

        # Validate URL format for IMAP
        if url and not url.startswith(("imap://", "imaps://")):
            # If URL is provided, validate it
            if url.startswith(("http://", "https://")):
                result.add_error(
                    "IMAP sources should use imap:// or imaps:// URL scheme, "
                    "not http:// or https://. You can also leave URL empty "
                    "and configure via imap_host setting."
                )
                return result

        # Check for required configuration fields
        host = config.get("imap_host")
        username = config.get("imap_username")
        password = config.get("imap_password")
        password_encrypted = config.get("imap_password_encrypted")

        # Extract host from URL if not in config
        if not host and url:
            if url.startswith("imap://"):
                host = url.replace("imap://", "").split("/")[0].split(":")[0]
            elif url.startswith("imaps://"):
                host = url.replace("imaps://", "").split("/")[0].split(":")[0]

        # Map provider to host if not specified
        provider = config.get("imap_provider", "generic")
        if not host:
            if provider == "gmail":
                host = "imap.gmail.com"
            elif provider == "outlook":
                host = "outlook.office365.com"

        # Validate required fields
        if not host:
            result.add_error(
                "IMAP host is required. Specify via imap_host config "
                "or use imap://hostname URL format."
            )

        if not username:
            result.add_error(
                "IMAP username is required. "
                "Configure via imap_username setting or IMAP_USERNAME environment variable."
            )

        if not password and not password_encrypted:
            result.add_error(
                "IMAP password is required. "
                "Configure via imap_password setting or IMAP_PASSWORD environment variable."
            )

        # Warn about OAuth for Gmail/Outlook
        if provider in ("gmail", "outlook"):
            result.add_warning(
                f"{provider.title()} requires an app-specific password. "
                "Regular password authentication may not work."
            )

        # If basic validation failed, return early
        if not result.valid:
            return result

        # Validate folders config
        folders = config.get("imap_folders", ["INBOX"])
        if isinstance(folders, str):
            folders = [f.strip() for f in folders.split(",")]

        if not folders:
            result.add_warning(
                "No folders specified, defaulting to INBOX."
            )

        # If test_fetch is enabled, try to connect
        if test_fetch and result.valid:
            result = self._validate_connection(
                host=host,
                port=int(config.get("imap_port", 993)),
                username=username,
                password=password or self._decrypt_password(password_encrypted),
                use_ssl=config.get("imap_use_ssl", True),
                folders=folders,
                timeout=timeout,
                result=result,
            )

        return result

    def _decrypt_password(self, encrypted_password: Optional[str]) -> str:
        """Decrypt an encrypted password if provided.

        Args:
            encrypted_password: Encrypted password string

        Returns:
            Decrypted password or empty string
        """
        if not encrypted_password:
            return ""
        try:
            from reconly_core.email.crypto import decrypt_token
            return decrypt_token(encrypted_password)
        except Exception as e:
            logger.warning(f"Failed to decrypt password: {e}")
            return ""

    def _validate_connection(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool,
        folders: List[str],
        timeout: int,
        result: ValidationResult,
    ) -> ValidationResult:
        """
        Test IMAP connection and authentication.

        Args:
            host: IMAP server hostname
            port: IMAP server port
            username: Email account username
            password: Email account password
            use_ssl: Use SSL/TLS
            folders: List of folders to check
            timeout: Connection timeout
            result: ValidationResult to update

        Returns:
            Updated ValidationResult
        """
        try:
            start_time = time.time()

            # Build config for provider
            imap_config = IMAPConfig(
                provider="generic",
                host=host,
                port=port,
                username=username,
                password=password,
                use_ssl=use_ssl,
                folders=folders,
                timeout=timeout,
            )

            # Attempt connection
            with GenericIMAPProvider(imap_config) as provider:
                elapsed_ms = (time.time() - start_time) * 1000
                result.response_time_ms = round(elapsed_ms, 2)

                # Check each folder
                accessible_folders = 0
                for folder in folders:
                    try:
                        # Try to select the folder
                        provider._connection.select(folder, readonly=True)
                        accessible_folders += 1
                    except Exception as e:
                        result.add_warning(
                            f"Folder '{folder}' is not accessible: {str(e)}"
                        )

                result.test_item_count = accessible_folders

                if accessible_folders == 0:
                    result.add_error(
                        "No folders are accessible. "
                        "Check folder names and permissions."
                    )

        except IMAPError as e:
            error_msg = str(e).lower()
            if "authentication" in error_msg or "login" in error_msg:
                result.add_error(
                    "Authentication failed. Please check username and password. "
                    "For Gmail/Outlook, use an app-specific password."
                )
            elif "timeout" in error_msg:
                result.add_error(
                    f"Connection timed out after {timeout} seconds. "
                    "IMAP server may be unreachable."
                )
            elif "ssl" in error_msg or "certificate" in error_msg:
                result.add_error(
                    "SSL/TLS connection failed. "
                    "Try disabling SSL or check certificate settings."
                )
            else:
                result.add_error(f"IMAP connection failed: {str(e)}")

        except Exception as e:
            result.add_error(f"Failed to validate IMAP connection: {str(e)}")

        return result

    def _is_valid_scheme(self, url: str) -> bool:
        """
        Check if URL has a valid scheme for IMAP fetcher.

        Args:
            url: URL to check

        Returns:
            True if URL scheme is valid for IMAP
        """
        return url.startswith(("imap://", "imaps://", "http://", "https://"))
