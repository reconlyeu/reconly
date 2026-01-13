<script setup lang="ts">
/**
 * GraphCanvas - Cytoscape.js graph visualization component
 *
 * Renders the knowledge graph using Cytoscape.js with:
 * - Force-directed, hierarchical, and radial layouts
 * - Node click to select
 * - Node double-click to expand
 * - Zoom and pan controls
 */

import { ref, onMounted, onUnmounted, watch } from 'vue';
import cytoscape, { type Core, type NodeSingular } from 'cytoscape';
import type { GraphNode, GraphEdge, GraphLayoutType } from '@/types/entities';

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout: GraphLayoutType;
  selectedNodeId: string | null;
}

interface Emits {
  (e: 'node-select', node: GraphNode | null): void;
  (e: 'node-expand', node: GraphNode): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const containerRef = ref<HTMLElement | null>(null);
let cy: Core | null = null;

// Node colors by type
const nodeColors: Record<string, { bg: string; border: string; text: string }> = {
  digest: { bg: '#3b82f6', border: '#1d4ed8', text: '#ffffff' }, // blue
  tag: { bg: '#8b5cf6', border: '#6d28d9', text: '#ffffff' }, // purple
  source: { bg: '#10b981', border: '#047857', text: '#ffffff' }, // green
  feed: { bg: '#f59e0b', border: '#d97706', text: '#ffffff' }, // amber
};

// Edge colors by type
const edgeColors: Record<string, string> = {
  semantic: '#3b82f6', // blue
  tag: '#8b5cf6', // purple
  source: '#10b981', // green
  temporal: '#6b7280', // gray
};

// Cytoscape stylesheet
const cytoscapeStyle: cytoscape.Stylesheet[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '11px',
      'font-weight': 500,
      color: '#ffffff',
      'text-outline-width': 1,
      'text-outline-color': 'data(borderColor)',
      'background-color': 'data(bgColor)',
      'border-width': 2,
      'border-color': 'data(borderColor)',
      width: 'data(size)',
      height: 'data(size)',
      'text-wrap': 'ellipsis',
      'text-max-width': '80px',
    },
  },
  {
    selector: 'node[type="digest"]',
    style: {
      shape: 'round-rectangle',
    },
  },
  {
    selector: 'node[type="tag"]',
    style: {
      shape: 'ellipse',
    },
  },
  {
    selector: 'node[type="source"]',
    style: {
      shape: 'diamond',
    },
  },
  {
    selector: 'node[type="feed"]',
    style: {
      shape: 'hexagon',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#fbbf24', // amber-400
      'box-shadow': '0 0 10px #fbbf24',
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 3,
      'border-color': '#fbbf24',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 'data(width)',
      'line-color': 'data(color)',
      'target-arrow-color': 'data(color)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      opacity: 0.7,
    },
  },
  {
    selector: 'edge:selected',
    style: {
      opacity: 1,
      width: 3,
    },
  },
  {
    selector: 'edge.highlighted',
    style: {
      opacity: 1,
      width: 3,
    },
  },
];

// Base config for all layouts
const BASE_LAYOUT_CONFIG = {
  animate: true,
  animationDuration: 500,
};

// Layout-specific configurations
const LAYOUT_CONFIGS: Record<GraphLayoutType, cytoscape.LayoutOptions> = {
  force: {
    ...BASE_LAYOUT_CONFIG,
    name: 'cose',
    idealEdgeLength: 100,
    nodeOverlap: 20,
    refresh: 20,
    fit: true,
    padding: 30,
    randomize: false,
    componentSpacing: 100,
    nodeRepulsion: () => 8000,
    edgeElasticity: () => 100,
    nestingFactor: 5,
    gravity: 80,
    numIter: 1000,
    initialTemp: 200,
    coolingFactor: 0.95,
    minTemp: 1.0,
  } as cytoscape.LayoutOptions,
  hierarchical: {
    ...BASE_LAYOUT_CONFIG,
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.5,
    padding: 30,
    avoidOverlap: true,
    fit: true,
  } as cytoscape.LayoutOptions,
  radial: {
    ...BASE_LAYOUT_CONFIG,
    name: 'concentric',
    fit: true,
    padding: 30,
    startAngle: (3 / 2) * Math.PI,
    sweep: 2 * Math.PI,
    clockwise: true,
    equidistant: false,
    minNodeSpacing: 50,
    avoidOverlap: true,
    concentric: (node: NodeSingular) => {
      // Digests at center, tags/sources at outer rings
      const type = node.data('type');
      if (type === 'digest') return 3;
      if (type === 'tag') return 2;
      if (type === 'source') return 1;
      return 0;
    },
    levelWidth: () => 1,
  } as cytoscape.LayoutOptions,
};

// Get layout config based on layout type
function getLayoutConfig(layoutType: GraphLayoutType): cytoscape.LayoutOptions {
  return LAYOUT_CONFIGS[layoutType] || LAYOUT_CONFIGS.force;
}

