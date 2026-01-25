<script setup lang="ts">
/**
 * Fetcher Settings Component
 *
 * Provides UI for configuring fetcher settings including:
 * - Fetcher list with cards showing status
 * - Fetcher-specific configuration via FetcherConfigPanel
 *
 * Supports deep-linking via useSettingsNavigation composable
 */
import { ref, watch, computed, onMounted } from 'vue';
import { ArrowRightToLine } from 'lucide-vue-next';
import BaseList from '@/components/common/BaseList.vue';
import FetcherCard from './FetcherCard.vue';
import FetcherConfigPanel from './FetcherConfigPanel.vue';
import { useFetchersList } from '@/composables/useFetchers';
import { useSettingsNavigation } from '@/composables/useSettingsNavigation';
import { strings } from '@/i18n/en';
import type { Fetcher } from '@/types/entities';

// Get deep-link target from navigation composable
const { consumeFetcherTarget } = useSettingsNavigation();
const deepLinkFetcher = ref<string | null>(null);

// Check for deep-link target on mount
onMounted(() => {
  const target = consumeFetcherTarget();
  if (target) {
    deepLinkFetcher.value = target;
  }
});

// Selected fetcher name
const selectedFetcherName = ref<string | null>(null);

// Fetch fetchers list using the composable
const { data: fetchersRaw, isLoading, isError, error, refetch } = useFetchersList();

// Filter out fetchers that shouldn't appear in settings (e.g., Agent has its own tab)
const fetchers = computed(() => {
  if (!fetchersRaw.value) return null;
  return fetchersRaw.value.filter(f => f.metadata?.show_in_settings !== false);
});

// Get the currently selected fetcher object
const selectedFetcher = computed<Fetcher | null>(() => {
  if (!fetchers.value || !selectedFetcherName.value) return null;
  return fetchers.value.find(f => f.name === selectedFetcherName.value) || null;
});

// Watch for deep-link fetcher and apply when fetchers list is available
watch(
  [() => fetchers.value, deepLinkFetcher],
  ([fetchersList, targetFetcher]) => {
    if (targetFetcher && fetchersList) {
      // Check if the target fetcher exists in the list
      const exists = fetchersList.some(f => f.name === targetFetcher);
      if (exists) {
        selectedFetcherName.value = targetFetcher;
        // Clear the deep link so we don't keep overriding
        deepLinkFetcher.value = null;
      }
    }
  },
  { immediate: true }
);

// Auto-select first fetcher when list loads if none selected
watch(
  () => fetchers.value,
  (fetchersList) => {
    if (fetchersList && fetchersList.length > 0 && !selectedFetcherName.value && !deepLinkFetcher.value) {
      selectedFetcherName.value = fetchersList[0].name;
    }
  },
  { immediate: true }
);

// Handle fetcher selection
const handleSelect = (fetcherName: string) => {
  selectedFetcherName.value = fetcherName;
};
</script>

<template>
  <div class="space-y-6">
    <!-- Fetcher Selection Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
      <div class="flex items-center gap-3 mb-6">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10">
          <ArrowRightToLine :size="20" class="text-purple-400" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-text-primary">{{ strings.settings.fetchers.contentFetchers }}</h2>
          <p class="text-sm text-text-muted">{{ strings.settings.fetchers.selectFetcher }}</p>
        </div>
      </div>

      <BaseList
        :items="fetchers || []"
        :is-loading="isLoading"
        :is-error="isError"
        :error="error"
        entity-name="fetcher"
        :grid-cols="2"
        :skeleton-count="4"
        skeleton-height="h-48"
        :empty-title="strings.settings.fetchers.noFetchers"
        :empty-message="strings.settings.fetchers.noFetchersDescription"
        :empty-icon="ArrowRightToLine"
        @retry="refetch"
      >
        <template #default="{ items }">
          <FetcherCard
            v-for="fetcher in (items as Fetcher[])"
            :key="fetcher.name"
            :fetcher="fetcher"
            :selected="selectedFetcherName === fetcher.name"
            @select="handleSelect"
          />
        </template>

        <template #empty-action>
          <p class="text-sm text-text-muted">
            {{ strings.settings.fetchers.checkInstallation }}
          </p>
        </template>
      </BaseList>
    </div>

    <!-- Fetcher Configuration Panel -->
    <FetcherConfigPanel
      v-if="selectedFetcher"
      :fetcher="selectedFetcher"
    />
  </div>
</template>
