<script setup lang="ts">
/**
 * Reusable empty state component.
 * Displays when a list or collection has no items.
 */
import { Inbox, type LucideIcon } from 'lucide-vue-next';
import { type Component } from 'vue';
import { strings } from '@/i18n/en';

interface Props {
  /** Main title text */
  title?: string;
  /** Description/subtitle text */
  message?: string;
  /** Icon component to display */
  icon?: LucideIcon | Component;
}

withDefaults(defineProps<Props>(), {
  title: strings.common.empty.title,
  message: strings.common.empty.message,
  icon: () => Inbox,
});
</script>

<template>
  <div
    class="rounded-2xl border border-dashed border-border-subtle bg-bg-surface/50 p-12 text-center"
  >
    <div class="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-bg-elevated">
      <component :is="icon" :size="32" class="text-text-muted" :stroke-width="2" />
    </div>
    <h3 class="mb-2 text-lg font-semibold text-text-primary">
      {{ title }}
    </h3>
    <p class="mx-auto max-w-sm text-sm text-text-muted">
      {{ message }}
    </p>
    <!-- Slot for action button -->
    <div v-if="$slots.action" class="mt-6">
      <slot name="action" />
    </div>
  </div>
</template>
