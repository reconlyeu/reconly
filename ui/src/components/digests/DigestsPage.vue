<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useQuery, useMutation, useQueryClient, useIsFetching } from '@tanstack/vue-query';
import { feedsApi, sourcesApi, digestsApi } from '@/services/api';
import { strings } from '@/i18n/en';
import DigestList from './DigestList.vue';
import DigestTable from './DigestTable.vue';
import DigestModal from './DigestModal.vue';
import ViewModeToggle from '@/components/common/ViewModeToggle.vue';
import TagFilterDropdown from '@/components/common/TagFilterDropdown.vue';
import { useViewMode } from '@/composables/useViewMode';
import { useToast } from '@/composables/useToast';
import type { Digest, Exporter } from '@/types/entities';
import { Search, Filter, Loader2 } from 'lucide-vue-next';

// View mode state
const { viewMode, isCardView, isTableView } = useViewMode('digests');

// State
const searchQuery = ref('');
const debouncedSearchQuery = ref('');
const isSearchDebouncing = ref(false);
const feedFilter = ref<number | null>(null);
const sourceFilter = ref<number | null>(null);
const tagFilter = ref<string | null>(null);
const currentPage = ref(1);
const pageSize = 10;
const selectedDigest = ref<Digest | null>(null);
const isModalOpen = ref(false);
const digestTableRef = ref<InstanceType<typeof DigestTable> | null>(null);

// Check for view query param on mount to open specific digest
onMounted(async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const viewId = urlParams.get('view');
  if (viewId) {
    try {
      const digest = await digestsApi.get(parseInt(viewId, 10));
      selectedDigest.value = digest;
      isModalOpen.value = true;
      // Clean up URL without reload
      window.history.replaceState({}, '', '/digests');
    } catch (error) {
      console.error('Failed to load digest:', error);
    }
  }
});

// Debounce search with loading indicator
let searchTimeout: ReturnType<typeof setTimeout>;
watch(searchQuery, (newVal) => {
  clearTimeout(searchTimeout);
  isSearchDebouncing.value = true;
  searchTimeout = setTimeout(() => {
    debouncedSearchQuery.value = newVal;
    isSearchDebouncing.value = false;
    currentPage.value = 1; // Reset to first page on search
  }, 300);
});

// Reset page when filters change
watch([feedFilter, sourceFilter, tagFilter], () => {
  currentPage.value = 1;
});

// Fetch feeds for filter dropdown
const { data: feeds } = useQuery({
  queryKey: ['feeds'],
  queryFn: () => feedsApi.list(),
  staleTime: 60000,
});

// Fetch sources for filter dropdown
const { data: sources } = useQuery({
  queryKey: ['sources'],
  queryFn: () => sourcesApi.list(),
  staleTime: 60000,
});

// Query client for cache invalidation
const queryClient = useQueryClient();

// Fetch digests for table view
const {
  data: digestsData,
  isLoading: isDigestsLoading,
  isFetching: isDigestsFetching,
  isError: isDigestsError,
  error: digestsError,
  refetch: refetchDigests,
} = useQuery({
  queryKey: ['digests', debouncedSearchQuery, feedFilter, sourceFilter, tagFilter, currentPage],
  queryFn: () =>
    digestsApi.list(
      {
        search: debouncedSearchQuery.value || undefined,
        feed_id: feedFilter.value || undefined,
        source_id: sourceFilter.value || undefined,
        tags: tagFilter.value || undefined,
      },
      currentPage.value,
      pageSize
    ),
  staleTime: 30000,
  refetchInterval: 30000,
  enabled: isTableView,
});

const digests = computed(() => {
  if (!digestsData.value) return [];
  if (digestsData.value.digests) return digestsData.value.digests;
  if (Array.isArray(digestsData.value)) return digestsData.value;
  return [];
});

const totalPages = computed(() => {
  if (digestsData.value && 'total' in digestsData.value) {
    return Math.ceil(digestsData.value.total / pageSize);
  }
  return 1;
});

const hasNextPage = computed(() => currentPage.value < totalPages.value);
const hasPrevPage = computed(() => currentPage.value > 1);

// Track any digests query fetching (works for both card and table view)
const digestsFetchingCount = useIsFetching({ queryKey: ['digests'] });

// Search loading state (debouncing or fetching)
const isSearching = computed(() => {
  return isSearchDebouncing.value || digestsFetchingCount.value > 0;
});

// Delete mutation
const deleteMutation = useMutation({
  mutationFn: (digestId: number) => digestsApi.delete(digestId),
  onSuccess: () => {
    // Invalidate digests query to refresh the list
    queryClient.invalidateQueries({ queryKey: ['digests'] });
  },
});

const handleDeleteDigest = (digestId: number) => {
  deleteMutation.mutate(digestId);
};

// Batch delete mutation
const batchDeleteMutation = useMutation({
  mutationFn: (ids: number[]) => digestsApi.batchDelete(ids),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['digests'] });
    digestTableRef.value?.clearSelection();
  },
});

const handleBatchDelete = (ids: number[]) => {
  batchDeleteMutation.mutate(ids);
};

