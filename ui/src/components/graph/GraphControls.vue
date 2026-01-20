<script setup lang="ts">
/**
 * GraphControls - Filter and layout controls for the knowledge graph
 *
 * Provides:
 * - Layout switcher (force/hierarchical/radial)
 * - Zoom controls
 * - Filter controls (feed, date range, tags, similarity)
 * - Export buttons
 */

import { ref, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { feedsApi, tagsApi } from '@/services/api';
import { strings } from '@/i18n/en';
import type { GraphLayoutType, GraphViewMode, GraphEdgeType } from '@/types/entities';
import {
  LayoutGrid,
  GitBranch,
  Circle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCcw,
  Download,
  FileJson,
  Filter,
  X,
  ChevronDown,
  Box,
  Square,
} from 'lucide-vue-next';

interface Props {
  layout: GraphLayoutType;
  viewMode: GraphViewMode;
  minSimilarity: number;
  includeTags: boolean;
  depth: number;
  feedFilter: number | null;
  fromDate: string;
  toDate: string;
  tagFilter: string[];
  relationshipTypes: GraphEdgeType[];
  nodeCount: number;
  edgeCount: number;
}

interface Emits {
  (e: 'update:layout', value: GraphLayoutType): void;
  (e: 'update:viewMode', value: GraphViewMode): void;
  (e: 'update:minSimilarity', value: number): void;
  (e: 'update:includeTags', value: boolean): void;
  (e: 'update:depth', value: number): void;
  (e: 'update:feedFilter', value: number | null): void;
  (e: 'update:fromDate', value: string): void;
  (e: 'update:toDate', value: string): void;
  (e: 'update:tagFilter', value: string[]): void;
  (e: 'update:relationshipTypes', value: GraphEdgeType[]): void;
  (e: 'zoom-in'): void;
  (e: 'zoom-out'): void;
  (e: 'fit-to-screen'): void;
  (e: 'reset-view'): void;
  (e: 'export-png'): void;
  (e: 'export-json'): void;
  (e: 'clear-filters'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const showFilters = ref(false);

// Fetch feeds for filter dropdown
const { data: feeds } = useQuery({
  queryKey: ['feeds'],
  queryFn: () => feedsApi.list(),
  staleTime: 60000,
});

// Fetch tags for filter
const { data: tags } = useQuery({
  queryKey: ['tags'],
  queryFn: () => tagsApi.list(),
  staleTime: 60000,
});

const layoutOptions: { value: GraphLayoutType; label: string; icon: typeof LayoutGrid }[] = [
  { value: 'force', label: strings.knowledgeGraph.layouts.force, icon: GitBranch },
  { value: 'hierarchical', label: strings.knowledgeGraph.layouts.hierarchical, icon: LayoutGrid },
  { value: 'radial', label: strings.knowledgeGraph.layouts.radial, icon: Circle },
];

const viewModeOptions: { value: GraphViewMode; label: string; icon: typeof Box }[] = [
  { value: '2d', label: '2D', icon: Square },
  { value: '3d', label: '3D', icon: Box },
];

const relationshipTypeOptions: { value: GraphEdgeType; label: string }[] = [
  { value: 'semantic', label: strings.knowledgeGraph.edgeTypes.semantic },
  { value: 'tag', label: strings.knowledgeGraph.edgeTypes.tag },
  { value: 'source', label: strings.knowledgeGraph.edgeTypes.source },
];

// Default relationship types (semantic only for cleaner visualization)
const defaultRelationshipTypes: GraphEdgeType[] = ['semantic'];

// Check if relationship types differ from default
const relationshipTypesChanged = computed(() => {
  if (props.relationshipTypes.length !== defaultRelationshipTypes.length) return true;
  return !defaultRelationshipTypes.every(t => props.relationshipTypes.includes(t));
});

const hasActiveFilters = computed(() => {
  return (
    props.feedFilter !== null ||
    props.fromDate !== '' ||
    props.toDate !== '' ||
    props.tagFilter.length > 0 ||
    props.minSimilarity !== 0.5 ||
    !props.includeTags ||
    relationshipTypesChanged.value
  );
});

const handleTagToggle = (tagName: string) => {
  const currentTags = [...props.tagFilter];
  const index = currentTags.indexOf(tagName);
  if (index === -1) {
    currentTags.push(tagName);
  } else {
    currentTags.splice(index, 1);
  }
  emit('update:tagFilter', currentTags);
};

const handleRelationshipTypeToggle = (type: GraphEdgeType) => {
  const currentTypes = [...props.relationshipTypes];
  const index = currentTypes.indexOf(type);
  if (index === -1) {
    currentTypes.push(type);
  } else {
    // Don't allow deselecting all types - keep at least one
    if (currentTypes.length > 1) {
      currentTypes.splice(index, 1);
    }
  }
  emit('update:relationshipTypes', currentTypes);
};

const clearAllFilters = () => {
  emit('update:feedFilter', null);
  emit('update:fromDate', '');
  emit('update:toDate', '');
  emit('update:tagFilter', []);
  emit('update:minSimilarity', 0.5);
  emit('update:includeTags', true);
  emit('update:relationshipTypes', [...defaultRelationshipTypes]);
  emit('clear-filters');
};
</script>

<template>
  <div class="relative flex flex-col gap-3">
    <!-- Top Controls Row -->
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <!-- View Mode Toggle (2D/3D) - placed first so it doesn't jump when layout options disappear -->
      <div class="flex items-center gap-2">
        <span class="text-sm text-text-secondary">{{ strings.knowledgeGraph.controls.viewMode }}:</span>
        <div class="flex rounded-lg border border-border-subtle overflow-hidden">
          <button
            v-for="option in viewModeOptions"
            :key="option.value"
            @click="emit('update:viewMode', option.value)"
            class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors"
            :class="[
              props.viewMode === option.value
                ? 'bg-accent-primary text-white'
                : 'bg-bg-surface text-text-secondary hover:bg-bg-hover hover:text-text-primary',
            ]"
            :title="option.label"
          >
            <component :is="option.icon" class="w-4 h-4" />
            <span>{{ option.label }}</span>
          </button>
        </div>
      </div>

      <!-- Layout Switcher (only for 2D view) -->
      <div v-if="props.viewMode === '2d'" class="flex items-center gap-2">
        <span class="text-sm text-text-secondary">{{ strings.knowledgeGraph.controls.layout }}:</span>
        <div class="flex rounded-lg border border-border-subtle overflow-hidden">
          <button
            v-for="option in layoutOptions"
            :key="option.value"
            @click="emit('update:layout', option.value)"
            class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors"
            :class="[
              props.layout === option.value
                ? 'bg-accent-primary text-white'
                : 'bg-bg-surface text-text-secondary hover:bg-bg-hover hover:text-text-primary',
            ]"
            :title="option.label"
          >
            <component :is="option.icon" class="w-4 h-4" />
            <span class="hidden sm:inline">{{ option.label }}</span>
          </button>
        </div>
      </div>

      <!-- Stats -->
      <div class="flex items-center gap-4 text-sm text-text-secondary">
        <span>
          {{ strings.knowledgeGraph.stats.nodes }}: <strong class="text-text-primary">{{ props.nodeCount }}</strong>
        </span>
        <span>
          {{ strings.knowledgeGraph.stats.edges }}: <strong class="text-text-primary">{{ props.edgeCount }}</strong>
        </span>
      </div>

      <!-- Zoom Controls -->
      <div class="flex items-center gap-1">
        <button
          @click="emit('zoom-in')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.zoomIn"
        >
          <ZoomIn class="w-5 h-5" />
        </button>
        <button
          @click="emit('zoom-out')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.zoomOut"
        >
          <ZoomOut class="w-5 h-5" />
        </button>
        <button
          @click="emit('fit-to-screen')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.fitToScreen"
        >
          <Maximize2 class="w-5 h-5" />
        </button>
        <button
          @click="emit('reset-view')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.resetView"
        >
          <RotateCcw class="w-5 h-5" />
        </button>
        <div class="w-px h-6 bg-border-subtle mx-1" />
        <button
          @click="emit('export-png')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.exportPng"
        >
          <Download class="w-5 h-5" />
        </button>
        <button
          @click="emit('export-json')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          :title="strings.knowledgeGraph.controls.exportJson"
        >
          <FileJson class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Filter Toggle -->
    <div class="flex items-center gap-2">
      <button
        @click="showFilters = !showFilters"
        class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors"
        :class="[
          showFilters || hasActiveFilters
            ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
            : 'border-border-subtle bg-bg-surface text-text-secondary hover:bg-bg-hover',
        ]"
      >
        <Filter class="w-4 h-4" />
        <span class="text-sm font-medium">{{ strings.knowledgeGraph.controls.filters }}</span>
        <ChevronDown
          class="w-4 h-4 transition-transform"
          :class="showFilters ? 'rotate-180' : ''"
        />
      </button>
      <button
        v-if="hasActiveFilters"
        @click="clearAllFilters"
        class="flex items-center gap-1 px-2 py-1 rounded text-sm text-text-secondary hover:text-status-failed transition-colors"
      >
        <X class="w-4 h-4" />
        {{ strings.knowledgeGraph.filters.clearFilters }}
      </button>
    </div>

    <!-- Filter Panel (overlay) -->
    <div
      v-if="showFilters"
      class="absolute left-0 right-0 top-full z-20 mt-2 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-bg-surface rounded-lg border border-border-subtle shadow-lg"
    >
      <!-- Feed Filter -->
      <div class="space-y-2">
        <label class="text-sm font-medium text-text-secondary">{{ strings.knowledgeGraph.filters.feed }}</label>
        <select
          :value="props.feedFilter"
          @change="emit('update:feedFilter', ($event.target as HTMLSelectElement).value ? parseInt(($event.target as HTMLSelectElement).value) : null)"
          class="w-full rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        >
          <option :value="null">{{ strings.knowledgeGraph.filters.allFeeds }}</option>
          <option v-for="feed in feeds" :key="feed.id" :value="feed.id">
            {{ feed.name }}
          </option>
        </select>
      </div>

      <!-- Date Range -->
      <div class="space-y-2">
        <label class="text-sm font-medium text-text-secondary">{{ strings.knowledgeGraph.filters.dateRange }}</label>
        <div class="flex gap-2">
          <input
            type="date"
            :value="props.fromDate"
            @input="emit('update:fromDate', ($event.target as HTMLInputElement).value)"
            class="flex-1 rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :placeholder="strings.knowledgeGraph.filters.fromDate"
          />
          <input
            type="date"
            :value="props.toDate"
            @input="emit('update:toDate', ($event.target as HTMLInputElement).value)"
            class="flex-1 rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
            :placeholder="strings.knowledgeGraph.filters.toDate"
          />
        </div>
      </div>

      <!-- Similarity Threshold -->
      <div class="space-y-2">
        <label class="text-sm font-medium text-text-secondary">
          {{ strings.knowledgeGraph.controls.minSimilarity }}: {{ (props.minSimilarity * 100).toFixed(0) }}%
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          :value="props.minSimilarity"
          @input="emit('update:minSimilarity', parseFloat(($event.target as HTMLInputElement).value))"
          class="w-full h-2 rounded-lg appearance-none cursor-pointer bg-bg-elevated accent-accent-primary"
        />
      </div>

      <!-- Depth Control -->
      <div class="space-y-2">
        <label class="text-sm font-medium text-text-secondary">
          {{ strings.knowledgeGraph.controls.depth }}: {{ props.depth }}
        </label>
        <input
          type="range"
          min="1"
          max="4"
          step="1"
          :value="props.depth"
          @input="emit('update:depth', parseInt(($event.target as HTMLInputElement).value))"
          class="w-full h-2 rounded-lg appearance-none cursor-pointer bg-bg-elevated accent-accent-primary"
        />
      </div>

      <!-- Relationship Types -->
      <div class="space-y-2 md:col-span-2">
        <label class="text-sm font-medium text-text-secondary">{{ strings.knowledgeGraph.filters.relationshipTypes }}</label>
        <div class="flex flex-wrap gap-3">
          <label
            v-for="option in relationshipTypeOptions"
            :key="option.value"
            class="flex items-center gap-2 cursor-pointer"
          >
            <input
              type="checkbox"
              :checked="props.relationshipTypes.includes(option.value)"
              @change="handleRelationshipTypeToggle(option.value)"
              class="w-4 h-4 rounded border-border-subtle bg-bg-elevated text-accent-primary focus:ring-accent-primary focus:ring-offset-bg-base"
            />
            <span class="text-sm text-text-secondary">{{ option.label }}</span>
          </label>
        </div>
      </div>

      <!-- Tag Filter -->
      <div class="space-y-2 md:col-span-3">
        <label class="text-sm font-medium text-text-secondary">{{ strings.knowledgeGraph.filters.tags }}</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="tag in tags?.slice(0, 20)"
            :key="tag.id"
            @click="handleTagToggle(tag.name)"
            class="px-2 py-1 rounded-full text-xs font-medium transition-colors"
            :class="[
              props.tagFilter.includes(tag.name)
                ? 'bg-accent-primary text-white'
                : 'bg-bg-elevated text-text-secondary hover:bg-bg-hover',
            ]"
          >
            {{ tag.name }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
