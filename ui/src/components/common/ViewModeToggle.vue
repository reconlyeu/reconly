<script setup lang="ts">
/**
 * Toggle button for switching between card and table view modes.
 */
import { LayoutGrid, List } from 'lucide-vue-next';
import type { ViewMode } from '@/composables/useViewMode';
import { strings } from '@/i18n/en';

interface Props {
  modelValue: ViewMode;
}

interface Emits {
  (e: 'update:modelValue', value: ViewMode): void;
}

defineProps<Props>();
const emit = defineEmits<Emits>();

const setMode = (mode: ViewMode) => {
  emit('update:modelValue', mode);
};
</script>

<template>
  <div class="inline-flex rounded-lg border border-border-subtle bg-bg-surface p-1">
    <button
      type="button"
      @click="setMode('card')"
      class="flex items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-1 focus:ring-offset-bg-surface"
      :class="
        modelValue === 'card'
          ? 'bg-bg-hover text-text-primary shadow-sm'
          : 'text-text-muted hover:text-text-secondary'
      "
      :aria-pressed="modelValue === 'card'"
      :title="strings.common.viewMode.card"
    >
      <LayoutGrid :size="18" :stroke-width="2" />
    </button>
    <button
      type="button"
      @click="setMode('table')"
      class="flex items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-1 focus:ring-offset-bg-surface"
      :class="
        modelValue === 'table'
          ? 'bg-bg-hover text-text-primary shadow-sm'
          : 'text-text-muted hover:text-text-secondary'
      "
      :aria-pressed="modelValue === 'table'"
      :title="strings.common.viewMode.table"
    >
      <List :size="18" :stroke-width="2" />
    </button>
  </div>
</template>
