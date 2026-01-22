# Contributing to Reconly

Thank you for your interest in contributing to Reconly!

**Before you start:** Please read the [Where to Contribute](#where-to-contribute) section to understand which contributions are welcome. The best place to contribute is the **[reconly-extensions](https://github.com/reconlyeu/reconly-extensions)** repository where you can add fetchers, exporters, and providers without touching core code.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Where to Contribute](#where-to-contribute)

## 🤝 Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to hello@reconly.eu.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Basic understanding of Python, FastAPI, and SQLAlchemy

### Fork the Repository

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/reconly.git
cd reconly
```

3. Add the upstream repository:

```bash
git remote add upstream https://github.com/reconlyeu/reconly.git
```

## 💻 Development Setup

### Install Dependencies

```bash
# Install core package in development mode
pip install -e packages/core

# Install API package in development mode
pip install -e packages/api

# Install development dependencies
pip install pytest pytest-asyncio pytest-cov
```

### Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=packages --cov-report=html

# Run specific test file
pytest tests/core/test_digest_crud.py -v
```

### Start Development Server

```bash
# Start API server with auto-reload
uvicorn reconly_api.main:app --reload --port 8000
```

## 🔨 Making Changes

### Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### Branch Naming Convention

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test improvements

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): subject

body (optional)

footer (optional)
```

Examples:
```
feat(core): add support for Atom feeds
fix(api): resolve database connection pool exhaustion
docs(readme): update installation instructions
test(core): add tests for YouTube fetcher
```

## ✅ Testing

### Writing Tests

- Place tests in `tests/core/` or `tests/api/` depending on the package
- Use descriptive test names: `test_create_digest_with_tags()`
- Aim for >80% code coverage for new code
- Test both success and error cases

### Test Structure

```python
import pytest
from reconly_core.database.crud import DigestDB

@pytest.mark.unit
def test_create_digest(db_session):
    """Test creating a digest with valid data."""
    digest_db = DigestDB(session=db_session)

    digest = digest_db.create_digest(
        url="https://example.com/article",
        title="Test Article",
        summary="Test summary"
    )

    assert digest.id is not None
    assert digest.title == "Test Article"
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run tests for a specific package
pytest tests/core/

# Run tests with markers
pytest tests/ -m unit
pytest tests/ -m integration

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=packages --cov-report=term-missing
```

## 📤 Submitting Changes

### Before Submitting

1. ✅ All tests pass: `pytest tests/`
2. ✅ Code follows style guidelines (see below)
3. ✅ Documentation updated if needed
4. ✅ Commits follow conventional format
5. ✅ Branch is up-to-date with `main`

### Pull Request Process

1. **Update your branch**:
```bash
git fetch upstream
git rebase upstream/main
```

2. **Push to your fork**:
```bash
git push origin feature/your-feature-name
```

3. **Create Pull Request**:
   - Go to GitHub and create a PR from your fork
   - Fill out the PR template
   - Link any related issues

4. **PR Template**:
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] All existing tests pass
- [ ] Added new tests for changes
- [ ] Tested locally

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
```

5. **Review Process**:
   - Maintainers will review your PR
   - Address any feedback
   - Once approved, it will be merged

## 🎨 Code Style

### Python Style

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 100 characters (not 79)
- **Imports**: Group by stdlib, third-party, local
- **Docstrings**: Google style
- **Type hints**: Use where helpful

### Example

```python
"""Module for fetching and processing RSS feeds."""
from datetime import datetime
from typing import List, Optional

import feedparser
from sqlalchemy.orm import Session

from reconly_core.database.models import Digest


def fetch_rss_feed(
    feed_url: str,
    language: str = "en",
    max_items: int = 10
) -> List[Dict]:
    """
    Fetch and parse an RSS feed.

    Args:
        feed_url: URL of the RSS feed
        language: Target language for summaries
        max_items: Maximum number of items to fetch

    Returns:
        List of parsed feed items

    Raises:
        ValueError: If feed_url is invalid
        RequestException: If feed cannot be fetched
    """
    if not feed_url:
        raise ValueError("feed_url cannot be empty")

    # Implementation...
    return items
```

### Formatting Tools

We recommend using:
- `black` for code formatting
- `isort` for import sorting
- `mypy` for type checking (optional)

```bash
pip install black isort mypy

# Format code
black packages/
isort packages/

# Type check
mypy packages/core --ignore-missing-imports
```

## 💡 Where to Contribute

Reconly is maintained by a solo developer with a commercial Enterprise edition built on top of the OSS core. To be transparent about where contributions are welcome and to avoid wasted effort, contributions are organized into tiers:

### ✅ Welcome - Extensions Repository

**The best way to contribute!** The [reconly-extensions](https://github.com/reconlyeu/reconly-extensions) repository is designed for community contributions:

- **Fetchers** - Add support for new content sources (podcasts, newsletters, etc.)
- **Exporters** - Export to new formats or PKM systems
- **Providers** - Integrate new LLM or search providers

Extensions follow a registry pattern and don't modify core code. PRs here are reviewed and merged regularly.

👉 **Start here:** [reconly-extensions](https://github.com/reconlyeu/reconly-extensions)

### ✅ Welcome - Documentation & Typos

Low-risk improvements that are always appreciated:

- Fix typos and grammar
- Improve setup guides and examples
- Add tutorials or usage examples
- Translate documentation

### ⚠️ Discuss First - Bug Fixes

Bug fixes to the core are welcome but **require discussion before coding**:

1. Open an issue describing the bug
2. Wait for maintainer confirmation
3. Discuss the proposed fix approach
4. Only then submit a PR

This prevents duplicate effort and ensures fixes align with the codebase direction.

### 🚫 Not Accepting - Core Features

**The core architecture is not open for feature contributions.** This includes:

- New API endpoints
- Database schema changes
- New core services or major features
- Architectural refactoring

**Why?** The OSS core must remain stable as the foundation for [Reconly Enterprise](https://reconly.eu). Feature direction is driven by the roadmap, not community PRs.

**Want a feature?** Open a [Discussion](https://github.com/reconlyeu/reconly/discussions) to share your idea. Good ideas often make it to the roadmap!

### What NOT to Submit

To save everyone's time, these PRs will be closed without review:

- Core feature PRs without prior discussion
- Enterprise features (teams, multi-user, billing) - these belong in Reconly Enterprise
- Breaking changes or large refactors
- Code that doesn't follow style guidelines
- PRs that ignore this contribution guide

## 📞 Questions?

- 💬 **Discussions**: [GitHub Discussions](https://github.com/reconlyeu/reconly/discussions)
- 📧 **Email**: hello@reconly.eu
- 🐛 **Bugs**: [GitHub Issues](https://github.com/reconlyeu/reconly/issues)

Thank you for contributing to Reconly! 🙏
