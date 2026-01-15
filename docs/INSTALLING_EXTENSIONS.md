# Installing Reconly Extensions

This guide explains how to install, configure, and manage extensions in Reconly.

## Overview

Extensions add new capabilities to Reconly:
- **Exporters** - Export digests to new formats (Obsidian, Notion, etc.)
- **Fetchers** - Fetch content from new sources (Reddit, HackerNews, etc.)
- **Providers** - LLM providers (coming soon)

## Installing Extensions

### Via the Catalog (Recommended)

The easiest way to install extensions is through Reconly's built-in catalog:

1. Open Reconly
2. Go to **Settings > Extensions**
3. Click **Browse Catalog**
4. Search for the extension you want
5. Click **Install**
6. Restart Reconly when prompted

The catalog shows both **verified** and **community** extensions:

**Verified Extensions:**
- Reviewed by the Reconly team
- Hosted in the official [reconly-extensions](https://github.com/reconlyeu/reconly-extensions) repository
- One-click installation from GitHub
- Display a "Verified" badge in the UI
- Automatically updated when you refresh the catalog

**Community Extensions:**
- Created by community members
- May be hosted in individual repositories
- Can be installed via GitHub URLs or PyPI
- No verification badge, use with appropriate caution

### Via GitHub URL (Advanced)

You can install extensions directly from GitHub:

```bash
# Install from a GitHub repository
pip install git+https://github.com/username/reconly-ext-myformat.git

# Install from a monorepo subdirectory (like reconly-extensions)
pip install git+https://github.com/reconlyeu/reconly-extensions.git#subdirectory=extensions/reconly-ext-txt
```

Then restart Reconly.

**When to use GitHub installation:**
- Installing pre-release versions
- Testing development branches
- Installing community extensions not yet in catalog
- Working with extensions in monorepos

### Via pip from PyPI (Traditional)

Extensions published to PyPI can be installed like any Python package:

```bash
pip install reconly-ext-notion
```

Then restart Reconly.

### For Local Development

If you're developing an extension locally:

```bash
cd /path/to/reconly-ext-myformat
pip install -e .
```

This installs the extension in "editable" mode so changes take effect immediately (after restart).

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

The catalog is fetched from the [reconly-extensions](https://github.com/reconlyeu/reconly-extensions) repository and includes:

- **Verified Extensions**: Official extensions reviewed by the Reconly team
- **Community Extensions**: Extensions submitted by community members
- **Install Source Badge**: Shows whether the extension is from GitHub or PyPI
- **One-Click Install**: Install directly from the UI for GitHub-based extensions

**Catalog Features:**
- Search by name or description
- Filter by type (exporter, fetcher, provider)
- Filter to show only verified extensions
- View source code links
- See minimum Reconly version required

### Catalog Sources

Extensions in the catalog can be installed from different sources:

| Source | Badge | Description |
|--------|-------|-------------|
| **GitHub (Verified)** | Verified | Official extensions in reconly-extensions monorepo |
| **GitHub (Community)** | - | Community extensions in their own repositories |
| **PyPI** | - | Traditional PyPI packages |

**GitHub-based extensions** are preferred because:
- No need to publish to PyPI
- Faster iteration and updates
- Easier code review process
- Direct source code access
- Monorepo benefits for verified extensions

### PyPI

Search PyPI for `reconly-ext-*`:
```
https://pypi.org/search/?q=reconly-ext-
```

### GitHub

Search GitHub for repositories with:
- `reconly-ext-` prefix
- `reconly-extension` topic
- Visit [reconly-extensions](https://github.com/reconlyeu/reconly-extensions) for verified extensions

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
