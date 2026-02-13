<script setup lang="ts">
/**
 * Base list component with loading, error, and empty states.
 * Renders items in a responsive grid layout.
 */
import LoadingSkeleton from './LoadingSkeleton.vue';
import ErrorState from './ErrorState.vue';
import EmptyState from './EmptyState.vue';
import Pagination from './Pagination.vue';
import { type Component } from 'vue';

interface Props {
  /** Loading state */
  isLoading?: boolean;
  /** Error state */
  isError?: boolean;
  /** Error object or message */
  error?: Error | string | null;
  /** Items to render */
  items: unknown[];
  /** Entity name for messages (e.g., 'digest', 'source') */
  entityName?: string;
  /** Number of grid columns on medium screens */
  gridCols?: 1 | 2 | 3 | 4;
  /** Number of skeleton items to show while loading */
  skeletonCount?: number;
  /** Skeleton item height */
  skeletonHeight?: string;
  /** Empty state title */
  emptyTitle?: string;
  /** Empty state message */
  emptyMessage?: string;
  /** Empty state icon */
  emptyIcon?: Component;
  /** Empty state tip */
  emptyTip?: string;
  /** Empty state learn more URL */
  emptyLearnMoreUrl?: string;
  /** Show pagination */
  showPagination?: boolean;
  /** Current page */
  page?: number;
  /** Total pages */
  totalPages?: number;
  /** Has next page */
  hasNext?: boolean;
  /** Has previous page */
  hasPrev?: boolean;
}

interface Emits {
  (e: 'retry'): void;
  (e: 'prev-page'): void;
  (e: 'next-page'): void;
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
  isError: false,
  entityName: 'item',
  gridCols: 2,
  skeletonCount: 6,
  skeletonHeight: 'h-80',
  showPagination: false,
  page: 1,
  totalPages: 1,
});

defineEmits<Emits>();

const gridColsClass = {
  1: 'md:grid-cols-1',
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-2 lg:grid-cols-3',
  4: 'md:grid-cols-2 lg:grid-cols-4',
};
</script>

<template>
  <div>
    <!-- Loading State -->
    <div v-if="isLoading" class="grid gap-6" :class="gridColsClass[gridCols]">
      <div
        v-for="i in skeletonCount"
        :key="i"
        class="animate-pulse rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated/50 to-bg-surface/30"
        :class="skeletonHeight"
      >
        <div class="p-6">
          <div class="mb-4 flex gap-2">
            <div class="h-6 w-24 rounded-full bg-bg-hover" />
            <div class="h-6 w-20 rounded-full bg-bg-hover" />
          </div>
          <div class="mb-3 h-7 w-3/4 rounded bg-bg-hover" />
          <div class="mb-2 h-4 w-full rounded bg-bg-hover" />
          <div class="mb-2 h-4 w-full rounded bg-bg-hover" />
          <div class="mb-4 h-4 w-2/3 rounded bg-bg-hover" />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <ErrorState
      v-else-if="isError"
      :entity-name="entityName + 's'"
      :error="error"
      show-retry
      @retry="$emit('retry')"
    />

    <!-- Empty State -->
    <EmptyState
      v-else-if="!items || items.length === 0"
      :title="emptyTitle || `No ${entityName}s found`"
      :message="emptyMessage || `${entityName.charAt(0).toUpperCase() + entityName.slice(1)}s will appear here once they are created.`"
      :icon="emptyIcon"
      :tip="emptyTip"
      :learn-more-url="emptyLearnMoreUrl"
    >
      <template #action>
        <slot name="empty-action" />
      </template>
    </EmptyState>

    <!-- Items Grid -->
    <template v-else>
      <div class="grid gap-6" :class="gridColsClass[gridCols]">
        <slot :items="items" />
      </div>

      <!-- Pagination -->
      <div v-if="showPagination && totalPages > 1" class="mt-8">
        <Pagination
          :page="page"
          :total-pages="totalPages"
          :has-next="hasNext"
          :has-prev="hasPrev"
          @prev="$emit('prev-page')"
          @next="$emit('next-page')"
        />
      </div>

      <!-- Extra pagination slot for custom pagination -->
      <slot name="pagination" />
    </template>
  </div>
</template>