const handleViewDigest = (digest: Digest) => {
  selectedDigest.value = digest;
  isModalOpen.value = true;
};

const handleTagsUpdated = (updatedDigest: Digest) => {
  // Update the selected digest with the new tags
  selectedDigest.value = updatedDigest;
};

// Toast notifications
const toast = useToast();

// Download export mutation for browser downloads
const downloadExportMutation = useMutation({
  mutationFn: async ({ ids, format, filename }: { ids: number[]; format: string; filename: string }) => {
    const blob = await digestsApi.export(ids, format);
    return { blob, filename };
  },
  onSuccess: ({ blob, filename }) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Export downloaded successfully');
    digestTableRef.value?.clearSelection();
  },
  onError: (error: Error) => {
    toast.error(`Export failed: ${error.message}`);
  },
});

const handleExportDigest = (digest: Digest, exporter: Exporter) => {
  const ids = [digest.id];
  const baseFilename = digest.title?.replace(/[^a-z0-9]/gi, '-').toLowerCase() || 'digest';
  const filename = `${baseFilename}.${exporter.file_extension}`;

  // Always use browser download for digest modal/card exports
  // (supports_direct_export is only for automated feed auto-export with configured paths)
  downloadExportMutation.mutate({
    ids,
    format: exporter.name,
    filename,
  });
};

const handleBulkExport = (ids: number[], exporter: Exporter) => {
  const filename = `digests-${new Date().toISOString().split('T')[0]}.${exporter.file_extension}`;

  // Always use browser download for bulk exports from digests page
  // (supports_direct_export is only for automated feed auto-export with configured paths)
  downloadExportMutation.mutate({
    ids,
    format: exporter.name,
    filename,
  });
};

const handlePageChange = (page: number) => {
  currentPage.value = page;
};

const closeModal = () => {
  isModalOpen.value = false;
  selectedDigest.value = null;
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.digests.title }}</h1>
        <p class="mt-1 text-sm text-text-secondary">
          {{ strings.pageSubtitles.digests }}
        </p>
      </div>
      <ViewModeToggle v-model="viewMode" />
    </div>

    <!-- Search and Filters -->
    <div class="mb-6 flex flex-col gap-4 md:flex-row">
      <!-- Search -->
      <div class="relative flex-1">
        <Loader2 v-if="isSearching" class="absolute left-3 top-1/2 -translate-y-1/2 text-accent-primary animate-spin" :size="18" />
        <Search v-else class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
        <input
          v-model="searchQuery"
          type="search"
          :placeholder="strings.digests.search"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        />
      </div>

      <!-- Feed Filter -->
      <div class="relative">
        <Filter class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" :size="18" />
        <select
          v-model="feedFilter"
          class="w-full md:w-48 rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        >
          <option :value="null">{{ strings.digests.filters.allFeeds }}</option>
          <option v-for="feed in feeds" :key="feed.id" :value="feed.id">
            {{ feed.name }}
          </option>
        </select>
      </div>

      <!-- Source Filter -->
      <div class="relative">
        <Filter class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" :size="18" />
        <select
          v-model="sourceFilter"
          class="w-full md:w-48 rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
        >
          <option :value="null">{{ strings.digests.filters.allSources }}</option>
          <option v-for="source in sources" :key="source.id" :value="source.id">
            {{ source.name }}
          </option>
        </select>
      </div>

      <!-- Tag Filter -->
      <TagFilterDropdown v-model="tagFilter" />
    </div>

    <!-- Digest List (Card View) -->
    <div v-if="isCardView">
      <DigestList
        :search-query="debouncedSearchQuery"
        :feed-filter="feedFilter"
        :source-filter="sourceFilter"
        :tag-filter="tagFilter"
        :page="currentPage"
        @view="handleViewDigest"
        @export="handleExportDigest"
        @delete="handleDeleteDigest"
        @page-change="handlePageChange"
      />
    </div>

    <!-- Digest Table (Table View) -->
    <div v-else>
      <DigestTable
        ref="digestTableRef"
        :digests="digests"
        :is-loading="isDigestsLoading"
        :is-error="isDigestsError"
        :error="digestsError"
        @view="handleViewDigest"
        @export="handleExportDigest"
        @export-selected="handleBulkExport"
        @delete="handleDeleteDigest"
        @delete-selected="handleBatchDelete"
        @retry="refetchDigests"
      />
      <!-- Pagination for table view -->
      <div v-if="totalPages > 1" class="mt-4 flex items-center justify-center gap-4">
        <button
          :disabled="!hasPrevPage"
          @click="currentPage--"
          class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <span class="text-sm text-text-secondary">
          Page {{ currentPage }} of {{ totalPages }}
        </span>
        <button
          :disabled="!hasNextPage"
          @click="currentPage++"
          class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Digest Modal -->
    <DigestModal
      :is-open="isModalOpen"
      :digest="selectedDigest"
      @close="closeModal"
      @export="handleExportDigest"
      @tags-updated="handleTagsUpdated"
    />
  </div>
</template>

