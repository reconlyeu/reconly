# Migration Guides

This directory contains migration guides for breaking changes between versions.

## Guide Format

Each migration guide follows this template:

```markdown
# Migration: v{old} to v{new}

## Breaking Changes

### Change 1: [Brief description]

**What changed:** [Detailed explanation]

**Migration steps:**
1. Step one
2. Step two

**Example:**
```python
# Before (v{old})
old_code()

# After (v{new})
new_code()
```

### Change 2: ...

## Database Migrations

Database migrations run automatically via Alembic. If manual intervention is needed:

```bash
# Check current migration
alembic current

# Upgrade to latest
alembic upgrade head
```

## Rollback

If you need to rollback:

```bash
# Rollback one migration
alembic downgrade -1

# Use previous Docker image
docker pull ghcr.io/reconlyeu/reconly:v{old}
```
```

## Current Guides

| Version | Date | Summary |
|---------|------|---------|
| (none yet) | - | First release pending |

## Creating a New Guide

When creating a breaking change:

1. Create `vX.Y.Z.md` in this directory
2. Follow the template above
3. Link from CHANGELOG.md
4. Update this README's table
