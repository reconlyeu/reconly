<script setup lang="ts">
/**
 * Bulk action bar for multi-select operations.
 * Shows selection count and action buttons.
 */
import { X, Trash2 } from 'lucide-vue-next';

interface Props {
  /** Number of items selected */
  count: number;
  /** Entity name for display (e.g., 'digest', 'source') */
  entityName?: string;
  /** Show delete button */
  showDelete?: boolean;
  /** Delete button is loading */
  isDeleting?: boolean;
}

interface Emits {
  (e: 'deselect-all'): void;
  (e: 'delete'): void;
}

withDefaults(defineProps<Props>(), {
  entityName: 'item',
  showDelete: true,
  isDeleting: false,
});

defineEmits<Emits>();

const pluralize = (count: number, singular: string): string => {
  return count === 1 ? singular : `${singular}s`;
};
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-4"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-4"
  >
    <div
      v-if="count > 0"
      class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 transform"
    >
      <div
        class="flex items-center gap-4 rounded-xl border border-border-subtle bg-bg-elevated px-5 py-3 shadow-2xl shadow-black/20"
      >
        <!-- Selection count -->
        <span class="text-sm font-medium text-text-primary">
          {{ count }} {{ pluralize(count, entityName) }} selected
        </span>

        <!-- Divider -->
        <div class="h-5 w-px bg-border-subtle" />

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <!-- Deselect All -->
          <button
            @click="$emit('deselect-all')"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-text-muted transition-all hover:bg-bg-hover hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-elevated"
          >
            <X :size="16" :stroke-width="2" />
            Clear
          </button>

          <!-- Delete Selected -->
          <button
            v-if="showDelete"
            @click="$emit('delete')"
            :disabled="isDeleting"
            class="flex items-center gap-1.5 rounded-lg bg-status-failed/10 px-3 py-1.5 text-sm font-medium text-status-failed transition-all hover:bg-status-failed/20 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-status-failed focus:ring-offset-2 focus:ring-offset-bg-elevated"
          >
            <Trash2 :size="16" :stroke-width="2" />
            {{ isDeleting ? 'Deleting...' : 'Delete' }}
          </button>

          <!-- Slot for additional actions -->
          <slot name="actions" />
        </div>
      </div>
    </div>
  </Transition>
</template>
