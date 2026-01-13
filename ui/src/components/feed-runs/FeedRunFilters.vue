<script setup lang="ts">
import { ref, watch } from 'vue';
import { Filter, X } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { Feed, FeedRunStatus } from '@/types/entities';
import type { FeedRunFilters } from '@/services/api';

const props = defineProps<{
  feeds: Feed[];
  filters: FeedRunFilters;
}>();

const emit = defineEmits<{
  'update:filters': [filters: FeedRunFilters];
}>();

const localFilters = ref<FeedRunFilters>({ ...props.filters });

const statusOptions: { value: FeedRunStatus | ''; label: string }[] = [
  { value: '', label: strings.feedRuns.filters.allStatuses },
  { value: 'pending', label: strings.status.pending },
  { value: 'running', label: strings.status.running },
  { value: 'completed', label: strings.status.completed },
  { value: 'failed', label: strings.status.failed },
];

watch(localFilters, (newFilters) => {
  const cleaned: FeedRunFilters = {};
  if (newFilters.feed_id) cleaned.feed_id = newFilters.feed_id;
  if (newFilters.status) cleaned.status = newFilters.status;
  if (newFilters.from_date) cleaned.from_date = newFilters.from_date;
  if (newFilters.to_date) cleaned.to_date = newFilters.to_date;
  emit('update:filters', cleaned);
}, { deep: true });

const clearFilters = () => {
  localFilters.value = {};
};

const hasFilters = () => {
  return Object.values(localFilters.value).some(v => v !== undefined && v !== '');
};
</script>

<template>
  <div class="mb-6 p-4 bg-bg-surface rounded-lg border border-border-subtle">
    <div class="flex items-center gap-2 mb-4">
      <Filter :size="16" class="text-text-secondary" />
      <span class="text-sm font-medium text-text-primary">Filters</span>
      <button
        v-if="hasFilters()"
        @click="clearFilters"
        class="ml-auto text-xs text-accent-primary hover:text-accent-primary-hover flex items-center gap-1"
      >
        <X :size="14" />
        {{ strings.feedRuns.filters.clearFilters }}
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <!-- Feed filter -->
      <div>
        <label class="block text-xs text-text-secondary mb-1">Feed</label>
        <select
          v-model.number="localFilters.feed_id"
          class="w-full px-3 py-2 rounded-lg border border-border-subtle bg-bg-primary text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
        >
          <option :value="undefined">{{ strings.feedRuns.filters.allFeeds }}</option>
          <option v-for="feed in feeds" :key="feed.id" :value="feed.id">
            {{ feed.name }}
          </option>
        </select>
      </div>

      <!-- Status filter -->
      <div>
        <label class="block text-xs text-text-secondary mb-1">Status</label>
        <select
          v-model="localFilters.status"
          class="w-full px-3 py-2 rounded-lg border border-border-subtle bg-bg-primary text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
        >
          <option v-for="option in statusOptions" :key="option.value" :value="option.value || undefined">
            {{ option.label }}
          </option>
        </select>
      </div>

      <!-- From date -->
      <div>
        <label class="block text-xs text-text-secondary mb-1">{{ strings.feedRuns.filters.fromDate }}</label>
        <input
          v-model="localFilters.from_date"
          type="datetime-local"
          class="w-full px-3 py-2 rounded-lg border border-border-subtle bg-bg-primary text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
        />
      </div>

      <!-- To date -->
      <div>
        <label class="block text-xs text-text-secondary mb-1">{{ strings.feedRuns.filters.toDate }}</label>
        <input
          v-model="localFilters.to_date"
          type="datetime-local"
          class="w-full px-3 py-2 rounded-lg border border-border-subtle bg-bg-primary text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-accent-primary"
        />
      </div>
    </div>
  </div>
</template>
