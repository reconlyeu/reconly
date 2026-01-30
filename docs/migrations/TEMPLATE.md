# Migration: vX.Y.Z to vA.B.C

> **Release Date:** YYYY-MM-DD
>
> **Affected versions:** Users upgrading from vX.Y.Z or earlier

## Overview

Brief summary of what changed and why.

## Breaking Changes

### 1. [Change Title]

**What changed:**
Description of the change.

**Why:**
Reason for the change.

**Migration steps:**

1. First step
2. Second step
3. Third step

**Before (vX.Y.Z):**
```python
# Old way
old_code_example()
```

**After (vA.B.C):**
```python
# New way
new_code_example()
```

### 2. [Another Change Title]

...

## Configuration Changes

| Setting | Old Value | New Value | Notes |
|---------|-----------|-----------|-------|
| `SETTING_NAME` | `old` | `new` | Description |

## Database Migrations

Database migrations run automatically. If upgrading from a very old version:

```bash
# Ensure all migrations are applied
cd packages/api
alembic upgrade head
```

### Manual Data Migration (if needed)

```sql
-- Run this SQL if upgrading from vX.Y.Z
UPDATE table SET column = 'new_value' WHERE condition;
```

## API Changes

| Endpoint | Change | Migration |
|----------|--------|-----------|
| `GET /api/v1/example` | Removed field `old_field` | Use `new_field` instead |

## Docker Compose Changes

If your `docker-compose.yml` was customized, update:

```yaml
# Old
old_config: value

# New
new_config: value
```

## Verification

After upgrading, verify the migration was successful:

```bash
# Check version
curl http://localhost:8000/health/detailed | jq .version

# Verify functionality
curl http://localhost:8000/api/v1/status
```

## Rollback

If issues occur, rollback to the previous version:

```bash
# Stop current version
docker compose down

# Use previous image
RECONLY_VERSION=X.Y.Z docker compose up -d

# Rollback database (if needed)
alembic downgrade -1
```

## Support

- [GitHub Issues](https://github.com/reconlyeu/reconly/issues)
- [Discussions](https://github.com/reconlyeu/reconly/discussions)
