# Development Guide

This guide covers setting up a development environment and contributing to Reconly.

## Prerequisites

- Python 3.11+
- Node.js 18+ (for UI development)
- PostgreSQL 16+ with pgvector extension
- Git

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/reconlyeu/reconly.git
cd reconly-oss

# Install packages in development mode
pip install -e packages/core
pip install -e packages/api

# Install test dependencies
pip install pytest pytest-cov pytest-mock responses freezegun
```

### 2. Set Up PostgreSQL

Start PostgreSQL with pgvector:

```bash
# Using Docker (recommended for development)
docker-compose -f docker/docker-compose.postgres.yml up -d

# Or install PostgreSQL 16+ with pgvector extension locally
# See docs/rag-setup.md for installation instructions
```

Configure the database connection:

```bash
# Create .env file
echo "DATABASE_URL=postgresql://reconly:reconly_dev@localhost:5432/reconly" > .env
```

### 3. Initialize Database

```bash
cd packages/api
python -m alembic upgrade head

# Optional: Load sample data (development only - not used in production Docker)
python scripts/populate_sample_data.py
```

### 4. Start Development Server

```bash
cd packages/api
python -m uvicorn reconly_api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. UI Development (Optional)

For frontend development with hot-reload:

```bash
# Terminal 1: Start API server
cd packages/api
python -m uvicorn reconly_api.main:app --reload --port 8000

# Terminal 2: Start UI dev server
cd ui
npm install
npm run dev
```

The UI dev server runs at `http://localhost:4321` with hot-reload.
API requests are proxied to `http://localhost:8000`.

#### Building UI for Production

```bash
cd ui
npm run build
```

Built files go to `ui/dist/` and are served by FastAPI automatically.

## Project Structure

```
reconly-oss/
├── packages/
│   ├── core/                    # Core library
│   │   └── reconly_core/
│   │       ├── cli/             # CLI commands
│   │       ├── database/        # Models, CRUD, migrations
│   │       ├── fetchers/        # RSS, YouTube, website
│   │       ├── marketplace/     # Feed bundle export/import
│   │       ├── services/        # DigestService, FeedService
│   │       └── summarizers/     # LLM providers
│   └── api/                     # FastAPI server
│       ├── migrations/          # Alembic migrations
│       └── reconly_api/
│           ├── routes/          # API endpoints
│           ├── scheduler.py     # APScheduler for feed scheduling
│           └── tasks/           # Background task functions
├── ui/                          # Frontend (Astro + Vue)
├── config/                      # Configuration files
├── data/                        # Data files
├── tests/                       # Test suite
├── docs/                        # Documentation
└── docker/                      # Docker configurations
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=packages/core/reconly_core --cov-report=term-missing

# Run specific test file
pytest tests/test_fetchers.py -v

# Run tests matching pattern
pytest tests/ -k "test_rss" -v
```

### Test Coverage

- 283+ tests covering core functionality
- 90%+ coverage for fetchers, summarizers, and database
- Comprehensive provider test suites

## Code Style

- Python: Follow PEP 8
- TypeScript: ESLint + Prettier
- Use type hints in Python
- Write docstrings for public functions

## Adding a New LLM Provider

1. Create provider file in `packages/core/reconly_core/summarizers/`
2. Implement the `BaseSummarizer` interface
3. Register in provider factory
4. Add tests in `tests/test_summarizers/`
5. Update documentation

See `docs/ADDING_PROVIDERS.md` for detailed guide.

## Database Migrations

When modifying database models:

```bash
cd packages/api

# Create migration
alembic revision --autogenerate -m "Add new field to sources"

# Review the generated migration in migrations/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Feed Scheduling

Feeds support cron-based scheduling with the built-in APScheduler. No external services like Redis or Celery are required.

```python
from reconly_core.database import Feed, get_session

session = get_session()

