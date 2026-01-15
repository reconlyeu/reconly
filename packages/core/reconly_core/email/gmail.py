"""Gmail OAuth2 email provider implementation.

This module provides Gmail email fetching via the Gmail API with OAuth2
authentication. It's more reliable than IMAP for OAuth2 flows.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from reconly_core.email.base import EmailMessage, EmailProvider, IMAPConfig
from reconly_core.email.content import extract_email_content
from reconly_core.email.errors import (
    IMAPAuthError,
    IMAPConnectionError,
    IMAPFetchError,
)

logger = logging.getLogger(__name__)

# Gmail OAuth2 configuration
GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"

# Gmail OAuth2 scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


class GmailOAuthError(Exception):
    """Raised when Gmail OAuth operations fail."""
    pass


@dataclass
class GmailTokens:
    """Gmail OAuth2 tokens.

    Attributes:
        access_token: The access token for API calls
        refresh_token: The refresh token for getting new access tokens
        expires_at: When the access token expires
        scopes: The granted OAuth scopes
    """
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    scopes: List[str]


def get_gmail_client_credentials() -> Tuple[str, str]:
    """Get Gmail OAuth2 client credentials from environment.

    Returns:
        Tuple of (client_id, client_secret)

    Raises:
        GmailOAuthError: If credentials are not configured
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise GmailOAuthError(
            "Gmail OAuth credentials not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )

    return client_id, client_secret


def generate_gmail_auth_url(
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    """Generate the Gmail OAuth2 authorization URL.

    Args:
        redirect_uri: The OAuth callback URL
        state: Encrypted state parameter for CSRF protection
        code_challenge: PKCE code challenge

    Returns:
        The authorization URL to redirect the user to
    """
    client_id, _ = get_gmail_client_credentials()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Always show consent screen for refresh token
    }

    return f"{GMAIL_AUTH_URL}?{urlencode(params)}"


def exchange_gmail_code(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> GmailTokens:
    """Exchange authorization code for tokens.

    Args:
        code: The authorization code from OAuth callback
        redirect_uri: The OAuth callback URL (must match authorize request)
        code_verifier: PKCE code verifier

    Returns:
        GmailTokens with access and refresh tokens

    Raises:
        GmailOAuthError: If token exchange fails
    """
    client_id, client_secret = get_gmail_client_credentials()

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(
            GMAIL_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
            logger.error(f"Gmail token exchange failed: {error_msg}")
            raise GmailOAuthError(f"Token exchange failed: {error_msg}")

        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return GmailTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scopes=token_data.get("scope", "").split(),
        )

    except requests.RequestException as e:
        logger.error(f"Gmail token exchange request failed: {e}")
        raise GmailOAuthError(f"Network error during token exchange: {e}") from e
    except GmailOAuthError:
        raise
    except Exception as e:
        logger.error(f"Gmail token exchange failed: {e}")
        raise GmailOAuthError(f"Failed to exchange authorization code: {e}") from e


def refresh_gmail_token(refresh_token: str) -> GmailTokens:
    """Refresh an expired access token.

    Args:
        refresh_token: The refresh token

    Returns:
        GmailTokens with new access token

    Raises:
        GmailOAuthError: If token refresh fails
    """
    client_id, client_secret = get_gmail_client_credentials()

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        response = requests.post(
            GMAIL_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
            logger.error(f"Gmail token refresh failed: {error_msg}")
            raise GmailOAuthError(f"Token refresh failed: {error_msg}")

        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return GmailTokens(
            access_token=token_data["access_token"],
            # Refresh token may not be included in refresh response
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_at=expires_at,
            scopes=token_data.get("scope", "").split(),
        )

    except requests.RequestException as e:
        logger.error(f"Gmail token refresh request failed: {e}")
        raise GmailOAuthError(f"Network error during token refresh: {e}") from e
    except GmailOAuthError:
        raise
    except Exception as e:
        logger.error(f"Gmail token refresh failed: {e}")
        raise GmailOAuthError(f"Failed to refresh token: {e}") from e


def revoke_gmail_token(token: str) -> bool:
    """Revoke a Gmail OAuth token.

    Args:
        token: The access or refresh token to revoke

    Returns:
        True if revocation succeeded
    """
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/revoke",
            data={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to revoke Gmail token: {e}")
        return False


class GmailProvider(EmailProvider):
    """Gmail email provider using Gmail API with OAuth2.

    This provider uses the Gmail API instead of IMAP for better reliability
    with OAuth2 authentication. It fetches emails in read-only mode.

    Example:
        >>> tokens = GmailTokens(access_token="...", refresh_token="...", ...)
        >>> provider = GmailProvider(tokens=tokens, folders=["INBOX"])
        >>> with provider:
        ...     emails = provider.fetch_emails("INBOX", max_items=10)
    """

    def __init__(
        self,
        tokens: GmailTokens,
        folders: Optional[List[str]] = None,
        from_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        on_token_refresh: Optional[callable] = None,
    ):
        """Initialize the Gmail provider.

        Args:
            tokens: GmailTokens with OAuth credentials
            folders: List of label/folder names to fetch from (default: ["INBOX"])
            from_filter: Optional filter for sender email addresses
            subject_filter: Optional filter for subject line patterns
            on_token_refresh: Callback function when tokens are refreshed
                              Signature: (new_tokens: GmailTokens) -> None
        """
        # Create a minimal IMAPConfig for base class compatibility
        config = IMAPConfig(
            provider="gmail",
            username="oauth2",  # Placeholder
            password="oauth2",  # Placeholder
            folders=folders or ["INBOX"],
            from_filter=from_filter,
            subject_filter=subject_filter,
        )
        super().__init__(config)

        self._tokens = tokens
        self._session: Optional[requests.Session] = None
        self._on_token_refresh = on_token_refresh

    @property
    def tokens(self) -> GmailTokens:
        """Get current tokens."""
        return self._tokens

    def connect(self) -> None:
        """Initialize the API session.

        Raises:
            IMAPConnectionError: If connection fails
            IMAPAuthError: If authentication fails
        """
        if self._connected and self._session:
            return

        try:
            # Check if token needs refresh
            if self._tokens.expires_at and self._tokens.expires_at <= datetime.utcnow():
                if self._tokens.refresh_token:
                    self._refresh_tokens()
                else:
                    raise IMAPAuthError("Access token expired and no refresh token available")

            # Create session with auth header
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._tokens.access_token}",
            })

            # Verify the token works
            response = self._session.get(
                f"{GMAIL_API_BASE}/users/me/profile",
                timeout=10,
            )

            if response.status_code == 401:
                # Try refresh
                if self._tokens.refresh_token:
                    self._refresh_tokens()
                    self._session.headers.update({
                        "Authorization": f"Bearer {self._tokens.access_token}",
                    })
                    # Retry
                    response = self._session.get(
                        f"{GMAIL_API_BASE}/users/me/profile",
                        timeout=10,
                    )

            if response.status_code != 200:
                raise IMAPAuthError(
                    f"Gmail API authentication failed: {response.status_code}",
                    details=response.text,
                )

            self._connected = True
            profile = response.json()
            logger.info(f"Connected to Gmail API as {profile.get('emailAddress')}")

        except IMAPAuthError:
            raise
        except GmailOAuthError as e:
            raise IMAPAuthError(str(e))
        except requests.RequestException as e:
            raise IMAPConnectionError(f"Failed to connect to Gmail API: {e}")
        except Exception as e:
            raise IMAPConnectionError(f"Gmail connection failed: {e}")

    def disconnect(self) -> None:
        """Close the API session."""
        if self._session:
            self._session.close()
            self._session = None
        self._connected = False
        logger.debug("Disconnected from Gmail API")

    def _refresh_tokens(self) -> None:
        """Refresh the access token."""
        if not self._tokens.refresh_token:
            raise GmailOAuthError("No refresh token available")

        logger.debug("Refreshing Gmail access token")
        new_tokens = refresh_gmail_token(self._tokens.refresh_token)
        self._tokens = new_tokens

        # Update session header
        if self._session:
            self._session.headers.update({
                "Authorization": f"Bearer {self._tokens.access_token}",
            })

        # Notify callback
        if self._on_token_refresh:
            try:
                self._on_token_refresh(new_tokens)
            except Exception as e:
                logger.warning(f"Token refresh callback failed: {e}")

    def list_folders(self) -> List[str]:
        """List available Gmail labels.

        Returns:
            List of label names

        Raises:
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            response = self._session.get(
                f"{GMAIL_API_BASE}/users/me/labels",
                timeout=30,
            )

            if response.status_code != 200:
                raise IMAPFetchError(f"Failed to list labels: {response.status_code}")

            labels_data = response.json()
            return [label["name"] for label in labels_data.get("labels", [])]

        except requests.RequestException as e:
            raise IMAPFetchError(f"Failed to list labels: {e}")

    def fetch_emails(
        self,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
    ) -> List[EmailMessage]:
        """Fetch emails from a Gmail label.

        Args:
            folder: Label name to fetch from (default "INBOX")
            since: Only return emails after this datetime
            max_items: Maximum number of emails to return

        Returns:
            List of EmailMessage objects, sorted by date (newest first)

        Raises:
            IMAPFetchError: If fetch fails
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            # Build query
            query_parts = [f"in:{folder}"]

            if since:
                # Gmail uses YYYY/MM/DD format for after: query
                date_str = since.strftime("%Y/%m/%d")
                query_parts.append(f"after:{date_str}")

            query = " ".join(query_parts)

            # Get message list
            params = {
                "q": query,
                "maxResults": min(max_items or 100, 100),  # Gmail API max is 100
            }

            response = self._session.get(
                f"{GMAIL_API_BASE}/users/me/messages",
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                raise IMAPFetchError(f"Failed to fetch messages: {response.status_code}")

            messages_data = response.json()
            message_ids = [msg["id"] for msg in messages_data.get("messages", [])]

            logger.debug(f"Found {len(message_ids)} messages in {folder}")

            if not message_ids:
                return []

            # Limit to max_items
            if max_items and len(message_ids) > max_items:
                message_ids = message_ids[:max_items]

            # Fetch full message details
            emails = []
            for msg_id in message_ids:
                try:
                    email_msg = self._fetch_message(msg_id, folder)
                    if email_msg:
                        # Apply from_filter
                        if self.config.from_filter:
                            if not self._matches_filter(
                                email_msg.sender, self.config.from_filter
                            ):
                                continue

                        # Apply subject_filter
                        if self.config.subject_filter:
                            if not self._matches_filter(
                                email_msg.subject, self.config.subject_filter
                            ):
                                continue

                        emails.append(email_msg)

                except Exception as e:
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")
                    continue

            # Sort by date (newest first)
            emails.sort(key=lambda e: e.date or datetime.min, reverse=True)

            logger.info(f"Fetched {len(emails)} emails from {folder}")
            return emails

        except requests.RequestException as e:
            raise IMAPFetchError(f"Failed to fetch emails: {e}")

    def _ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if not self._connected or not self._session:
            raise IMAPConnectionError("Not connected to Gmail API")

    def _fetch_message(self, message_id: str, folder: str) -> Optional[EmailMessage]:
        """Fetch a single message by ID.

        Args:
            message_id: Gmail message ID
            folder: The folder/label name

        Returns:
            Parsed EmailMessage or None if parsing fails
        """
        response = self._session.get(
            f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
            params={"format": "full"},
            timeout=30,
        )

        if response.status_code != 200:
            return None

        msg_data = response.json()
        return self._parse_message(msg_data, folder)

    def _parse_message(self, msg_data: Dict[str, Any], folder: str) -> EmailMessage:
        """Parse Gmail API message data into EmailMessage.

        Args:
            msg_data: Gmail API message response
            folder: The folder/label name

        Returns:
            Parsed EmailMessage
        """
        headers = {}
        for header in msg_data.get("payload", {}).get("headers", []):
            headers[header["name"].lower()] = header["value"]

        # Extract message ID
        message_id = headers.get("message-id", msg_data.get("id", ""))
        if message_id:
            message_id = message_id.strip("<>")

        # Extract subject
        subject = headers.get("subject", "")

        # Extract sender
        from_header = headers.get("from", "")
        sender_name, sender_addr = self._parse_email_address(from_header)

        # Extract recipients
        to_header = headers.get("to", "")
        recipients = []
        if to_header:
            for addr in to_header.split(","):
                _, email_addr = self._parse_email_address(addr.strip())
                if email_addr:
                    recipients.append(email_addr)

        # Extract date
        date = None
        date_header = headers.get("date")
        if date_header:
            try:
                date = parsedate_to_datetime(date_header)
            except Exception:
                pass

        # Extract body
        text_content, html_content = self._extract_body(msg_data.get("payload", {}))

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
            metadata={"gmail_id": msg_data.get("id")},
        )

    def _parse_email_address(self, address: str) -> Tuple[Optional[str], str]:
        """Parse an email address with optional display name.

        Args:
            address: Email address like "Name <email@example.com>"

        Returns:
            Tuple of (display_name, email_address)
        """
        import re

        # Try to match "Name <email>" format
        match = re.match(r'"?([^"<]*)"?\s*<([^>]+)>', address)
        if match:
            name = match.group(1).strip()
            email = match.group(2).strip()
            return (name if name else None, email)

        # Just an email address
        return (None, address.strip())

    def _extract_body(self, payload: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Extract text and HTML body from Gmail message payload.

        Args:
            payload: Gmail API message payload

        Returns:
            Tuple of (text_content, html_content)
        """
        text_content = ""
        html_content = None

        mime_type = payload.get("mimeType", "")

        if mime_type.startswith("multipart/"):
            # Recursively process parts
            for part in payload.get("parts", []):
                part_text, part_html = self._extract_body(part)
                if part_text and not text_content:
                    text_content = part_text
                if part_html and not html_content:
                    html_content = part_html

        elif mime_type == "text/plain":
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                text_content = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        elif mime_type == "text/html":
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                html_content = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        return text_content, html_content