// Truncate text with ellipsis
function truncateLabel(text: string, maxLength: number): string {
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// Calculate node size based on type and data
function getNodeSize(node: GraphNode): number {
  if (node.type === 'digest') return 50;
  if (node.type === 'tag' && node.data.count) {
    return Math.min(60, 30 + (node.data.count as number) * 2);
  }
  return 40;
}

// Transform API nodes to Cytoscape format
function transformNodes(nodes: GraphNode[]): cytoscape.ElementDefinition[] {
  return nodes.map((node) => {
    const colors = nodeColors[node.type] || nodeColors.digest;
    return {
      data: {
        id: node.id,
        label: truncateLabel(node.label, 20),
        fullLabel: node.label,
        type: node.type,
        bgColor: colors.bg,
        borderColor: colors.border,
        textColor: colors.text,
        size: getNodeSize(node),
        ...node.data,
      },
    };
  });
}

// Transform API edges to Cytoscape format
function transformEdges(edges: GraphEdge[]): cytoscape.ElementDefinition[] {
  return edges.map((edge, index) => ({
    data: {
      id: `e_${index}`,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      score: edge.score,
      color: edgeColors[edge.type] || edgeColors.semantic,
      width: 1 + edge.score * 3, // Width based on score (1-4px)
    },
  }));
}

// Build GraphNode from Cytoscape node data
function nodeDataToGraphNode(nodeData: Record<string, unknown>): GraphNode {
  return {
    id: nodeData.id as string,
    type: nodeData.type as GraphNode['type'],
    label: nodeData.fullLabel as string,
    data: nodeData as GraphNode['data'],
  };
}

// Initialize Cytoscape
function initCytoscape(): void {
  if (!containerRef.value) return;

  cy = cytoscape({
    container: containerRef.value,
    elements: {
      nodes: transformNodes(props.nodes),
      edges: transformEdges(props.edges),
    },
    style: cytoscapeStyle,
    layout: getLayoutConfig(props.layout),
    minZoom: 0.1,
    maxZoom: 3,
    wheelSensitivity: 0.3,
  });

  // Node tap - select node
  cy.on('tap', 'node', (evt) => {
    emit('node-select', nodeDataToGraphNode(evt.target.data()));
  });

  // Background tap - deselect
  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      emit('node-select', null);
    }
  });

  // Node double-tap - expand
  cy.on('dbltap', 'node', (evt) => {
    emit('node-expand', nodeDataToGraphNode(evt.target.data()));
  });

  // Highlight connected nodes/edges on hover
  cy.on('mouseover', 'node', (evt) => {
    const node = evt.target;
    cy?.elements().removeClass('highlighted');
    node.neighborhood().add(node).addClass('highlighted');
  });

  cy.on('mouseout', 'node', () => {
    cy?.elements().removeClass('highlighted');
  });
}

// Update graph when data changes
function updateGraph(): void {
  if (!cy) return;

  // Get existing node positions for smooth transitions
  const positions: Record<string, { x: number; y: number }> = {};
  cy.nodes().forEach((node) => {
    positions[node.id()] = node.position();
  });

  // Update elements
  cy.elements().remove();
  cy.add([...transformNodes(props.nodes), ...transformEdges(props.edges)]);

  // Apply saved positions for existing nodes
  cy.nodes().forEach((node) => {
    if (positions[node.id()]) {
      node.position(positions[node.id()]);
    }
  });

  cy.layout(getLayoutConfig(props.layout)).run();
}

// Run layout
function runLayout(): void {
  if (!cy) return;
  cy.layout(getLayoutConfig(props.layout)).run();
}

// Zoom controls (exposed to parent)
function zoomIn(): void {
  if (!cy) return;
  cy.zoom(cy.zoom() * 1.2);
  cy.center();
}

function zoomOut(): void {
  if (!cy) return;
  cy.zoom(cy.zoom() / 1.2);
  cy.center();
}

function fitToScreen(): void {
  if (!cy) return;
  cy.fit(undefined, 30);
}

function resetView(): void {
  if (!cy) return;
  cy.fit(undefined, 30);
  cy.center();
}

// Export functions
function exportPng(): string | null {
  if (!cy) return null;
  return cy.png({ full: true, scale: 2, bg: '#1f2937' });
}

function exportJson(): object | null {
  if (!cy) return null;
  return cy.json();
}

// Watch for changes
watch(() => [props.nodes, props.edges], updateGraph, { deep: true });
watch(() => props.layout, runLayout);
watch(
  () => props.selectedNodeId,
  (newId) => {
    if (!cy) return;
    cy.nodes().unselect();
    if (newId) {
      const node = cy.getElementById(newId);
      if (node.length) {
        node.select();
        cy.center(node);
      }
    }
  }
);

// Lifecycle
onMounted(() => {
  initCytoscape();
});

onUnmounted(() => {
  if (cy) {
    cy.destroy();
    cy = null;
  }
});

// Expose methods to parent
defineExpose({
  zoomIn,
  zoomOut,
  fitToScreen,
  resetView,
  exportPng,
  exportJson,
  runLayout,
});
</script>

<template>
  <div ref="containerRef" class="w-full h-full bg-bg-elevated rounded-lg" />
</template>

<style scoped>
/* Ensure the container takes full space */
div {
  min-height: 400px;
}
</style>
