"""Outlook/Microsoft 365 OAuth2 email provider implementation.

This module provides Outlook email fetching via Microsoft Graph API with OAuth2
authentication. It supports both personal Microsoft accounts and work/school accounts.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
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

# Microsoft OAuth2 configuration
# Using /common endpoint to support both personal and work/school accounts
MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Microsoft Graph API scopes
OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "offline_access",  # For refresh tokens
]


class OutlookOAuthError(Exception):
    """Raised when Outlook OAuth operations fail."""
    pass


@dataclass
class OutlookTokens:
    """Outlook OAuth2 tokens.

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


def get_outlook_client_credentials() -> Tuple[str, str]:
    """Get Microsoft OAuth2 client credentials from environment.

    Returns:
        Tuple of (client_id, client_secret)

    Raises:
        OutlookOAuthError: If credentials are not configured
    """
    client_id = os.environ.get("MICROSOFT_CLIENT_ID")
    client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise OutlookOAuthError(
            "Microsoft OAuth credentials not configured. "
            "Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET environment variables."
        )

    return client_id, client_secret


def generate_outlook_auth_url(
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    """Generate the Microsoft OAuth2 authorization URL.

    Args:
        redirect_uri: The OAuth callback URL
        state: Encrypted state parameter for CSRF protection
        code_challenge: PKCE code challenge

    Returns:
        The authorization URL to redirect the user to
    """
    client_id, _ = get_outlook_client_credentials()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(OUTLOOK_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "response_mode": "query",
        "prompt": "consent",  # Always show consent for refresh token
    }

    return f"{MICROSOFT_AUTH_URL}?{urlencode(params)}"


def exchange_outlook_code(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> OutlookTokens:
    """Exchange authorization code for tokens.

    Args:
        code: The authorization code from OAuth callback
        redirect_uri: The OAuth callback URL (must match authorize request)
        code_verifier: PKCE code verifier

    Returns:
        OutlookTokens with access and refresh tokens

    Raises:
        OutlookOAuthError: If token exchange fails
    """
    client_id, client_secret = get_outlook_client_credentials()

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
            MICROSOFT_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
            logger.error(f"Outlook token exchange failed: {error_msg}")
            raise OutlookOAuthError(f"Token exchange failed: {error_msg}")

        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return OutlookTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scopes=token_data.get("scope", "").split(),
        )

    except requests.RequestException as e:
        logger.error(f"Outlook token exchange request failed: {e}")
        raise OutlookOAuthError(f"Network error during token exchange: {e}") from e
    except OutlookOAuthError:
        raise
    except Exception as e:
        logger.error(f"Outlook token exchange failed: {e}")
        raise OutlookOAuthError(f"Failed to exchange authorization code: {e}") from e


def refresh_outlook_token(refresh_token: str) -> OutlookTokens:
    """Refresh an expired access token.

    Args:
        refresh_token: The refresh token

    Returns:
        OutlookTokens with new access token

    Raises:
        OutlookOAuthError: If token refresh fails
    """
    client_id, client_secret = get_outlook_client_credentials()

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(OUTLOOK_SCOPES),
    }

    try:
        response = requests.post(
            MICROSOFT_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
            logger.error(f"Outlook token refresh failed: {error_msg}")
            raise OutlookOAuthError(f"Token refresh failed: {error_msg}")

        token_data = response.json()

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return OutlookTokens(
            access_token=token_data["access_token"],
            # Refresh token may be rotated
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_at=expires_at,
            scopes=token_data.get("scope", "").split(),
        )

    except requests.RequestException as e:
        logger.error(f"Outlook token refresh request failed: {e}")
        raise OutlookOAuthError(f"Network error during token refresh: {e}") from e
    except OutlookOAuthError:
        raise
    except Exception as e:
        logger.error(f"Outlook token refresh failed: {e}")
        raise OutlookOAuthError(f"Failed to refresh token: {e}") from e


def revoke_outlook_token(token: str) -> bool:
    """Revoke an Outlook OAuth token.

    Note: Microsoft doesn't have a standard revocation endpoint for user tokens.
    The token will expire naturally. This function is provided for API consistency.

    Args:
        token: The access or refresh token to revoke

    Returns:
        True (Microsoft tokens cannot be explicitly revoked via API)
    """
    logger.info("Outlook token revocation requested - tokens will expire naturally")
    return True


class OutlookProvider(EmailProvider):
    """Outlook email provider using Microsoft Graph API with OAuth2.

    This provider uses the Microsoft Graph API for reliable OAuth2-based
    email access. It supports both personal and work/school accounts.

    Example:
        >>> tokens = OutlookTokens(access_token="...", refresh_token="...", ...)
        >>> provider = OutlookProvider(tokens=tokens, folders=["Inbox"])
        >>> with provider:
        ...     emails = provider.fetch_emails("Inbox", max_items=10)
    """

    def __init__(
        self,
        tokens: OutlookTokens,
        folders: Optional[List[str]] = None,
        from_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        on_token_refresh: Optional[callable] = None,
    ):
        """Initialize the Outlook provider.

        Args:
            tokens: OutlookTokens with OAuth credentials
            folders: List of folder names to fetch from (default: ["Inbox"])
            from_filter: Optional filter for sender email addresses
            subject_filter: Optional filter for subject line patterns
            on_token_refresh: Callback function when tokens are refreshed
                              Signature: (new_tokens: OutlookTokens) -> None
        """
        # Create a minimal IMAPConfig for base class compatibility
        config = IMAPConfig(
            provider="outlook",
            username="oauth2",  # Placeholder
            password="oauth2",  # Placeholder
            folders=folders or ["Inbox"],
            from_filter=from_filter,
            subject_filter=subject_filter,
        )
        super().__init__(config)

        self._tokens = tokens
        self._session: Optional[requests.Session] = None
        self._on_token_refresh = on_token_refresh

    @property
    def tokens(self) -> OutlookTokens:
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
                "Content-Type": "application/json",
            })

            # Verify the token works
            response = self._session.get(
                f"{GRAPH_API_BASE}/me",
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
                        f"{GRAPH_API_BASE}/me",
                        timeout=10,
                    )

            if response.status_code != 200:
                raise IMAPAuthError(
                    f"Microsoft Graph API authentication failed: {response.status_code}",
                    details=response.text,
                )

            self._connected = True
            profile = response.json()
            email = profile.get("mail") or profile.get("userPrincipalName", "unknown")
            logger.info(f"Connected to Microsoft Graph API as {email}")

        except IMAPAuthError:
            raise
        except OutlookOAuthError as e:
            raise IMAPAuthError(str(e))
        except requests.RequestException as e:
            raise IMAPConnectionError(f"Failed to connect to Microsoft Graph API: {e}")
        except Exception as e:
            raise IMAPConnectionError(f"Outlook connection failed: {e}")

    def disconnect(self) -> None:
        """Close the API session."""
        if self._session:
            self._session.close()
            self._session = None
        self._connected = False
        logger.debug("Disconnected from Microsoft Graph API")

    def _refresh_tokens(self) -> None:
        """Refresh the access token."""
        if not self._tokens.refresh_token:
            raise OutlookOAuthError("No refresh token available")

        logger.debug("Refreshing Outlook access token")
        new_tokens = refresh_outlook_token(self._tokens.refresh_token)
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
        """List available mail folders.

        Returns:
            List of folder names

        Raises:
            IMAPConnectionError: If not connected
        """
        self._ensure_connected()

        try:
            response = self._session.get(
                f"{GRAPH_API_BASE}/me/mailFolders",
                timeout=30,
            )

            if response.status_code != 200:
                raise IMAPFetchError(f"Failed to list folders: {response.status_code}")

            folders_data = response.json()
            return [folder["displayName"] for folder in folders_data.get("value", [])]

        except requests.RequestException as e:
            raise IMAPFetchError(f"Failed to list folders: {e}")

    def fetch_emails(
        self,
        folder: str = "Inbox",
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
    ) -> List[EmailMessage]:
        """Fetch emails from an Outlook folder.

        Args:
            folder: Folder name to fetch from (default "Inbox")
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
            # Get folder ID by name
            folder_id = self._get_folder_id(folder)
            if not folder_id:
                raise IMAPFetchError(f"Folder not found: {folder}")

            # Build query parameters
            params = {
                "$select": "id,subject,from,toRecipients,receivedDateTime,body,bodyPreview",
                "$orderby": "receivedDateTime desc",
                "$top": min(max_items or 100, 100),  # Graph API max per request
            }

            # Add date filter if specified
            if since:
                # Microsoft Graph uses ISO 8601 format
                date_str = since.isoformat() + "Z"
                params["$filter"] = f"receivedDateTime ge {date_str}"

            response = self._session.get(
                f"{GRAPH_API_BASE}/me/mailFolders/{folder_id}/messages",
                params=params,
                timeout=30,
            )

            if response.status_code != 200:
                raise IMAPFetchError(f"Failed to fetch messages: {response.status_code}")

            messages_data = response.json()
            messages = messages_data.get("value", [])

            logger.debug(f"Found {len(messages)} messages in {folder}")

            emails = []
            for msg_data in messages:
                try:
                    email_msg = self._parse_message(msg_data, folder)
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
                    logger.warning(f"Failed to parse message: {e}")
                    continue

            # Sort by date (newest first) - should already be sorted but ensure
            emails.sort(key=lambda e: e.date or datetime.min, reverse=True)

            logger.info(f"Fetched {len(emails)} emails from {folder}")
            return emails

        except requests.RequestException as e:
            raise IMAPFetchError(f"Failed to fetch emails: {e}")

    def _ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if not self._connected or not self._session:
            raise IMAPConnectionError("Not connected to Microsoft Graph API")

    def _get_folder_id(self, folder_name: str) -> Optional[str]:
        """Get folder ID by display name.

        Args:
            folder_name: The folder display name

        Returns:
            The folder ID or None if not found
        """
        # Well-known folder names can be used directly
        well_known = {
            "inbox": "inbox",
            "drafts": "drafts",
            "sentitems": "sentItems",
            "sent items": "sentItems",
            "deleteditems": "deletedItems",
            "deleted items": "deletedItems",
            "junkemail": "junkemail",
            "junk email": "junkemail",
            "junk": "junkemail",
            "archive": "archive",
        }

        folder_lower = folder_name.lower()
        if folder_lower in well_known:
            return well_known[folder_lower]

        # Otherwise, list folders and find by name
        try:
            response = self._session.get(
                f"{GRAPH_API_BASE}/me/mailFolders",
                params={"$filter": f"displayName eq '{folder_name}'"},
                timeout=30,
            )

            if response.status_code == 200:
                folders = response.json().get("value", [])
                if folders:
                    return folders[0]["id"]

        except Exception as e:
            logger.warning(f"Failed to get folder ID for '{folder_name}': {e}")

        return None

    def _parse_message(self, msg_data: Dict[str, Any], folder: str) -> EmailMessage:
        """Parse Graph API message data into EmailMessage.

        Args:
            msg_data: Graph API message response
            folder: The folder name

        Returns:
            Parsed EmailMessage
        """
        # Extract message ID
        message_id = msg_data.get("internetMessageId", msg_data.get("id", ""))
        if message_id:
            message_id = message_id.strip("<>")

        # Extract subject
        subject = msg_data.get("subject", "")

        # Extract sender
        from_data = msg_data.get("from", {}).get("emailAddress", {})
        sender_addr = from_data.get("address", "")
        sender_name = from_data.get("name")

        # Extract recipients
        recipients = []
        for recipient in msg_data.get("toRecipients", []):
            email_addr = recipient.get("emailAddress", {}).get("address")
            if email_addr:
                recipients.append(email_addr)

        # Extract date
        date = None
        date_str = msg_data.get("receivedDateTime")
        if date_str:
            try:
                # Parse ISO 8601 format
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # Extract body
        body = msg_data.get("body", {})
        body_content = body.get("content", "")
        body_type = body.get("contentType", "").lower()

        if body_type == "html":
            html_content = body_content
            text_content = extract_email_content(html_content)
        else:
            text_content = body_content
            html_content = None

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
            metadata={"outlook_id": msg_data.get("id")},
        )
