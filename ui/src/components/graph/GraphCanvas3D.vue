<script setup lang="ts">
/**
 * GraphCanvas3D - 3D Knowledge Graph visualization using 3d-force-graph
 *
 * Renders the knowledge graph in WebGL with:
 * - Force-directed layout in 3D space
 * - Camera orbit controls (built-in)
 * - Node click/hover interactions
 * - Color-coded nodes by type
 * - Edge lines colored by relationship type
 * - Text labels on nodes and feed clusters
 */

import { ref, onMounted, onUnmounted, watch, computed, shallowRef } from 'vue';
import type { GraphNode, GraphEdge, GraphNodeType, GraphEdgeType, GraphNodeData } from '@/types/entities';
import SpriteText from 'three-spritetext';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ForceGraph3DInstance = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ForceGraph3DFactory = any;

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
}

interface Emits {
  (e: 'node-select', node: GraphNode | null): void;
  (e: 'node-expand', node: GraphNode): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const containerRef = ref<HTMLElement | null>(null);
// Use shallowRef for the graph instance to avoid deep reactivity issues
const graph = shallowRef<ForceGraph3DInstance | null>(null);
// Store the dynamically imported ForceGraph3D factory
let ForceGraph3D: ForceGraph3DFactory | null = null;

// Node colors by type (matching 2D version)
const nodeColors: Record<GraphNodeType, number> = {
  digest: 0x3b82f6, // blue
  tag: 0x8b5cf6, // purple
  source: 0x10b981, // green
  feed: 0xf59e0b, // amber - used for feed cluster labels
};

// Feed nodes are rendered as larger text labels without spheres
const isFeedNode = (type: string): boolean => type === 'feed';

// Edge colors by type (matching 2D version)
const edgeColors: Record<GraphEdgeType, string> = {
  semantic: '#3b82f6', // blue
  tag: '#8b5cf6', // purple
  source: '#10b981', // green
  temporal: '#6b7280', // gray
};

// Selected node highlight color
const selectedColor = 0xfbbf24; // amber-400

// Transform nodes to 3d-force-graph format
interface Graph3DNode {
  id: string;
  type: GraphNodeType;
  label: string;
  fullLabel: string;
  color: number;
  size: number;
  nodeData: GraphNodeData;
  // 3d-force-graph adds these during simulation
  x?: number;
  y?: number;
  z?: number;
}

interface Graph3DLink {
  source: string;
  target: string;
  type: GraphEdgeType;
  score: number;
  color: string;
}

const transformData = computed(() => {
  const nodes: Graph3DNode[] = props.nodes.map((node) => {
    // Size based on node type
    let size = 6;
    if (node.type === 'tag' && node.data.count) {
      size = Math.min(12, 4 + (node.data.count as number) * 0.5);
    } else if (node.type === 'digest') {
      size = 8;
    }

    return {
      id: node.id,
      type: node.type,
      label: node.label.length > 15 ? node.label.substring(0, 15) + '...' : node.label,
      fullLabel: node.label,
      color: nodeColors[node.type] || nodeColors.digest,
      size,
      nodeData: node.data,
    };
  });

  const links: Graph3DLink[] = props.edges.map((edge) => ({
    source: edge.source,
    target: edge.target,
    type: edge.type,
    score: edge.score,
    color: edgeColors[edge.type] || edgeColors.semantic,
  }));

  return { nodes, links };
});

// Double-click tracking
let lastClickTime = 0;
let lastClickNodeId: string | null = null;
const DOUBLE_CLICK_THRESHOLD = 300; // ms

// Convert hex number to CSS color string
function hexToColor(hex: number): string {
  return `#${hex.toString(16).padStart(6, '0')}`;
}

// Convert Graph3DNode to GraphNode for emit
function toGraphNode(n: Graph3DNode): GraphNode {
  return { id: n.id, type: n.type, label: n.fullLabel, data: n.nodeData };
}

// Initialize the 3D graph
async function initGraph(): Promise<void> {
  if (!containerRef.value) return;

  // Dynamically import 3d-force-graph to avoid SSR issues
  if (!ForceGraph3D) {
    const module = await import('3d-force-graph');
    ForceGraph3D = module.default;
  }

  const width = containerRef.value.clientWidth;
  const height = containerRef.value.clientHeight;

  const graphInstance = ForceGraph3D()(containerRef.value)
    .width(width)
    .height(height)
    .backgroundColor('#0f172a') // Darker background for better text contrast
    .nodeLabel((node: Graph3DNode) =>
      `<div class="bg-gray-900/90 px-2 py-1 rounded text-sm text-white">${node.fullLabel}</div>`
    )
    // Custom node rendering with text labels
    .nodeThreeObject((node: Graph3DNode) => {
      // Create text sprite for node label
      const sprite = new SpriteText(node.label);
      const isSelected = props.selectedNodeId === node.id;

      if (isFeedNode(node.type)) {
        // Feed nodes: large prominent labels as cluster titles
        sprite.color = '#fbbf24'; // amber
        sprite.textHeight = 8;
        sprite.fontWeight = 'bold';
        sprite.backgroundColor = 'rgba(251, 191, 36, 0.15)';
        sprite.padding = 3;
        sprite.borderRadius = 4;
        sprite.borderWidth = 1;
        sprite.borderColor = '#fbbf24';
      } else if (node.type === 'tag') {
        // Tag nodes: medium labels
        sprite.color = hexToColor(isSelected ? selectedColor : node.color);
        sprite.textHeight = 4;
        sprite.backgroundColor = 'rgba(15, 23, 42, 0.7)';
        sprite.padding = 1.5;
        sprite.borderRadius = 2;
      } else {
        // Digest nodes: smaller labels
        sprite.color = hexToColor(isSelected ? selectedColor : node.color);
        sprite.textHeight = 3;
        sprite.backgroundColor = 'rgba(15, 23, 42, 0.7)';
        sprite.padding = 1.5;
        sprite.borderRadius = 2;
      }
      return sprite;
    })
    .nodeThreeObjectExtend((node: Graph3DNode) => !isFeedNode(node.type)) // No sphere for feed nodes
    .nodeColor((node: Graph3DNode) =>
      hexToColor(props.selectedNodeId === node.id ? selectedColor : node.color)
    )
    .nodeVal((node: Graph3DNode) => node.size)
    .nodeResolution(16)
    .linkColor((link: Graph3DLink) => link.color)
    .linkWidth((link: Graph3DLink) => 0.5 + link.score * 2)
    .linkOpacity(0.6)
    .linkDirectionalParticles(1)
    .linkDirectionalParticleWidth((link: Graph3DLink) => link.score * 2)
    .linkDirectionalParticleSpeed(0.005)
    // Performance optimizations
    .warmupTicks(100)
    .cooldownTicks(200)
    .d3AlphaDecay(0.02)
    .d3VelocityDecay(0.3)
    // Event handlers
    .onNodeClick((node: Graph3DNode) => {
      const now = Date.now();
      const isDoubleClick = lastClickNodeId === node.id && now - lastClickTime < DOUBLE_CLICK_THRESHOLD;

      if (isDoubleClick) {
        emit('node-expand', toGraphNode(node));
        lastClickNodeId = null;
        lastClickTime = 0;
      } else {
        emit('node-select', toGraphNode(node));
        lastClickNodeId = node.id;
        lastClickTime = now;
      }
    })
    .onBackgroundClick(() => {
      emit('node-select', null);
    });

  graphInstance.graphData(transformData.value);
  graph.value = graphInstance;
}

// Update graph when data changes
function updateGraph(): void {
  if (!graph.value) return;
  graph.value.graphData(transformData.value);
}

// Helper to adjust camera distance
function adjustCameraDistance(factor: number): void {
  if (!graph.value) return;
  const camera = graph.value.camera();
  const distance = camera.position.length();
  const direction = camera.position.clone().normalize();
  camera.position.copy(direction.multiplyScalar(distance * factor));
}

// Zoom controls (exposed to parent)
function zoomIn(): void {
  adjustCameraDistance(0.8);
}

function zoomOut(): void {
  adjustCameraDistance(1.2);
}

function fitToScreen(): void {
  if (!graph.value) return;
  graph.value.zoomToFit(400, 50);
}

function resetView(): void {
  if (!graph.value) return;
  graph.value.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
}

// Focus on a specific node
function focusOnNode(nodeId: string): void {
  if (!graph.value) return;

  const graphNodes = graph.value.graphData().nodes as Graph3DNode[];
  const node = graphNodes.find((n) => n.id === nodeId);

  if (!node || node.x === undefined || node.y === undefined || node.z === undefined) return;

  const distance = 150;
  const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

  graph.value.cameraPosition(
    { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
    { x: node.x, y: node.y, z: node.z },
    1000
  );
}

// Handle resize
function handleResize(): void {
  if (!containerRef.value || !graph.value) return;
  graph.value.width(containerRef.value.clientWidth).height(containerRef.value.clientHeight);
}

// Watch for data changes
watch(() => [props.nodes, props.edges], updateGraph, { deep: true });

// Watch for selected node changes
watch(
  () => props.selectedNodeId,
  (newId) => {
    if (!graph.value) return;
    // Refresh node colors to update selection highlighting
    graph.value.nodeColor(graph.value.nodeColor());
    // Focus on selected node
    if (newId) {
      focusOnNode(newId);
    }
  }
);

// Lifecycle
onMounted(() => {
  initGraph();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (graph.value) {
    // Clean up Three.js resources
    graph.value._destructor?.();
    graph.value = null;
  }
});

// Expose methods to parent
defineExpose({
  zoomIn,
  zoomOut,
  fitToScreen,
  resetView,
  focusOnNode,
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

/* Override 3d-force-graph tooltip styling */
:deep(.scene-tooltip) {
  font-family: inherit;
}
</style>
