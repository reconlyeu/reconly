<script setup lang="ts">
import { ref, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { strings } from '@/i18n/en';
import { feedRunsApi, feedsApi, type FeedRunFilters } from '@/services/api';
import FeedRunFiltersComponent from './FeedRunFilters.vue';
import FeedRunTable from './FeedRunTable.vue';
import type { FeedRunStatus } from '@/types/entities';

const filters = ref<FeedRunFilters>({});
const currentPage = ref(1);
const pageSize = 20;

const { data: feedsData } = useQuery({
  queryKey: ['feeds'],
  queryFn: () => feedsApi.list(),
});

const feeds = computed(() => feedsData.value || []);

const { data: runsData, isLoading, error } = useQuery({
  queryKey: ['feed-runs', filters.value, currentPage.value],
  queryFn: () => feedRunsApi.list(filters.value, pageSize, (currentPage.value - 1) * pageSize),
});

const runs = computed(() => runsData.value?.items || []);
const total = computed(() => runsData.value?.total || 0);
const totalPages = computed(() => Math.ceil(total.value / pageSize));

const handleFilterChange = (newFilters: FeedRunFilters) => {
  filters.value = newFilters;
  currentPage.value = 1;
};

const handlePageChange = (page: number) => {
  currentPage.value = page;
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-text-primary">{{ strings.feedRuns.title }}</h1>
      <p class="mt-1 text-sm text-text-secondary">
        {{ strings.feedRuns.subtitle }}
      </p>
    </div>

    <!-- Filters -->
    <FeedRunFiltersComponent
      :feeds="feeds"
      :filters="filters"
      @update:filters="handleFilterChange"
    />

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-primary"></div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="bg-status-error/10 text-status-error p-4 rounded-lg">
      {{ strings.errors.generic }}
    </div>

    <!-- Empty state -->
    <div v-else-if="runs.length === 0" class="text-center py-12 text-text-secondary">
      {{ strings.feedRuns.noRuns }}
    </div>

    <!-- Feed runs table -->
    <template v-else>
      <FeedRunTable :runs="runs" />

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="mt-6 flex items-center justify-between">
        <div class="text-sm text-text-secondary">
          Showing {{ (currentPage - 1) * pageSize + 1 }} to {{ Math.min(currentPage * pageSize, total) }} of {{ total }} runs
        </div>
        <div class="flex gap-2">
          <button
            @click="handlePageChange(currentPage - 1)"
            :disabled="currentPage === 1"
            class="px-3 py-1 rounded border border-border-subtle text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-bg-hover"
          >
            Previous
          </button>
          <span class="px-3 py-1 text-sm text-text-secondary">
            Page {{ currentPage }} of {{ totalPages }}
          </span>
          <button
            @click="handlePageChange(currentPage + 1)"
            :disabled="currentPage >= totalPages"
            class="px-3 py-1 rounded border border-border-subtle text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-bg-hover"
          >
            Next
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
