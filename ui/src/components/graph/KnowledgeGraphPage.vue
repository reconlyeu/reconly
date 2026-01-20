<script setup lang="ts">
/**
 * KnowledgeGraphPage - Main page component for knowledge graph visualization
 *
 * Combines GraphCanvas, GraphControls, and NodeDetailSidebar to provide
 * a complete graph exploration experience.
 */

import { ref, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { graphApi } from '@/services/api';
import { strings } from '@/i18n/en';
import { useToast } from '@/composables/useToast';
import type { GraphNode, GraphLayoutType, GraphViewMode, GraphFilters, GraphEdgeType } from '@/types/entities';
import GraphCanvas from './GraphCanvas.vue';
import GraphCanvas3D from './GraphCanvas3D.vue';
import GraphControls from './GraphControls.vue';
import NodeDetailSidebar from './NodeDetailSidebar.vue';
import EmptyState from '@/components/common/EmptyState.vue';
import ErrorState from '@/components/common/ErrorState.vue';
import { Network, Loader2 } from 'lucide-vue-next';

// State
const layout = ref<GraphLayoutType>('force');
const viewMode = ref<GraphViewMode>('2d');
const minSimilarity = ref(0.5);
const includeTags = ref(true);
const depth = ref(2);
const feedFilter = ref<number | null>(null);
const fromDate = ref('');
const toDate = ref('');
const tagFilter = ref<string[]>([]);
const relationshipTypes = ref<GraphEdgeType[]>(['semantic']); // Default to semantic only for cleaner visualization

const selectedNode = ref<GraphNode | null>(null);
const sidebarOpen = ref(false);
const graphCanvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null);
const graphCanvas3DRef = ref<InstanceType<typeof GraphCanvas3D> | null>(null);

const toast = useToast();

// Build filters object
const filters = computed<GraphFilters>(() => ({
  depth: depth.value,
  min_similarity: minSimilarity.value,
  include_tags: true, // Always true - relationship_types controls what's shown
  feed_id: feedFilter.value || undefined,
  from_date: fromDate.value || undefined,
  to_date: toDate.value || undefined,
  tags: tagFilter.value.length > 0 ? tagFilter.value : undefined,
  relationship_types: relationshipTypes.value.length > 0 ? relationshipTypes.value : undefined,
  limit: 100,
}));

// Fetch graph data
const {
  data: graphData,
  isLoading,
  isError,
  error,
  refetch,
} = useQuery({
  queryKey: ['graph', filters],
  queryFn: () => graphApi.getNodes(filters.value),
  staleTime: 30000,
  refetchOnWindowFocus: false,
});

const nodes = computed(() => graphData.value?.nodes || []);
const edges = computed(() => graphData.value?.edges || []);
const nodeCount = computed(() => nodes.value.length);
const edgeCount = computed(() => edges.value.length);

const hasData = computed(() => nodes.value.length > 0);

// Node selection handler
function handleNodeSelect(node: GraphNode | null): void {
  selectedNode.value = node;
  sidebarOpen.value = node !== null;
}

// Node expand handler
async function handleNodeExpand(node: GraphNode): Promise<void> {
  try {
    const expandedData = await graphApi.expandNode(node.id, 1, minSimilarity.value);

    if (!graphData.value) return;

    const existingNodeIds = new Set(graphData.value.nodes.map(n => n.id));
    const existingEdgeKeys = new Set(graphData.value.edges.map(e => `${e.source}-${e.target}`));

    const newNodes = expandedData.nodes.filter(n => !existingNodeIds.has(n.id));
    const newEdges = expandedData.edges.filter(e => !existingEdgeKeys.has(`${e.source}-${e.target}`));

    // Update the data (will trigger reactivity)
    graphData.value.nodes.push(...newNodes);
    graphData.value.edges.push(...newEdges);
    graphData.value.total_nodes = graphData.value.nodes.length;
    graphData.value.total_edges = graphData.value.edges.length;

    graphCanvasRef.value?.runLayout();
  } catch (err) {
    console.error('Failed to expand node:', err);
    toast.error('Failed to expand node connections');
  }
}

// View digest handler
function handleViewDigest(digestId: number): void {
  window.location.href = `/digests?view=${digestId}`;
}

// Sidebar close handler
function handleSidebarClose(): void {
  sidebarOpen.value = false;
}

// Get active canvas reference based on view mode
function getActiveCanvas() {
  return viewMode.value === '3d' ? graphCanvas3DRef.value : graphCanvasRef.value;
}

// Zoom handlers - delegate to the active canvas
function handleZoomIn(): void {
  getActiveCanvas()?.zoomIn();
}

function handleZoomOut(): void {
  getActiveCanvas()?.zoomOut();
}

function handleFitToScreen(): void {
  getActiveCanvas()?.fitToScreen();
}

