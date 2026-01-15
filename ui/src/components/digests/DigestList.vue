<script setup lang="ts">
import { computed, toRefs } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { digestsApi } from '@/services/api';
import { useDigestsStore } from '@/stores/digests';
import BaseList from '@/components/common/BaseList.vue';
import DigestCard from './DigestCard.vue';
import type { Digest, Exporter } from '@/types/entities';
import { FileText } from 'lucide-vue-next';

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

const emptyMessage = computed(() => {
  if (props.searchQuery || props.feedFilter || props.sourceFilter || props.tagFilter) {
    return 'Try adjusting your filters or search query';
  }
  return 'Digests will appear here once feeds start running';
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
    empty-title="No digests found"
    :empty-message="emptyMessage"
    :empty-icon="FileText"
    :show-pagination="totalPages > 1"
    :page="page"
    :total-pages="totalPages"
    :has-next="hasNextPage"
    :has-prev="hasPrevPage"
    @retry="refetch"
    @prev-page="prevPage"
    @next-page="nextPage"
  >
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
