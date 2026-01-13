<script setup lang="ts">
/**
 * Extensions section for the Settings page.
 * Lists installed extensions with their status and toggle controls.
 * Configuration is handled in the Exports tab (for exporters).
 */
import { computed, ref } from 'vue';
import { Puzzle, Terminal, RefreshCw, Store } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import { useExtensionsList, useToggleExtension } from '@/composables/useExtensions';
import { useToast } from '@/composables/useToast';
import ExtensionCard from './ExtensionCard.vue';
import ExtensionCatalogModal from './ExtensionCatalogModal.vue';
import type { ExtensionType } from '@/types/entities';

const { data: extensions, isLoading, isError, error, refetch } = useExtensionsList();
const toast = useToast();

// Catalog modal state
const isCatalogOpen = ref(false);

// Toggle mutation
const toggleMutation = useToggleExtension({
  onSuccess: (data) => {
    toast.success(
      data.enabled
        ? `${data.metadata.name} enabled`
        : `${data.metadata.name} disabled`
    );
  },
  onError: (err) => {
    toast.error(`Failed to toggle extension: ${err.message}`);
  },
});

const handleToggle = (name: string, type: string, enabled: boolean) => {
  toggleMutation.mutate({
    type: type as ExtensionType,
    name,
    enabled,
  });
};

// Check if we have any extensions
const hasExtensions = computed(() => {
  return extensions.value && extensions.value.length > 0;
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold text-text-primary">
          {{ strings.settings.extensions.title }}
        </h2>
        <p class="text-sm text-text-muted">
          {{ strings.settings.extensions.description }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="isCatalogOpen = true"
          class="inline-flex items-center gap-2 rounded-lg bg-accent-primary/10 px-3 py-2 text-sm font-medium text-accent-primary hover:bg-accent-primary/20 transition-colors"
        >
          <Store :size="16" />
          {{ strings.settings.extensions.browseCatalog }}
        </button>
        <button
          @click="() => refetch()"
          class="inline-flex items-center gap-2 rounded-lg bg-bg-surface px-3 py-2 text-sm font-medium text-text-secondary hover:bg-bg-elevated hover:text-text-primary transition-colors"
          :disabled="isLoading"
        >
          <RefreshCw :size="16" :class="{ 'animate-spin': isLoading }" />
          Refresh
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <div class="flex items-center gap-3 text-text-muted">
        <RefreshCw :size="20" class="animate-spin" />
        <span>Loading extensions...</span>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="rounded-lg bg-red-500/10 border border-red-500/20 p-4">
      <p class="text-sm text-red-400">
        Failed to load extensions: {{ error?.message || 'Unknown error' }}
      </p>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!hasExtensions"
      class="rounded-2xl border border-border-subtle bg-bg-elevated p-8 text-center"
    >
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-bg-surface">
        <Puzzle :size="32" class="text-text-muted" />
      </div>
      <h3 class="mt-4 text-lg font-semibold text-text-primary">
        {{ strings.settings.extensions.noExtensions }}
      </h3>
      <p class="mt-2 text-sm text-text-muted">
        {{ strings.settings.extensions.noExtensionsDescription }}
      </p>
      <div class="mt-4 inline-flex items-center gap-2 rounded-lg bg-bg-surface px-4 py-2 font-mono text-sm text-text-secondary">
        <Terminal :size="16" />
        {{ strings.settings.extensions.installHint }}
      </div>
    </div>

    <!-- Extensions grid -->
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <ExtensionCard
        v-for="ext in extensions"
        :key="`${ext.type}-${ext.name}`"
        :extension="ext"
        :is-toggling="toggleMutation.isPending.value"
        @toggle="handleToggle"
      />
    </div>

    <!-- Install hint (shown when extensions exist) -->
    <div
      v-if="hasExtensions"
      class="rounded-lg bg-bg-elevated border border-border-subtle p-4"
    >
      <p class="text-sm text-text-muted">
        {{ strings.settings.extensions.noExtensionsDescription }}
      </p>
      <div class="mt-2 inline-flex items-center gap-2 rounded-lg bg-bg-surface px-3 py-1.5 font-mono text-xs text-text-secondary">
        <Terminal :size="14" />
        {{ strings.settings.extensions.installHint }}
      </div>
    </div>

    <!-- Catalog Modal -->
    <ExtensionCatalogModal
      :is-open="isCatalogOpen"
      @close="isCatalogOpen = false"
    />
  </div>
</template>
