<script setup lang="ts">
import { computed, toRefs } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { digestsApi } from '@/services/api';
import { useDigestsStore } from '@/stores/digests';
import BaseList from '@/components/common/BaseList.vue';
import DigestCard from './DigestCard.vue';
import type { Digest, Exporter } from '@/types/entities';
import { FileText, ArrowRight } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  searchQuery?: string;
  feedFilter?: number | null;
  sourceFilter?: number | null;
  tagFilter?: string | null;
  page?: number;
  pageSize?: number;
}

interface Emits {
  (e: 'view', digest: Digest): void;
  (e: 'export', digest: Digest, exporter: Exporter): void;
  (e: 'delete', digestId: number): void;
  (e: 'page-change', page: number): void;
}

const props = withDefaults(defineProps<Props>(), {
  searchQuery: '',
  feedFilter: null,
  sourceFilter: null,
  tagFilter: null,
  page: 1,
  pageSize: 10,
});

const emit = defineEmits<Emits>();

// Convert props to refs for reactivity in queryKey
const { searchQuery, feedFilter, sourceFilter, tagFilter, page } = toRefs(props);

// Fetch digests with filters - use refs in queryKey for reactivity
const { data, isLoading, isError, error, refetch } = useQuery({
  queryKey: ['digests', searchQuery, feedFilter, sourceFilter, tagFilter, page],
  queryFn: async () => {
    const result = await digestsApi.list(
      {
        search: searchQuery.value || undefined,
        feed_id: feedFilter.value || undefined,
        source_id: sourceFilter.value || undefined,
        tags: tagFilter.value || undefined,
      },
      page.value,
      props.pageSize
    );
    // Access store inside queryFn to ensure Pinia is initialized
    const digestsStore = useDigestsStore();
    digestsStore.setDigests(result.digests || []);
    return result;
  },
  staleTime: 5000, // Reduce stale time for faster updates
});

const digests = computed(() => {
  // Handle the digests response format
  let items: Digest[] = [];
  if (!data.value) return items;
  // API returns { total, digests }
  if (data.value.digests) {
    items = data.value.digests;
  }
  // Fallback: if data is array directly
  else if (Array.isArray(data.value)) {
    items = data.value;
  }
  // Sort by created_at descending (newest first)
  return [...items].sort((a, b) => {
    const aDate = a.created_at ? new Date(a.created_at).getTime() : 0;
    const bDate = b.created_at ? new Date(b.created_at).getTime() : 0;
    return bDate - aDate;
  });
});

const totalPages = computed(() => {
  if (data.value && 'total' in data.value) {
    return Math.ceil(data.value.total / props.pageSize);
  }
  return 1;
});

const hasNextPage = computed(() => props.page < totalPages.value);
const hasPrevPage = computed(() => props.page > 1);

// Check if any filters are applied
const hasFilters = computed(() => {
  return !!(props.searchQuery || props.feedFilter || props.sourceFilter || props.tagFilter);
});

// Empty state content - use onboarding strings when no filters applied
const emptyTitle = computed(() => {
  return hasFilters.value
    ? strings.digests.list.emptyTitle
    : strings.onboarding.emptyStates.digests.title;
});

const emptyMessage = computed(() => {
  return hasFilters.value
    ? strings.digests.list.filterMessage
    : strings.onboarding.emptyStates.digests.message;
});

const emptyTip = computed(() => {
  return hasFilters.value ? undefined : strings.onboarding.emptyStates.digests.tip;
});

const handleView = (digest: Digest) => {
  emit('view', digest);
};

const handleExport = (digest: Digest, exporter: Exporter) => {
  emit('export', digest, exporter);
};

const handleDelete = (digestId: number) => {
  emit('delete', digestId);
};

const nextPage = () => {
  if (hasNextPage.value) {
    emit('page-change', props.page + 1);
  }
};

const prevPage = () => {
  if (hasPrevPage.value) {
    emit('page-change', props.page - 1);
  }
};
</script>

<template>
  <BaseList
    :is-loading="isLoading"
    :is-error="isError"
    :error="error"
    :items="digests"
    entity-name="digest"
    :grid-cols="2"
    :skeleton-count="pageSize"
    skeleton-height="h-80"
    :empty-title="emptyTitle"
    :empty-message="emptyMessage"
    :empty-icon="FileText"
    :empty-tip="emptyTip"
    :show-pagination="totalPages > 1"
    :page="page"
    :total-pages="totalPages"
    :has-next="hasNextPage"
    :has-prev="hasPrevPage"
    @retry="refetch"
    @prev-page="prevPage"
    @next-page="nextPage"
  >
    <template #empty-action>
      <a
        v-if="!hasFilters"
        href="/feeds"
        aria-label="Navigate to feeds page"
        class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-accent-primary-hover focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
      >
        {{ strings.onboarding.emptyStates.digests.cta }}
        <ArrowRight :size="16" :stroke-width="2" />
      </a>
    </template>
    <template #default>
      <DigestCard
        v-for="(digest, index) in digests"
        :key="digest.id"
        :digest="digest"
        :style="{ animationDelay: `${index * 50}ms` }"
        @view="handleView"
        @export="handleExport"
        @delete="handleDelete"
      />
    </template>
  </BaseList>
</template>
