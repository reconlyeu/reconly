"""Base classes and data structures for email providers.

This module defines the abstract base class for email providers and the data
structures used to represent email messages and configuration.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass
class EmailMessage:
    """Represents a parsed email message.

    Attributes:
        message_id: Unique message identifier from the email headers
        subject: Email subject line
        sender: Sender email address (From header)
        sender_name: Sender display name if available
        recipients: List of recipient email addresses (To header)
        date: Email date/time from Date header
        content: Extracted plain text content of the email body
        html_content: Original HTML content if available
        folder: IMAP folder the email was fetched from
        metadata: Additional provider-specific metadata
    """
    message_id: str
    subject: str
    sender: str
    sender_name: Optional[str] = None
    recipients: List[str] = field(default_factory=list)
    date: Optional[datetime] = None
    content: str = ""
    html_content: Optional[str] = None
    folder: str = "INBOX"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for serialization."""
        result = {
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "recipients": self.recipients,
            "date": self.date.isoformat() if self.date else None,
            "content": self.content,
            "folder": self.folder,
        }
        if self.html_content:
            result["html_content"] = self.html_content
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class IMAPConfig:
    """Configuration for IMAP email provider.

    Attributes:
        provider: Email provider type (gmail, outlook, or generic)
        host: IMAP server hostname (required for generic provider)
        port: IMAP server port (default 993 for SSL)
        username: Email account username/address
        password: Email account password or app-specific password
        use_ssl: Whether to use SSL/TLS connection (default True)
        folders: List of folders to fetch from (default ["INBOX"])
        from_filter: Optional filter for sender email addresses
        subject_filter: Optional filter for subject line patterns
        timeout: Connection timeout in seconds (default 30)
    """
    provider: Literal["gmail", "outlook", "generic"]
    username: str
    password: str
    host: Optional[str] = None
    port: int = 993
    use_ssl: bool = True
    folders: List[str] = field(default_factory=lambda: ["INBOX"])
    from_filter: Optional[str] = None
    subject_filter: Optional[str] = None
    timeout: int = 30

    def __post_init__(self):
        """Validate configuration and set defaults based on provider."""
        if self.provider == "gmail":
            if not self.host:
                self.host = "imap.gmail.com"
        elif self.provider == "outlook":
            if not self.host:
                self.host = "outlook.office365.com"
        elif self.provider == "generic":
            if not self.host:
                raise ValueError("host is required for generic IMAP provider")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format, excluding sensitive data."""
        return {
            "provider": self.provider,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "use_ssl": self.use_ssl,
            "folders": self.folders,
            "from_filter": self.from_filter,
            "subject_filter": self.subject_filter,
            "timeout": self.timeout,
        }


class EmailProvider(ABC):
    """Abstract base class for email providers.

    Provides a standardized interface for connecting to and fetching emails
    from various email services. All implementations must be read-only and
    never modify or delete emails.

    Example:
        >>> config = IMAPConfig(provider="gmail", username="user@gmail.com", password="app_password")
        >>> provider = GenericIMAPProvider(config)
        >>> provider.connect()
        >>> emails = provider.fetch_emails("INBOX", since=datetime.now() - timedelta(days=7))
        >>> provider.disconnect()
    """

    def __init__(self, config: IMAPConfig):
        """Initialize the provider with configuration.

        Args:
            config: IMAPConfig with connection settings
        """
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the email server.

        Raises:
            IMAPConnectionError: If connection fails
            IMAPAuthError: If authentication fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the email server."""
        pass

    @abstractmethod
    def list_folders(self) -> List[str]:
        """List available folders/mailboxes.

        Returns:
            List of folder names

        Raises:
            IMAPConnectionError: If not connected
        """
        pass

    @abstractmethod
    def fetch_emails(
        self,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
    ) -> List[EmailMessage]:
        """Fetch emails from a folder.

        Args:
            folder: Folder name to fetch from (default "INBOX")
            since: Only return emails after this datetime
            max_items: Maximum number of emails to return

        Returns:
            List of EmailMessage objects

        Raises:
            IMAPFolderError: If folder doesn't exist or cannot be selected
            IMAPConnectionError: If not connected
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if provider is currently connected."""
        return self._connected

    def __enter__(self):
        """Context manager entry - connect to server."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect from server."""
        self.disconnect()
        return False

    def _matches_filter(self, value: str, pattern: str) -> bool:
        """Check if a value matches a filter pattern.

        Supports simple wildcard matching with * for any characters.

        Args:
            value: Value to check
            pattern: Filter pattern (can include * wildcards)

        Returns:
            True if value matches pattern
        """
        import re

        if not pattern:
            return True

        # Convert glob-style pattern to regex
        regex_pattern = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.search(regex_pattern, value, re.IGNORECASE))
