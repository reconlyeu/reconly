<script setup lang="ts">
/**
 * Reusable empty state component.
 * Displays when a list or collection has no items.
 */
import { Inbox, Lightbulb, ExternalLink, type LucideIcon } from 'lucide-vue-next';
import { type Component } from 'vue';
import { strings } from '@/i18n/en';

interface Props {
  /** Main title text */
  title?: string;
  /** Description/subtitle text */
  message?: string;
  /** Icon component to display */
  icon?: LucideIcon | Component;
  /** Optional tip text shown with lightbulb icon */
  tip?: string;
  /** Optional URL for a "Learn more" link */
  learnMoreUrl?: string;
  /** Label for the learn more link */
  learnMoreLabel?: string;
}

withDefaults(defineProps<Props>(), {
  title: strings.common.empty.title,
  message: strings.common.empty.message,
  icon: () => Inbox,
  tip: undefined,
  learnMoreUrl: undefined,
  learnMoreLabel: 'Learn more',
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
    <!-- Optional learn more link -->
    <div v-if="learnMoreUrl" class="mt-4">
      <a
        :href="learnMoreUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1.5 text-sm text-accent-primary hover:text-accent-primary/80 transition-colors"
      >
        {{ learnMoreLabel }}
        <ExternalLink :size="14" :stroke-width="2" />
      </a>
    </div>
    <!-- Optional tip with lightbulb icon -->
    <div v-if="tip" class="mt-6 flex items-center justify-center gap-2 text-xs text-text-muted">
      <Lightbulb :size="14" :stroke-width="2" class="text-amber-500" />
      <span>{{ tip }}</span>
    </div>
  </div>
</template>
