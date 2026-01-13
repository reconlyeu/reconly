<script setup lang="ts">
/**
 * Reusable error state component.
 * Displays a consistent error message with optional retry action.
 */
import { CircleAlert, RefreshCw } from 'lucide-vue-next';

interface Props {
  /** Name of the entity that failed to load (e.g., 'digests', 'sources') */
  entityName?: string;
  /** Error message or Error object */
  error?: string | Error | null;
  /** Show retry button */
  showRetry?: boolean;
}

interface Emits {
  (e: 'retry'): void;
}

const props = withDefaults(defineProps<Props>(), {
  entityName: 'data',
  showRetry: false,
});

defineEmits<Emits>();

const errorMessage = (): string => {
  if (!props.error) return 'An unknown error occurred';
  if (typeof props.error === 'string') return props.error;
  return props.error.message || 'An unknown error occurred';
};
</script>

<template>
  <div
    class="rounded-2xl border border-status-failed/20 bg-status-failed/5 p-8 text-center"
  >
    <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-status-failed/10">
      <CircleAlert :size="32" class="text-status-failed" :stroke-width="2" />
    </div>
    <h3 class="mb-2 text-lg font-semibold text-text-primary">
      Failed to load {{ entityName }}
    </h3>
    <p class="text-sm text-status-failed">
      {{ errorMessage() }}
    </p>
    <button
      v-if="showRetry"
      @click="$emit('retry')"
      class="mt-4 inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-bg-hover focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
    >
      <RefreshCw :size="16" :stroke-width="2" />
      Try Again
    </button>
  </div>
</template>
