# Web UI Development

The Reconly web UI provides a modern interface for managing sources, feeds, and viewing digests.

## Technology Stack

- **Framework**: Astro 5.16 + Vue 3.5
- **Styling**: Tailwind CSS 4
- **State**: Pinia stores
- **Build Output**: `ui/dist/`

## Features

- Dashboard with live feed monitoring
- Source management (RSS, YouTube, Website, Blog)
- Feed orchestration with cron scheduling
- Template management (Prompt & Report templates)
- Digest browser with search and filtering
- **Tag management** with filtering and autocomplete
- **Feed bundles** - export/import feed configurations
- **Knowledge graph** - interactive visualization of digest relationships
- Analytics with CSS-only charts
- Settings with provider status

## Project Structure

```
ui/
├── src/
│   ├── components/          # Vue components by feature
│   │   ├── dashboard/       # Dashboard widgets
│   │   ├── sources/         # Source management
│   │   ├── feeds/           # Feed management
│   │   ├── templates/       # Template management
│   │   ├── digests/         # Digest browser
│   │   ├── graph/           # Knowledge graph visualization
│   │   ├── analytics/       # Analytics charts
│   │   ├── settings/        # Settings panels
│   │   └── common/          # Shared components
│   ├── layouts/             # Astro layouts
│   ├── pages/               # Astro pages (routes)
│   ├── services/            # API client
│   ├── stores/              # Pinia stores
│   ├── styles/              # Global styles & design system
│   ├── types/               # TypeScript type definitions
│   └── i18n/                # Internationalization strings
├── dist/                    # Build output (served by FastAPI)
└── package.json
```

## Development Mode

### Option 1: Full Stack (Recommended)

Start the backend which serves both API and built UI:

```bash
cd packages/api
python -m uvicorn reconly_api.main:app --reload --host 0.0.0.0 --port 8000
```

Access at `http://localhost:8000/`

### Option 2: UI Hot Reload

For active UI development with hot module replacement:

```bash
# Terminal 1: Start backend
cd packages/api
python -m uvicorn reconly_api.main:app --reload --port 8000

# Terminal 2: Start Astro dev server
cd ui
npm run dev
```

Access UI at `http://localhost:4321/` (proxies API calls to :8000)

## Building for Production

```bash
cd ui
npm run build
```

The build output in `ui/dist/` is automatically served by the FastAPI backend.

## Design System

The UI follows an **immich-inspired aesthetic**:

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#000000` | OLED black background |
| `--accent` | `#4250af` | Primary accent blue |
| `--text-primary` | `#ffffff` | Primary text |
| `--text-secondary` | `#a0a0a0` | Secondary text |

### Typography

- System font stack with custom configurations
- Monospace for code and data

### Animations

- CSS-only staggered reveals
- Smooth transitions for state changes
- No external animation libraries

### Charts

- Custom CSS-only visualizations
- No external charting libraries
- Responsive and accessible

## API Client

The API client in `src/services/` handles all backend communication:

```typescript
// src/services/api.ts
import { api } from './api';

// Example usage in a component
const sources = await api.sources.list();
const feed = await api.feeds.get(feedId);
await api.feeds.run(feedId);
```

## State Management

Pinia stores in `src/stores/` manage application state:

```typescript
// src/stores/sources.ts
import { useSourcesStore } from '@/stores/sources';

const store = useSourcesStore();
await store.fetchSources();
console.log(store.sources);
```

## Internationalization

Translations in `src/i18n/`:

```typescript
// src/i18n/en.ts
export default {
  dashboard: {
    title: 'Dashboard',
    totalSources: 'Total Sources',
  },
};
```

## Tag Management

The digest browser includes full tag management capabilities:

### Tag Filtering

- **Filter dropdown** in DigestsPage alongside Feed and Source filters
- **Multi-select** - filter by one or more tags (OR logic)
- **Usage counts** - each tag shows how many digests use it
- **URL sync** - tag filters persist in URL query parameters

### Tag Display

- **Digest cards** - tags displayed as styled badges
- **Digest modal** - dedicated Tags section with all tags
- **Consistent styling** - tags use the same visual style throughout

### Tag Editing

