<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { strings } from '@/i18n/en';
import { feedsApi } from '@/services/api';
import { useFeedsStore } from '@/stores/feeds';
import FeedList from './FeedList.vue';
import FeedTable from './FeedTable.vue';
import FeedForm from './FeedForm.vue';
import ViewModeToggle from '@/components/common/ViewModeToggle.vue';
import { useViewMode } from '@/composables/useViewMode';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';
import { useFeedRunPolling } from '@/composables/useFeedRunPolling';
import type { Feed } from '@/types/entities';
import { Plus } from 'lucide-vue-next';

// View mode state
const { viewMode, isCardView, isTableView } = useViewMode('feeds');

const queryClient = useQueryClient();
const toast = useToast();
const { confirmDelete } = useConfirm();

const isModalOpen = ref(false);
const editingFeed = ref<Feed | null>(null);
const feedTableRef = ref<InstanceType<typeof FeedTable> | null>(null);

// Use shared polling composable for tracking feed run status
const { runningFeeds, startPolling } = useFeedRunPolling();

// Handle ?edit= query param to open edit modal on page load
onMounted(async () => {
  const params = new URLSearchParams(window.location.search);
  const editId = params.get('edit');
  if (editId) {
    // Clean up URL immediately
    window.history.replaceState({}, '', window.location.pathname);

    // Fetch the feed directly and open edit modal
    try {
      const feedId = parseInt(editId, 10);
      const feed = await feedsApi.get(feedId);
      if (feed) {
        editingFeed.value = feed;
        isModalOpen.value = true;
      }
    } catch (error) {
      toast.error('Feed not found');
    }
  }
});

// Fetch feeds for table view
const {
  data: feedsData,
  isLoading: isFeedsLoading,
  isError: isFeedsError,
  error: feedsError,
  refetch: refetchFeeds,
} = useQuery({
  queryKey: ['feeds'],
  queryFn: async () => {
    const result = await feedsApi.list();
    // Access store inside queryFn to ensure Pinia is initialized
    const feedsStore = useFeedsStore();
    feedsStore.setFeeds(result);
    return result;
  },
  staleTime: 30000,
  refetchInterval: 30000,
  enabled: isTableView,
});

const feeds = computed(() => feedsData.value || []);

// Run feed mutation
const runFeedMutation = useMutation({
  mutationFn: async (feedId: number) => {
    runningFeeds.value.add(feedId);
    return await feedsApi.run(feedId);
  },
  onSuccess: (data, feedId) => {
    const feed = feeds.value?.find(f => f.id === feedId);
    const feedName = feed?.name || 'Feed';
    toast.success(`${feedName} started successfully`);
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    queryClient.invalidateQueries({ queryKey: ['feed-runs'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
    // Start polling for completion
    startPolling(feedId, data.id);
  },
  onError: (error: any, feedId) => {
    const feed = feeds.value?.find(f => f.id === feedId);
    const feedName = feed?.name || 'Feed';
    toast.error(`Failed to run ${feedName}: ${error.detail || error.message || 'Unknown error'}`);
    runningFeeds.value.delete(feedId);
  },
});

// Toggle feed mutation
const toggleFeedMutation = useMutation({
  mutationFn: async ({ feedId, enabled }: { feedId: number; enabled: boolean }) => {
    return await feedsApi.update(feedId, { schedule_enabled: enabled });
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to toggle feed');
  },
});

// Delete feed mutation
const deleteFeedMutation = useMutation({
  mutationFn: async (feedId: number) => {
    return await feedsApi.delete(feedId);
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    toast.success('Feed deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete feed');
  },
});

// Batch delete mutation
const batchDeleteMutation = useMutation({
  mutationFn: (ids: number[]) => feedsApi.batchDelete(ids),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    feedTableRef.value?.clearSelection();
    toast.success('Feeds deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete feeds');
  },
});

const handleRun = (feedId: number) => {
  runFeedMutation.mutate(feedId);
};

const handleToggle = (feedId: number, enabled: boolean) => {
  toggleFeedMutation.mutate({ feedId, enabled });
};

const handleDelete = (feedId: number) => {
  const feed = feeds.value?.find(f => f.id === feedId);
  const feedName = feed?.name || 'this feed';
  if (confirmDelete(feedName, 'feed')) {
    deleteFeedMutation.mutate(feedId);
  }
};

const handleBatchDelete = (ids: number[]) => {
  batchDeleteMutation.mutate(ids);
};

const openCreateModal = () => {
  editingFeed.value = null;
  isModalOpen.value = true;
};

const openEditModal = (feed: Feed) => {
  editingFeed.value = feed;
  isModalOpen.value = true;
};

const closeModal = () => {
  isModalOpen.value = false;
  editingFeed.value = null;
};

const handleSuccess = () => {
  const message = editingFeed.value
    ? 'Feed updated successfully'
    : 'Feed created successfully';
  toast.success(message);
  closeModal();
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.feeds.title }}</h1>
        <p class="mt-1 text-sm text-text-secondary">
          Configure feeds to orchestrate sources with schedules and outputs
        </p>
      </div>
      <div class="flex items-center gap-3">
        <ViewModeToggle v-model="viewMode" />
        <button
          @click="openCreateModal"
          class="group flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 font-medium text-white transition-all hover:bg-accent-primary-hover hover:shadow-lg hover:shadow-accent-primary/20"
        >
          <Plus :size="18" class="transition-transform group-hover:rotate-90" />
          {{ strings.feeds.createFeed }}
        </button>
      </div>
    </div>

    <!-- Feed List (Card View) -->
    <div v-if="isCardView">
      <FeedList @edit="openEditModal" />
    </div>

    <!-- Feed Table (Table View) -->
    <div v-else>
      <FeedTable
        ref="feedTableRef"
        :feeds="feeds"
        :is-loading="isFeedsLoading"
        :is-error="isFeedsError"
        :error="feedsError"
        :running-feeds="runningFeeds"
        @run="handleRun"
        @toggle="handleToggle"
        @edit="openEditModal"
        @delete="handleDelete"
        @delete-selected="handleBatchDelete"
        @retry="refetchFeeds"
      />
    </div>

    <!-- Create/Edit Modal -->
    <FeedForm
      :key="editingFeed?.id ?? 'create'"
      :is-open="isModalOpen"
      :feed="editingFeed"
      @close="closeModal"
      @success="handleSuccess"
    />
  </div>
</template>

