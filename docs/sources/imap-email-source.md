# Email Source Setup Guide

> **Status:** Available in v1.4+
> **Source Type:** `imap`
> **Requires:** IMAP credentials or OAuth2 (Gmail/Outlook)

This guide explains how to configure Reconly to fetch and summarize emails from your inbox using IMAP.

---

## Table of Contents

1. [Overview](#overview)
2. [Provider Options](#provider-options)
3. [Generic IMAP Setup](#generic-imap-setup)
4. [Gmail Setup (OAuth2)](#gmail-setup-oauth2)
5. [Outlook Setup (OAuth2)](#outlook-setup-oauth2)
6. [Configuration Options](#configuration-options)
7. [Filtering Emails](#filtering-emails)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)

---

## Overview

Reconly's IMAP email source allows you to:

- **Fetch emails from multiple providers**: Gmail, Outlook/Microsoft 365, or any generic IMAP server
- **Filter emails**: By sender, subject, or folder
- **Incremental processing**: Only fetch new emails since the last run
- **Read-only access**: Reconly never modifies or deletes your emails
- **Secure authentication**: OAuth2 for Gmail/Outlook, encrypted password storage for generic IMAP

### How It Works

1. Reconly connects to your IMAP server (read-only mode)
2. Fetches emails based on your filter criteria
3. Converts email content to plain text
4. Passes emails to your configured summarizer
5. Tracks processed message IDs to avoid re-processing

---

## Provider Options

Reconly supports three email provider types:

| Provider | Authentication | Best For |
|----------|---------------|----------|
| **Gmail** | OAuth2 (recommended) | Personal Gmail accounts, Google Workspace |
| **Outlook** | OAuth2 (recommended) | Outlook.com, Microsoft 365 |
| **Generic IMAP** | Password/App Password | ProtonMail, FastMail, self-hosted mail servers |

**Recommendation:** Use OAuth2 providers (Gmail/Outlook) when possible for better security and token refresh capabilities.

---

## Generic IMAP Setup

Generic IMAP is suitable for any email provider that supports IMAP access.

### Prerequisites

1. **Enable IMAP access** in your email provider settings
2. **Create an app-specific password** (recommended over using your main password)

### Common IMAP Server Settings

| Provider | IMAP Server | Port | SSL |
|----------|-------------|------|-----|
| **Gmail** | `imap.gmail.com` | 993 | Yes |
| **Outlook** | `outlook.office365.com` | 993 | Yes |
| **Yahoo Mail** | `imap.mail.yahoo.com` | 993 | Yes |
| **ProtonMail** | `127.0.0.1` (Bridge) | 1143 | No |
| **FastMail** | `imap.fastmail.com` | 993 | Yes |
| **iCloud** | `imap.mail.me.com` | 993 | Yes |

### Step-by-Step Configuration

#### 1. Create App Password (Gmail Example)

For Gmail:
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification (if not already enabled)
3. Navigate to **App passwords**
4. Generate a new app password for "Mail"
5. Copy the 16-character password

#### 2. Create IMAP Source in Reconly

**Via UI:**

1. Navigate to **Sources** → **Add Source**
2. Select **Email (IMAP)**
3. Choose **Generic IMAP** as provider
4. Fill in the configuration:
   - **IMAP Server:** `imap.gmail.com`
   - **Port:** `993`
   - **Username:** `your-email@gmail.com`
   - **Password:** (paste app password)
   - **Use SSL/TLS:** Enabled
   - **Folders:** `INBOX` (or comma-separated list)
5. Click **Save**

**Via CLI:**

```bash
reconly source create \
  --name "My Gmail Newsletters" \
  --type imap \
  --config '{
    "imap_provider": "generic",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "imap_username": "your-email@gmail.com",
    "imap_password": "your-app-password",
    "imap_use_ssl": true,
    "imap_folders": ["INBOX"]
  }'
```

**Via Environment Variables:**

```bash
export IMAP_USERNAME="your-email@gmail.com"
export IMAP_PASSWORD="your-app-password"

reconly source create \
  --name "My Emails" \
  --type imap \
  --config '{
    "imap_provider": "generic",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "imap_use_ssl": true,
    "imap_folders": ["INBOX"]
  }'
```

---

## Gmail Setup (OAuth2)

OAuth2 provides secure, token-based authentication without storing passwords.

### Prerequisites

1. **Google Cloud Console project** with Gmail API enabled
2. **OAuth2 credentials** (Client ID and Client Secret)
3. **Redirect URI** configured

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project**
3. Name your project (e.g., "Reconly Email Integration")
4. Click **Create**

### Step 2: Enable Gmail API

1. In your project, navigate to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click **Gmail API** → **Enable**

### Step 3: Create OAuth2 Credentials

1. Navigate to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Configure the OAuth consent screen if prompted:
   - User Type: **External** (or Internal for Workspace)
   - App name: `Reconly`
   - User support email: Your email
   - Add scope: `https://www.googleapis.com/auth/gmail.readonly`
4. Application type: **Web application**
5. Name: `Reconly IMAP Client`
6. **Authorized redirect URIs:**
   - For local development: `http://localhost:8000/api/v1/auth/oauth/callback`
   - For production: `https://your-domain.com/api/v1/auth/oauth/callback`
7. Click **Create**
8. Copy the **Client ID** and **Client Secret**

### Step 4: Configure Reconly

Add to your `.env` file:

```bash
GMAIL_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="your-client-secret"
OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/auth/oauth/callback"
```

### Step 5: Create Gmail Source

**Via UI:**

1. Navigate to **Sources** → **Add Source**
2. Select **Email (IMAP)**
3. Choose **Gmail (OAuth2)**
4. Click **Authorize with Gmail**
5. Complete the OAuth flow in the popup window
6. Grant read-only access to Gmail
7. You'll be redirected back to Reconly
8. Configure folders and filters
9. Click **Save**

**Via API:**

```bash
# 1. Create the source (returns OAuth URL)
curl -X POST http://localhost:8000/api/v1/sources/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gmail Newsletters",
    "source_type": "imap",
    "config": {
      "provider": "gmail",
      "folders": ["INBOX"]
    }
  }'

# Response:
# {
#   "id": 123,
#   "status": "pending_oauth",
#   "oauth_url": "https://accounts.google.com/o/oauth2/auth?..."
# }

# 2. Visit the oauth_url in your browser to complete authentication
# 3. After callback, the source becomes active
```

### OAuth Scopes

Reconly requests **read-only** access:

- `https://www.googleapis.com/auth/gmail.readonly` - Read-only access to emails

**What Reconly CANNOT do with OAuth:**
- Send emails
- Modify or delete emails
- Mark emails as read/unread
- Move emails between folders
- Change Gmail settings

---

## Outlook Setup (OAuth2)

OAuth2 for Microsoft 365 and Outlook.com accounts.

### Prerequisites

1. **Azure AD tenant** (automatic for Microsoft 365 organizations)
2. **App registration** in Azure Portal
3. **Redirect URI** configured

### Step 1: Register Application in Azure

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Configure:
   - Name: `Reconly Email Integration`
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
   - Redirect URI:
     - Platform: **Web**
     - URI: `http://localhost:8000/api/v1/auth/oauth/callback` (or your production URL)
5. Click **Register**

### Step 2: Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Description: `Reconly IMAP Client`
4. Expires: Choose duration (recommended: 24 months)
5. Click **Add**
6. **Copy the secret value immediately** (shown only once)

### Step 3: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Search for and add: `Mail.Read`
6. Click **Add permissions**
7. Optionally, click **Grant admin consent** (if you're an admin)

### Step 4: Configure Reconly

Add to your `.env` file:

```bash
OUTLOOK_CLIENT_ID="your-application-id"
OUTLOOK_CLIENT_SECRET="your-client-secret"
OUTLOOK_TENANT_ID="common"  # or your specific tenant ID
OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/auth/oauth/callback"
```

### Step 5: Create Outlook Source

**Via UI:**

1. Navigate to **Sources** → **Add Source**
2. Select **Email (IMAP)**
3. Choose **Outlook (OAuth2)**
4. Click **Authorize with Microsoft**
5. Sign in with your Microsoft account
6. Grant read-only access to Mail
7. Configure folders and filters
8. Click **Save**

### OAuth Scopes

Reconly requests:

- `Mail.Read` - Read-only access to user's mailbox
- `offline_access` - Refresh token for background fetching

---

## Configuration Options

All email sources support the following configuration options:

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `provider` | Email provider type | `"gmail"`, `"outlook"`, `"generic"` |
| `username` | Email address (generic IMAP only) | `"user@example.com"` |
| `password` | Password or app password (generic IMAP only) | `"abcd efgh ijkl mnop"` |
| `host` | IMAP server hostname (generic IMAP only) | `"imap.gmail.com"` |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `port` | Integer | `993` | IMAP server port (993 for SSL, 143 for non-SSL) |
| `use_ssl` | Boolean | `true` | Use SSL/TLS encryption |
| `folders` | Array | `["INBOX"]` | Folders to fetch emails from |
| `from_filter` | String | `null` | Filter by sender email (supports `*` wildcard) |
| `subject_filter` | String | `null` | Filter by subject (supports `*` wildcard) |
| `timeout` | Integer | `30` | Connection timeout in seconds |

### Environment Variables

For first-run age limiting:

```bash
# Only fetch emails from the last N days on first run
# Prevents fetching hundreds of old emails
IMAP_FIRST_RUN_MAX_AGE_DAYS=7  # Default: 7 days
```

---

## Filtering Emails

Reconly provides multiple filtering mechanisms to process only relevant emails.

### 1. Folder Filtering

Fetch emails from specific folders or labels:

```json
{
  "folders": ["INBOX", "Work", "Newsletters"]
}
```

**Gmail Labels:** Use the label name as it appears in Gmail. For nested labels, use the format: `"Parent/Child"`.

**Outlook Folders:** Use the folder path. For nested folders: `"Inbox/Project A"`.

### 2. Sender Filtering

Only process emails from specific senders:

```json
{
  "from_filter": "*@newsletter.com"
}
```

**Examples:**
- `"user@example.com"` - Exact match
- `"*@newsletter.com"` - All emails from newsletter.com domain
- `"*weekly*"` - Any sender containing "weekly"

### 3. Subject Filtering

Only process emails with specific subjects:

```json
{
  "subject_filter": "*Weekly Report*"
}
```

**Examples:**
- `"Daily Digest"` - Exact match
- `"*Report*"` - Contains "Report"
- `"Weekly*"` - Starts with "Weekly"

### 4. Combined Filtering

Use multiple filters together:

```json
{
  "folders": ["INBOX"],
  "from_filter": "*@news.example.com",
  "subject_filter": "*Digest*"
}
```

This fetches only emails from the INBOX folder, sent by news.example.com, with "Digest" in the subject.

### 5. Date-Based Filtering

Automatically handled by Reconly:

- **First run:** Fetches emails from the last 7 days (configurable via `IMAP_FIRST_RUN_MAX_AGE_DAYS`)
- **Subsequent runs:** Only fetches emails since the last successful fetch
- **Deduplication:** Tracks processed message IDs to avoid re-processing

---

## Troubleshooting

### Authentication Failed

**Symptoms:**
```
IMAPAuthError: Authentication failed for user@example.com
```

**Solutions:**

1. **Verify credentials:**
   - Double-check username and password
   - Ensure you're using an app-specific password, not your main password

2. **Check IMAP access:**
   - Gmail: [Enable IMAP](https://mail.google.com/mail/u/0/#settings/fwdandpop)
   - Outlook: IMAP is enabled by default
   - Other providers: Check settings for IMAP enable toggle

3. **Two-factor authentication:**
   - You MUST use an app password if 2FA is enabled
   - Regular passwords won't work with 2FA enabled

4. **OAuth token expired (Gmail/Outlook):**
   - Click the "Re-authenticate" button in the source settings
   - Reconly will automatically refresh tokens, but manual re-auth may be needed if refresh token expires

### Connection Timeout

**Symptoms:**
```
IMAPConnectionError: Connection timeout after 30 seconds
```

**Solutions:**

1. **Check firewall:** Ensure outbound connections to port 993 are allowed
2. **Verify server address:** Confirm IMAP server hostname is correct
3. **Try without SSL:** Some servers use non-SSL port 143 (not recommended)
4. **Increase timeout:**
   ```json
   {
     "timeout": 60
   }
   ```

### Folder Not Found

**Symptoms:**
```
IMAPFolderError: Folder 'Label_123' not found
```

**Solutions:**

1. **List available folders:**
   - Use the "Test Connection" feature in the UI
   - Or check your email client for exact folder names

2. **Gmail labels:**
   - Labels are prefixed with `INBOX/` or `[Gmail]/`
   - Example: `"INBOX/Work"` instead of `"Work"`
   - Use the Gmail web interface to see the exact folder structure

3. **Case sensitivity:**
   - Folder names are case-sensitive: `"INBOX"` ≠ `"inbox"`

### No Emails Fetched

**Symptoms:**
Source runs successfully but returns 0 emails.

**Solutions:**

1. **Check date filter:**
   - First run only fetches last 7 days
   - Adjust `IMAP_FIRST_RUN_MAX_AGE_DAYS` if needed

2. **Verify filters:**
   - Temporarily remove `from_filter` and `subject_filter`
   - Check if emails appear

3. **Folder selection:**
   - Ensure emails exist in the specified folders
   - Try fetching from `INBOX` first

### OAuth Errors

**Gmail: `invalid_grant` error**

- Your refresh token expired (happens after 6 months of inactivity)
- Solution: Re-authenticate via the UI

**Outlook: `AADSTS50011` error**

- Redirect URI mismatch
- Solution: Ensure the redirect URI in Azure matches exactly (including trailing slashes)

**OAuth popup blocked**

- Browser blocked the popup window
- Solution: Allow popups from Reconly's domain

---

## Security Considerations

### Read-Only Guarantee

Reconly operates in **strict read-only mode**:

- **Gmail OAuth scope:** `gmail.readonly` (no write access)
- **Outlook OAuth scope:** `Mail.Read` (no write access)
- **IMAP commands:** Only uses `FETCH` (no `STORE`, `DELETE`, `COPY`)

Reconly **CANNOT:**
- Send emails
- Delete or move emails
- Mark emails as read/unread
- Modify email flags or labels
- Change mailbox settings

### Credential Storage

**OAuth Tokens:**
- Stored encrypted in the database using Fernet (symmetric encryption)
- Encryption key derived from `SECRET_KEY` environment variable
- Tokens never appear in logs or API responses

**IMAP Passwords:**
- Encrypted using the same Fernet mechanism
- Only decrypted in memory during fetch operations
- Not included in API responses

**Best Practices:**
1. Use OAuth2 when possible (no password storage)
2. Use app-specific passwords for generic IMAP (never your main password)
3. Rotate `SECRET_KEY` periodically (requires re-authentication)
4. Use environment variables for credentials when feasible

### Network Security

- **SSL/TLS:** Enabled by default (port 993)
- **Certificate verification:** Enabled for all connections
- **No plaintext:** Passwords never transmitted unencrypted

### OAuth Token Refresh

- **Access tokens:** Short-lived (1 hour for Gmail/Outlook)
- **Refresh tokens:** Long-lived, automatically refreshed by Reconly
- **Token rotation:** Happens transparently in the background
- **Expiration handling:** Automatic re-authentication prompts if refresh fails

---

## Advanced Usage

### Processing Multiple Accounts

Create separate sources for each email account:

```bash
# Personal Gmail
reconly source create --name "Personal Gmail" --type imap --config '{"provider":"gmail",...}'

# Work Outlook
reconly source create --name "Work Email" --type imap --config '{"provider":"outlook",...}'

# Newsletter account
reconly source create --name "Newsletters" --type imap --config '{"provider":"generic",...}'
```

### Incremental Fetching

Reconly automatically tracks processed emails:

1. **Message ID tracking:** Stores last 1000 processed message IDs
2. **Circular buffer:** Automatically removes oldest IDs when limit reached
3. **Deduplication:** Filters out previously processed emails
4. **Date filtering:** Only fetches emails since last run

### Custom Fetch Schedule

Configure per-source schedules:

```json
{
  "schedule": "*/30 * * * *"  // Every 30 minutes
}
```

### Integration with Feeds

Combine email sources with summarization:

1. Create IMAP source
2. Create a feed referencing the source
3. Configure summarization prompt
4. Set output exporter (email, webhook, etc.)

---

## Related Documentation

- [Adding Custom Fetchers](../ADDING_FETCHERS.md) - Extend email provider support
- [Data Flow Architecture](../architecture/data-flow.md) - How emails flow through the system
- [Security Documentation](../SECURITY.md) - Comprehensive security details

---

## Support

**Issues:**
- Check [GitHub Issues](https://github.com/yourusername/reconly/issues) for known problems
- Search for `IMAPError` or `OAuth` related issues

**Contributing:**
- Submit pull requests to add new email provider support
- See [ADDING_FETCHERS.md](../ADDING_FETCHERS.md) for implementation guide