- **TagInput component** - reusable multi-select with autocomplete
- **Inline editing** - add/remove tags directly in digest modal
- **Create new tags** - type a new tag name and press Enter
- **Autocomplete** - suggestions based on existing tags

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `TagInput.vue` | `components/common/` | Reusable tag input with autocomplete |
| `DigestsPage.vue` | `components/digests/` | Tag filter dropdown |
| `DigestModal.vue` | `components/digests/` | Tag display and editing |
| `DigestCard.vue` | `components/digests/` | Tag badge display |

## Feed Bundle Export/Import

The UI supports exporting and importing feed configurations as portable JSON bundles.

### Export

- **Export button** on each feed card
- Downloads a `.json` file with complete feed configuration
- Includes sources, templates, schedule, and output config

### Import

- **Import Bundle** button in feeds page header
- Drag-and-drop or file picker for `.json` bundle files
- Preview shows what will be created before importing
- Validation ensures bundle schema compliance

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `FeedCard.vue` | `components/feeds/` | Export button in actions |
| `FeedList.vue` | `components/feeds/` | Import button and handler |
| `ImportBundleModal.vue` | `components/feeds/` | Drag-drop upload and preview |

### API Methods

```typescript
// src/services/api.ts
bundlesApi.export(feedId)      // Export feed as bundle
bundlesApi.validate(bundle)     // Validate bundle schema
bundlesApi.preview(bundle)      // Preview import (dry run)
bundlesApi.import(bundle)       // Import bundle to create feed
```

## Knowledge Graph

The Knowledge Graph page provides interactive visualization of semantic relationships between digests, powered by the RAG system's embedding-based similarity detection.

### Features

- **Interactive graph visualization** using Cytoscape.js (2D) and 3d-force-graph (3D)
- **Node expansion** - click to reveal related digests
- **Multiple layouts** - force-directed, hierarchical, radial
- **2D/3D toggle** - switch between visualization modes
- **Filtering** - by date range, feed, tags, similarity threshold
- **Detail sidebar** - view digest details on node selection
- **Export** - save graph as PNG or JSON

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `KnowledgeGraphPage.vue` | `components/graph/` | Main page orchestrator |
| `GraphCanvas.vue` | `components/graph/` | 2D Cytoscape.js renderer |
| `GraphCanvas3D.vue` | `components/graph/` | 3D WebGL renderer |
| `GraphControls.vue` | `components/graph/` | Filter and layout controls |
| `NodeDetailSidebar.vue` | `components/graph/` | Digest detail panel |

### Usage

Navigate to `/knowledge-graph` in the sidebar. The graph loads automatically with default settings:

1. **Explore** - Pan/zoom to navigate, click nodes to select
2. **Expand** - Double-click a node to load related digests
3. **Filter** - Use controls to filter by date, feed, tags
4. **Adjust similarity** - Lower threshold shows more connections
5. **Switch views** - Toggle between 2D and 3D modes
6. **Export** - Save current view as PNG or graph data as JSON

### API Methods

```typescript
// src/services/api.ts
graphApi.getNodes(filters)           // Get graph nodes and edges
graphApi.expandNode(id, depth, sim)  // Expand node to show related
```

### Requirements

The Knowledge Graph requires the RAG system to be configured:

1. PostgreSQL with pgvector extension
2. Embedding provider configured (Ollama, LM Studio, OpenAI, or HuggingFace)
3. Digests must be embedded (`embedding_status = 'completed'`)

See [RAG Setup Guide](rag-setup.md) for configuration details.

## Adding New Features

1. **Create component** in appropriate `src/components/` subdirectory
2. **Add route** in `src/pages/` if needed
3. **Create/update store** in `src/stores/` for state management
4. **Add API methods** in `src/services/` for backend calls
5. **Add translations** in `src/i18n/`

## Testing

```bash
cd ui

# Run unit tests
npm run test

# Run with coverage
npm run test:coverage
```

## Troubleshooting

### UI Not Loading in Production

1. Verify `ui/dist/` exists: `ls ui/dist/`
2. Check FastAPI logs for UI_DIR detection
3. Rebuild: `cd ui && npm run build`

### Hot Reload Not Working

1. Ensure Astro dev server is running on port 4321
2. Check browser console for WebSocket errors
3. Try hard refresh (Ctrl+Shift+R)

### API Calls Failing in Dev Mode

1. Verify backend is running on port 8000
2. Check CORS settings in `packages/api/reconly_api/config.py`
3. Ensure proxy is configured in `astro.config.mjs`
