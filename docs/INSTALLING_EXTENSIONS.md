# Installing Reconly Extensions

This guide explains how to install, configure, and manage extensions in Reconly.

## Overview

Extensions add new capabilities to Reconly:
- **Exporters** - Export digests to new formats (Obsidian, Notion, etc.)
- **Fetchers** - Fetch content from new sources (Reddit, HackerNews, etc.)
- **Providers** - LLM providers (coming soon)

## Installing Extensions

### Via the Catalog (Recommended)

1. Open Reconly
2. Go to **Settings > Extensions**
3. Click **Browse Catalog**
4. Search for the extension you want
5. Click **Install**
6. Restart Reconly when prompted

The catalog shows extensions that have been reviewed and listed by the Reconly community.

### Via pip (Manual)

Extensions are standard Python packages. Install directly with pip:

```bash
pip install reconly-ext-notion
```

Then restart Reconly.

**For development versions:**

```bash
pip install git+https://github.com/author/reconly-ext-myformat.git
```

**For local development:**

```bash
cd /path/to/reconly-ext-myformat
pip install -e .
```

---

## Configuring Extensions

After installation, extensions may need configuration before they can be used.

### Configuration States

| Status | Description |
|--------|-------------|
| **Active** | Ready to use |
| **Needs Config** | Missing required settings |
| **Disabled** | Turned off by user |

### Configuration Steps

1. Go to **Settings > Extensions**
2. Find the extension
3. Click **Configure**
4. Fill in required fields (marked with *)
5. Click **Save**

Once all required fields are filled, the extension activates automatically.

### Common Configuration Fields

**API Keys:**
Some extensions require API keys from external services. These are typically marked as "required" and may need to be set via environment variables for security.

**Output Paths:**
Exporter extensions often require a path where files should be saved (e.g., Obsidian vault path).

**Credentials:**
For security, some fields (like passwords, API secrets) can only be configured via environment variables, not through the UI.

---

## Managing Extensions

### Enable/Disable

Toggle extensions on or off:

1. Go to **Settings > Extensions**
2. Use the toggle switch to enable/disable

Disabled extensions:
- Remain installed
- Don't appear in feed configuration
- Don't consume resources

### Uninstall

**Via UI:**
1. Go to **Settings > Extensions**
2. Click the **Uninstall** button
3. Restart Reconly

**Via pip:**
```bash
pip uninstall reconly-ext-notion
```

---

## Extension Settings Storage

Extension settings are stored in the Reconly database with these key patterns:

| Extension Type | Setting Pattern |
|---------------|-----------------|
| Exporter | `extension.exporter.{name}.{field}` |
| Fetcher | `extension.fetcher.{name}.{field}` |
| Provider | `extension.provider.{name}.{field}` |

**Example:**
- `extension.exporter.obsidian.vault_path`
- `extension.exporter.obsidian.enabled`

---

## Environment Variables

Sensitive configuration (API keys, secrets) should be set via environment variables:

```bash
# Example for a hypothetical Reddit fetcher
export REDDIT_CLIENT_ID=your_client_id
export REDDIT_CLIENT_SECRET=your_client_secret
```

Or in a `.env` file:

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
```

Check each extension's documentation for its specific environment variables.

---

## Troubleshooting

### Extension Not Appearing

**After pip install:**
- Restart Reconly completely
- Check that the package installed correctly: `pip list | grep reconly-ext`
- Check logs for load errors

**Version mismatch:**
If you see "Requires Reconly X.X.X+":
- Update Reconly: `pip install --upgrade reconly-core`
- Or find an older version of the extension

### Extension Won't Enable

If the toggle is disabled:
- Click **Configure** and check for required fields
- All fields marked with * must have values
- Check if any fields require environment variables

### Extension Errors

Check the Reconly logs for detailed error messages:

```bash
# If running via uvicorn
uvicorn reconly_api.main:app --reload
# Errors appear in console output
```

Common issues:
- Missing dependencies (install via pip)
- API key invalid or expired
- Network connectivity issues
- Path doesn't exist (for filesystem exporters)

### Reset Extension Configuration

To reset an extension's configuration:

1. Disable the extension
2. Clear its settings via the API or database
3. Re-enable and configure fresh

---

## Finding Extensions

### Official Catalog

Browse the built-in catalog via **Settings > Extensions > Browse Catalog**.

### PyPI

Search PyPI for `reconly-ext-*`:
```
https://pypi.org/search/?q=reconly-ext-
```

### GitHub

Search GitHub for the `reconly-extension` topic or `reconly-ext-` prefix.

---

## Security Considerations

**Before installing third-party extensions:**

1. **Review the source code** - Extensions have full access to your digests and can make network requests
2. **Check the author** - Is it from a known/trusted developer?
3. **Look for "Verified" badge** - Verified extensions have been reviewed by the Reconly team
4. **Keep extensions updated** - Apply security patches promptly
5. **Use environment variables** for API keys - Don't put secrets in config files

---

## Creating Your Own Extensions

Want to create an extension? See the [Extension Development Guide](./EXTENSION_DEVELOPMENT.md).

---

## Questions?

- Check extension-specific documentation (usually in their repository)
- Open an issue on the extension's GitHub repository
- For general Reconly issues, use the main Reconly repository
