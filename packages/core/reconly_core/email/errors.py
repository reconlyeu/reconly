"""Error classes for IMAP email operations.

This module defines a hierarchy of exceptions for handling various
IMAP-related errors.
"""


class IMAPError(Exception):
    """Base exception for all IMAP-related errors.

    Attributes:
        message: Human-readable error message
        details: Optional additional details about the error
    """

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the full error message."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class IMAPAuthError(IMAPError):
    """Authentication failure when connecting to IMAP server.

    Raised when login credentials are rejected by the server.
    Common causes:
    - Invalid username or password
    - App-specific password required (Gmail, Outlook)
    - Account locked or disabled
    - Two-factor authentication not configured properly
    """

    def __init__(self, message: str = "Authentication failed", details: str | None = None):
        super().__init__(message, details)


class IMAPConnectionError(IMAPError):
    """Connection failure to IMAP server.

    Raised when the client cannot establish a connection to the server.
    Common causes:
    - Server hostname is incorrect
    - Port is blocked or incorrect
    - SSL/TLS configuration mismatch
    - Network timeout
    - Server is unavailable
    """

    def __init__(self, message: str = "Connection failed", details: str | None = None):
        super().__init__(message, details)


class IMAPFolderError(IMAPError):
    """Error related to IMAP folder operations.

    Raised when folder operations fail.
    Common causes:
    - Folder doesn't exist
    - Folder name is invalid
    - Insufficient permissions to access folder
    - Folder is locked by another client
    """

    def __init__(self, message: str = "Folder operation failed", details: str | None = None):
        super().__init__(message, details)


class IMAPFetchError(IMAPError):
    """Error when fetching email messages.

    Raised when email retrieval operations fail.
    Common causes:
    - Message has been deleted
    - Server timeout during fetch
    - Invalid message ID
    - Malformed email data
    """

    def __init__(self, message: str = "Failed to fetch email", details: str | None = None):
        super().__init__(message, details)


class IMAPParseError(IMAPError):
    """Error when parsing email content.

    Raised when email parsing operations fail.
    Common causes:
    - Malformed email headers
    - Invalid encoding
    - Corrupted message body
    - Unsupported content type
    """

    def __init__(self, message: str = "Failed to parse email", details: str | None = None):
        super().__init__(message, details)
