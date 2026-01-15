"""Email provider abstraction for IMAP email sources.

This module provides a standardized interface for fetching emails from various
email providers (Gmail, Outlook, generic IMAP) with read-only access.

Includes OAuth2 support for Gmail and Outlook with secure token storage.
"""
from reconly_core.email.base import (
    EmailProvider,
    EmailMessage,
    IMAPConfig,
)
from reconly_core.email.errors import (
    IMAPError,
    IMAPAuthError,
    IMAPConnectionError,
    IMAPFolderError,
)
from reconly_core.email.generic import GenericIMAPProvider
from reconly_core.email.content import extract_email_content

# OAuth2 providers
from reconly_core.email.gmail import (
    GmailProvider,
    GmailTokens,
    GmailOAuthError,
    generate_gmail_auth_url,
    exchange_gmail_code,
    refresh_gmail_token,
    revoke_gmail_token,
    GMAIL_SCOPES,
)
from reconly_core.email.outlook import (
    OutlookProvider,
    OutlookTokens,
    OutlookOAuthError,
    generate_outlook_auth_url,
    exchange_outlook_code,
    refresh_outlook_token,
    revoke_outlook_token,
    OUTLOOK_SCOPES,
)

# Crypto and OAuth utilities
from reconly_core.email.crypto import (
    TokenEncryptionError,
    encrypt_token,
    decrypt_token,
    encrypt_token_optional,
    decrypt_token_optional,
)
from reconly_core.email.oauth import (
    OAuthState,
    OAuthStateError,
    create_oauth_state,
    validate_oauth_state,
    generate_pkce_pair,
    get_redirect_uri,
)

__all__ = [
    # Base classes
    "EmailProvider",
    "EmailMessage",
    "IMAPConfig",
    # Providers
    "GenericIMAPProvider",
    "GmailProvider",
    "OutlookProvider",
    # Token types
    "GmailTokens",
    "OutlookTokens",
    # Errors
    "IMAPError",
    "IMAPAuthError",
    "IMAPConnectionError",
    "IMAPFolderError",
    "GmailOAuthError",
    "OutlookOAuthError",
    "TokenEncryptionError",
    "OAuthStateError",
    # Gmail OAuth functions
    "generate_gmail_auth_url",
    "exchange_gmail_code",
    "refresh_gmail_token",
    "revoke_gmail_token",
    "GMAIL_SCOPES",
    # Outlook OAuth functions
    "generate_outlook_auth_url",
    "exchange_outlook_code",
    "refresh_outlook_token",
    "revoke_outlook_token",
    "OUTLOOK_SCOPES",
    # Crypto utilities
    "encrypt_token",
    "decrypt_token",
    "encrypt_token_optional",
    "decrypt_token_optional",
    # OAuth utilities
    "OAuthState",
    "create_oauth_state",
    "validate_oauth_state",
    "generate_pkce_pair",
    "get_redirect_uri",
    # Content utilities
    "extract_email_content",
]