# Create feed with daily 8 AM schedule
feed = Feed(
    name="Morning Tech Digest",
    schedule_cron="0 8 * * *",  # minute hour day month weekday
    schedule_enabled=True,
    output_config={
        "db": True,
        "email": {
            "enabled": True,
            "recipients": ["me@example.com"]
        }
    }
)
session.add(feed)
session.commit()
```

The scheduler:
- Starts automatically with the API server
- Uses your local timezone by default (configurable via `SCHEDULER_TIMEZONE`)
- Syncs schedules when feeds are created/updated/deleted
- Logs scheduled jobs and their next run times on startup

## Template System

### Prompt Templates

Control how content is summarized:

| Template | Language | Length | Use Case |
|----------|----------|--------|----------|
| Standard Summary | DE/EN | 150 words | Daily digests |
| Quick Brief | DE/EN | 50 words | Fast scanning |
| Deep Analysis | DE/EN | 300 words | Research |

### Report Templates

Control output formatting:

| Template | Format | Use Case |
|----------|--------|----------|
| Daily Digest | Markdown | Notes, docs |
| Daily Digest | HTML | Email newsletters |
| Simple List | Markdown | Quick reference |
| Obsidian Note | Markdown | PKM with frontmatter |
| JSON Export | JSON | API integrations |

## Architecture

```
User (optional for single-user)
  └── Sources (RSS, YouTube, websites)
  └── Feeds (groups of sources with schedule)
        └── FeedRuns (execution history)
              └── Digests (summarized content)
                    └── LLMUsageLogs (cost tracking)
  └── PromptTemplates (LLM instructions, origin: builtin|user|imported)
  └── ReportTemplates (output formatting, origin: builtin|user|imported)
  └── FeedBundles (portable JSON packages for sharing feed configs)
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

### Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Be descriptive but concise
- Reference issues when applicable: "Fix #123: Handle empty feeds"

## Troubleshooting

### Import Errors

```bash
# Ensure packages are installed in dev mode
pip install -e packages/core
pip install -e packages/api
```

### Database Issues

```bash
# Reset database (drops all tables)
psql postgresql://reconly:reconly_dev@localhost:5432/reconly
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\q

# Recreate schema
cd packages/api
python -m alembic upgrade head
python scripts/populate_sample_data.py  # Optional: reload dev sample data
```

### Test Failures

```bash
# Run with verbose output
pytest tests/ -v --tb=long

# Run single test for debugging
pytest tests/test_file.py::test_function -v -s
```

## UI Development

### Stack

- **Astro 5.x** - Static site generation with islands architecture
- **Vue 3.5** - Component framework
- **Tailwind CSS 4** - Styling
- **TanStack Vue Query** - Data fetching and caching
- **Pinia** - State management
- **Axios** - HTTP client

### Directory Structure

```
ui/
├── src/
│   ├── components/          # Vue components
│   │   ├── common/          # Shared (Sidebar, Modal, etc.)
│   │   ├── dashboard/       # Dashboard widgets
│   │   ├── sources/         # Source management
│   │   ├── feeds/           # Feed management
│   │   ├── templates/       # Template editors
│   │   ├── digests/         # Digest browser
│   │   └── analytics/       # Analytics charts
│   ├── pages/               # Astro pages (routes)
│   ├── layouts/             # Page layouts
│   ├── stores/              # Pinia stores
│   ├── services/            # API client (api.ts)
│   ├── composables/         # Vue composables
│   ├── types/               # TypeScript types
│   └── config/              # Feature flags
├── public/                  # Static assets
└── astro.config.mjs         # Astro configuration
```

### Key Patterns

#### API Calls with TanStack Query

```typescript
// In components
import { useQuery, useMutation } from '@tanstack/vue-query';
import { sourcesApi } from '@/services/api';

// Fetching data
const { data: sources, isLoading } = useQuery({
  queryKey: ['sources'],
  queryFn: sourcesApi.list,
});

// Mutations
const createMutation = useMutation({
  mutationFn: sourcesApi.create,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
    toast.success('Source created');
  },
});
```

#### Feature Flags

```typescript
// src/config/features.ts
import { features } from '@config/features';

// In components
<div v-if="features.costDisplay">
  Cost: ${{ digest.cost }}
</div>
```

#### Toast Notifications

```typescript
import { useToast } from '@/composables/useToast';

const toast = useToast();
toast.success('Saved successfully');
toast.error('Failed to save');
```

### Development Commands

```bash
cd ui

# Install dependencies
npm install

# Start dev server (hot-reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run astro check
```

### Environment Variables

UI-specific environment variables (build-time):

```bash
# ui/.env
PUBLIC_API_URL=/api/v1      # API base URL
VITE_EDITION=oss            # Edition for feature flags
```

### Adding a New Page

1. Create page in `src/pages/`:
   ```astro
   ---
   import BaseLayout from '@layouts/BaseLayout.astro';
   import MyComponent from '@components/my/MyComponent.vue';
   ---
   <BaseLayout title="My Page">
     <MyComponent client:load />
   </BaseLayout>
   ```

2. Create Vue component in `src/components/`:
   ```vue
   <script setup lang="ts">
   import { useQuery } from '@tanstack/vue-query';
   </script>
   <template>
     <div>...</div>
   </template>
   ```

3. Add types to `src/types/entities.ts` if needed

4. Add API methods to `src/services/api.ts` if needed