function handleResetView(): void {
  getActiveCanvas()?.resetView();
}

// Helper to download data as file
function downloadFile(filename: string, content: string | Blob, mimeType: string): void {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.download = filename;
  link.href = url;
  link.click();
  URL.revokeObjectURL(url);
}

// Generate dated filename for exports
function getExportFilename(extension: string): string {
  return `knowledge-graph-${new Date().toISOString().split('T')[0]}.${extension}`;
}

// Export handlers
function handleExportPng(): void {
  if (viewMode.value === '3d') {
    toast.error('PNG export is only available in 2D view');
    return;
  }
  const dataUrl = graphCanvasRef.value?.exportPng();
  if (dataUrl) {
    const link = document.createElement('a');
    link.download = getExportFilename('png');
    link.href = dataUrl;
    link.click();
    toast.success('Graph exported as PNG');
  }
}

function handleExportJson(): void {
  const json = graphCanvasRef.value?.exportJson();
  if (json) {
    downloadFile(getExportFilename('json'), JSON.stringify(json, null, 2), 'application/json');
    toast.success('Graph exported as JSON');
  }
}
</script>

<template>
  <div class="graph-page flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex-shrink-0 mb-2">
      <h1 class="text-xl font-bold text-text-primary">{{ strings.knowledgeGraph.title }}</h1>
      <p class="text-sm text-text-secondary">
        {{ strings.knowledgeGraph.subtitle }}
      </p>
    </div>

    <!-- Controls + Graph wrapper -->
    <div class="flex-1 flex flex-col min-h-0 relative">
      <!-- Controls (flex-shrink-0 to prevent shrinking) -->
      <GraphControls
        v-model:layout="layout"
        v-model:view-mode="viewMode"
        v-model:min-similarity="minSimilarity"
        v-model:include-tags="includeTags"
        v-model:depth="depth"
        v-model:feed-filter="feedFilter"
        v-model:from-date="fromDate"
        v-model:to-date="toDate"
        v-model:tag-filter="tagFilter"
        v-model:relationship-types="relationshipTypes"
        :node-count="nodeCount"
        :edge-count="edgeCount"
        @zoom-in="handleZoomIn"
        @zoom-out="handleZoomOut"
        @fit-to-screen="handleFitToScreen"
        @reset-view="handleResetView"
        @export-png="handleExportPng"
        @export-json="handleExportJson"
        @clear-filters="refetch"
        class="flex-shrink-0 mb-2"
      />

      <!-- Graph Container -->
      <div
        class="flex-1 relative rounded-xl border border-border-subtle overflow-hidden min-h-0"
        :class="sidebarOpen ? 'mr-80' : ''"
      >
      <!-- Loading State -->
      <div
        v-if="isLoading"
        class="absolute inset-0 flex items-center justify-center bg-bg-elevated"
      >
        <div class="text-center">
          <Loader2 class="w-10 h-10 text-accent-primary animate-spin mx-auto mb-3" />
          <p class="text-text-secondary">{{ strings.knowledgeGraph.loading }}</p>
        </div>
      </div>

      <!-- Error State -->
      <ErrorState
        v-else-if="isError"
        class="absolute inset-0 flex items-center justify-center"
        entity-name="graph data"
        :error="error"
        show-retry
        @retry="refetch"
      />

      <!-- Empty State -->
      <EmptyState
        v-else-if="!hasData"
        class="absolute inset-0 flex items-center justify-center"
        :title="strings.knowledgeGraph.noData"
        :message="strings.knowledgeGraph.noDataDescription"
        :icon="Network"
      />

      <!-- Graph Canvas 2D -->
      <GraphCanvas
        v-else-if="viewMode === '2d'"
        ref="graphCanvasRef"
        :nodes="nodes"
        :edges="edges"
        :layout="layout"
        :selected-node-id="selectedNode?.id || null"
        @node-select="handleNodeSelect"
        @node-expand="handleNodeExpand"
        class="w-full h-full"
      />

      <!-- Graph Canvas 3D -->
      <GraphCanvas3D
        v-else
        ref="graphCanvas3DRef"
        :nodes="nodes"
        :edges="edges"
        :selected-node-id="selectedNode?.id || null"
        @node-select="handleNodeSelect"
        @node-expand="handleNodeExpand"
        class="w-full h-full"
      />
      </div>
    </div>

    <!-- Node Detail Sidebar -->
    <NodeDetailSidebar
      :node="selectedNode"
      :is-open="sidebarOpen"
      @close="handleSidebarClose"
      @expand-node="handleNodeExpand"
      @view-digest="handleViewDigest"
    />
  </div>
</template>

<style scoped>
/* Ensure the page fills available viewport height */
.graph-page {
  height: calc(100vh - 7rem);
}
</style>
