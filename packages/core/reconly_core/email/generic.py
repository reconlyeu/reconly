"""Generic IMAP provider implementation.

This module provides a generic IMAP client that works with any standard
IMAP server. It uses the Python standard library imaplib for IMAP operations.
"""
from __future__ import annotations

import email as email_stdlib
import imaplib
import logging
import re
import socket
from datetime import datetime
from email.header import decode_header
from email.message import Message as EmailMessageStdlib
from email.utils import parseaddr, parsedate_to_datetime
from typing import List, Optional, Tuple

from reconly_core.email.base import EmailMessage, EmailProvider, IMAPConfig
from reconly_core.email.content import extract_email_content
from reconly_core.email.errors import (
    IMAPAuthError,
    IMAPConnectionError,
    IMAPFetchError,
    IMAPFolderError,
    IMAPParseError,
)

logger = logging.getLogger(__name__)


class GenericIMAPProvider(EmailProvider):
    """Generic IMAP provider using imaplib.

    Connects to any standard IMAP server and fetches emails in read-only mode.
    Never modifies or deletes emails on the server.

    Example:
        >>> config = IMAPConfig(
        ...     provider="generic",
        ...     host="mail.example.com",
        ...     username="user@example.com",
        ...     password="password"
        ... )
        >>> with GenericIMAPProvider(config) as provider:
        ...     emails = provider.fetch_emails("INBOX", max_items=10)
    """

    def __init__(self, config: IMAPConfig):
        """Initialize the generic IMAP provider.

        Args:
            config: IMAPConfig with connection settings
        """
        super().__init__(config)
        self._connection: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None

    def connect(self) -> None:
        """Establish connection to the IMAP server.

        Raises:
            IMAPConnectionError: If connection fails
            IMAPAuthError: If authentication fails
        """
        if self._connected and self._connection:
            return

        host = self.config.host
        port = self.config.port
        timeout = self.config.timeout

        try:
            # Set socket timeout for connection
            socket.setdefaulttimeout(timeout)

            if self.config.use_ssl:
                logger.debug(f"Connecting to {host}:{port} with SSL")
                self._connection = imaplib.IMAP4_SSL(host, port)
            else:
                logger.debug(f"Connecting to {host}:{port} without SSL")
                self._connection = imaplib.IMAP4(host, port)

        except socket.timeout:
            raise IMAPConnectionError(
                f"Connection to {host}:{port} timed out after {timeout}s"
            )
        except socket.gaierror as e:
            raise IMAPConnectionError(
                f"Cannot resolve hostname {host}",
                details=str(e)
            )
        except ConnectionRefusedError:
            raise IMAPConnectionError(
                f"Connection refused by {host}:{port}"
            )
        except Exception as e:
            raise IMAPConnectionError(
                f"Failed to connect to {host}:{port}",
                details=str(e)
            )
        finally:
            # Reset socket timeout
            socket.setdefaulttimeout(None)

        # Authenticate
        try:
            logger.debug(f"Authenticating as {self.config.username}")
            self._connection.login(self.config.username, self.config.password)
            self._connected = True
            logger.info(f"Successfully connected to {host} as {self.config.username}")

        except imaplib.IMAP4.error as e:
            error_msg = str(e).upper()
            self._cleanup_connection()

            # Provide helpful hint for common auth failures
            if "AUTHENTICATIONFAILED" in error_msg:
                details = "Check username and password. For Gmail/Outlook, use an app-specific password."
            else:
                details = str(e)

            raise IMAPAuthError("Authentication failed", details=details)

    def disconnect(self) -> None:
        """Close connection to the IMAP server."""
        self._cleanup_connection()
        logger.debug("Disconnected from IMAP server")

    def _cleanup_connection(self) -> None:
        """Clean up the connection state."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None
        self._connected = False

    def list_folders(self) -> List[str]:
        """List available folders/mailboxes.

        Returns:
            List of folder names

        Raises:
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            status, folder_data = self._connection.list()  # type: ignore

            if status != "OK":
                raise IMAPFolderError("Failed to list folders")

            folders = []
            for item in folder_data:
                if isinstance(item, bytes):
                    # Parse folder name from IMAP LIST response
                    # Format: (\\HasNoChildren) "/" "INBOX"
                    decoded = item.decode("utf-8", errors="replace")
                    match = re.search(r'"([^"]+)"$|(\S+)$', decoded)
                    if match:
                        folder_name = match.group(1) or match.group(2)
                        folders.append(folder_name)

            logger.debug(f"Found {len(folders)} folders")
            return folders

        except imaplib.IMAP4.error as e:
            raise IMAPFolderError("Failed to list folders", details=str(e))

    def fetch_emails(
        self,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
    ) -> List[EmailMessage]:
        """Fetch emails from a folder in read-only mode.

        Args:
            folder: Folder name to fetch from (default "INBOX")
            since: Only return emails after this datetime
            max_items: Maximum number of emails to return

        Returns:
            List of EmailMessage objects, sorted by date (newest first)

        Raises:
            IMAPFolderError: If folder doesn't exist or cannot be selected
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()

        # Select folder in read-only mode (never modify server state)
        try:
            status, data = self._connection.select(folder, readonly=True)  # type: ignore
            if status != "OK":
                raise IMAPFolderError(f"Cannot select folder '{folder}'")
            logger.debug(f"Selected folder '{folder}' in read-only mode")
        except imaplib.IMAP4.error as e:
            raise IMAPFolderError(f"Cannot select folder '{folder}'", details=str(e))

        # Build search criteria
        search_criteria = self._build_search_criteria(since)

        try:
            status, data = self._connection.search(None, *search_criteria)  # type: ignore
            if status != "OK":
                raise IMAPFetchError("Failed to search emails")

            # Get message IDs
            message_ids = data[0].split() if data[0] else []
            logger.debug(f"Found {len(message_ids)} messages matching criteria")

            if not message_ids:
                return []

            # Fetch messages (newest first for proper limiting)
            # IMAP message IDs are sequential, so reverse for newest first
            message_ids = list(reversed(message_ids))

            # Apply max_items limit before fetching
            if max_items and len(message_ids) > max_items:
                message_ids = message_ids[:max_items]

            emails = []
            for msg_id in message_ids:
                try:
                    email_msg = self._fetch_single_email(msg_id, folder)
                    if email_msg:
                        # Apply from_filter if configured
                        if self.config.from_filter:
                            if not self._matches_filter(
                                email_msg.sender, self.config.from_filter
                            ):
                                continue

                        # Apply subject_filter if configured
                        if self.config.subject_filter:
                            if not self._matches_filter(
                                email_msg.subject, self.config.subject_filter
                            ):
                                continue

                        emails.append(email_msg)

                except Exception as e:
                    logger.warning(f"Failed to fetch email {msg_id}: {e}")
                    continue

            # Sort by date (newest first)
            emails.sort(key=lambda e: e.date or datetime.min, reverse=True)

            logger.info(f"Fetched {len(emails)} emails from '{folder}'")
            return emails

        except imaplib.IMAP4.error as e:
            raise IMAPFetchError("Failed to fetch emails", details=str(e))

    def _ensure_connected(self) -> None:
        """Ensure we have an active connection.

        Raises:
            IMAPConnectionError: If not connected
        """
        if not self._connected or not self._connection:
            raise IMAPConnectionError("Not connected to IMAP server")

    def _build_search_criteria(self, since: Optional[datetime]) -> List[str]:
        """Build IMAP search criteria.

        Args:
            since: Only return emails after this datetime

        Returns:
            List of search criteria strings
        """
        criteria = ["ALL"]

        if since:
            # IMAP SINCE uses date only (no time), format: DD-Mon-YYYY
            date_str = since.strftime("%d-%b-%Y")
            criteria = ["SINCE", date_str]

        return criteria

    def _fetch_single_email(
        self,
        msg_id: bytes,
        folder: str
    ) -> Optional[EmailMessage]:
        """Fetch and parse a single email.

        Args:
            msg_id: IMAP message ID
            folder: Folder the email is in

        Returns:
            Parsed EmailMessage or None if parsing fails
        """
        try:
            # Fetch email headers and body
            status, data = self._connection.fetch(msg_id, "(RFC822)")  # type: ignore

            if status != "OK" or not data or not data[0]:
                return None

            # Parse the raw email
            raw_email = data[0][1] if isinstance(data[0], tuple) else data[0]
            if isinstance(raw_email, bytes):
                msg = email_stdlib.message_from_bytes(raw_email)
            else:
                return None

            return self._parse_email_message(msg, folder)

        except Exception as e:
            logger.warning(f"Error fetching email {msg_id}: {e}")
            return None

    def _parse_email_message(
        self,
        msg: EmailMessageStdlib,
        folder: str
    ) -> EmailMessage:
        """Parse an email.message.Message into our EmailMessage format.

        Args:
            msg: Python email message object
            folder: Folder the email is in

        Returns:
            Parsed EmailMessage
        """
        # Extract message ID
        message_id = msg.get("Message-ID", "")
        if message_id:
            # Clean up message ID (remove < > brackets)
            message_id = message_id.strip("<>")

        # Extract and decode subject
        subject = self._decode_header_value(msg.get("Subject", ""))

        # Extract sender
        from_header = msg.get("From", "")
        sender_name, sender_addr = parseaddr(from_header)
        sender_name = self._decode_header_value(sender_name) if sender_name else None

        # Extract recipients
        to_header = msg.get("To", "")
        recipients = []
        if to_header:
            # Handle multiple recipients
            for addr in to_header.split(","):
                _, email_addr = parseaddr(addr.strip())
                if email_addr:
                    recipients.append(email_addr)

        # Extract date
        date = None
        date_header = msg.get("Date")
        if date_header:
            try:
                date = parsedate_to_datetime(date_header)
            except Exception:
                pass

        # Extract content
        text_content, html_content = self._extract_body(msg)

        # If we only have HTML, convert to text
        if not text_content and html_content:
            text_content = extract_email_content(html_content)

        return EmailMessage(
            message_id=message_id,
            subject=subject,
            sender=sender_addr,
            sender_name=sender_name,
            recipients=recipients,
            date=date,
            content=text_content,
            html_content=html_content,
            folder=folder,
        )

    def _decode_header_value(self, value: str) -> str:
        """Decode an email header value that may be encoded.

        Args:
            value: Raw header value

        Returns:
            Decoded string
        """
        if not value:
            return ""

        try:
            decoded_parts = decode_header(value)
            result_parts = []

            for content, charset in decoded_parts:
                if isinstance(content, bytes):
                    charset = charset or "utf-8"
                    try:
                        result_parts.append(content.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        result_parts.append(content.decode("utf-8", errors="replace"))
                else:
                    result_parts.append(str(content))

            return "".join(result_parts)

        except Exception:
            return str(value)

    def _extract_body(
        self,
        msg: EmailMessageStdlib
    ) -> Tuple[str, Optional[str]]:
        """Extract text and HTML body from email message.

        Prefers plain text, falls back to HTML.

        Args:
            msg: Python email message object

        Returns:
            Tuple of (text_content, html_content)
        """
        text_content = ""
        html_content = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain" and not text_content:
                    text_content = self._decode_payload(part)
                elif content_type == "text/html" and not html_content:
                    html_content = self._decode_payload(part)

        else:
            content_type = msg.get_content_type()
            payload = self._decode_payload(msg)

            if content_type == "text/plain":
                text_content = payload
            elif content_type == "text/html":
                html_content = payload

        return text_content, html_content

    def _decode_payload(self, part: EmailMessageStdlib) -> str:
        """Decode email part payload.

        Args:
            part: Email message part

        Returns:
            Decoded string content
        """
        try:
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                # Try to get charset from part
                charset = part.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    return payload.decode("utf-8", errors="replace")
            elif isinstance(payload, str):
                return payload
            return ""
        except Exception:
            return ""

    def _matches_filter(self, value: str, pattern: str) -> bool:
        """Check if a value matches a filter pattern.

        Supports simple wildcard matching with * for any characters.

        Args:
            value: Value to check
            pattern: Filter pattern (can include * wildcards)

        Returns:
            True if value matches pattern
        """
        if not pattern:
            return True

        # Convert glob-style pattern to regex
        regex_pattern = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.search(regex_pattern, value, re.IGNORECASE))
