<script setup lang="ts">
/**
 * Reusable pagination component.
 * Displays prev/next buttons and page indicator.
 */
import { ChevronLeft, ChevronRight } from 'lucide-vue-next';

interface Props {
  /** Current page number (1-based) */
  page: number;
  /** Total number of pages */
  totalPages: number;
  /** Whether there's a next page */
  hasNext?: boolean;
  /** Whether there's a previous page */
  hasPrev?: boolean;
  /** Show page numbers between buttons */
  showPageInfo?: boolean;
}

interface Emits {
  (e: 'prev'): void;
  (e: 'next'): void;
  (e: 'page', page: number): void;
}

const props = withDefaults(defineProps<Props>(), {
  showPageInfo: true,
});

defineEmits<Emits>();

// Compute hasNext/hasPrev if not provided
const canGoNext = () => props.hasNext ?? props.page < props.totalPages;
const canGoPrev = () => props.hasPrev ?? props.page > 1;
</script>

<template>
  <div class="flex items-center justify-between">
    <button
      @click="$emit('prev')"
      :disabled="!canGoPrev()"
      class="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-bg-hover disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
    >
      <ChevronLeft :size="16" :stroke-width="2" />
      Previous
    </button>

    <div v-if="showPageInfo" class="text-sm text-text-secondary">
      Page {{ page }} of {{ totalPages }}
    </div>

    <button
      @click="$emit('next')"
      :disabled="!canGoNext()"
      class="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-bg-hover disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
    >
      Next
      <ChevronRight :size="16" :stroke-width="2" />
    </button>
  </div>
</template>
