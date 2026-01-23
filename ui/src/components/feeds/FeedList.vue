<script setup lang="ts">
import { ref, computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { feedsApi, bundlesApi } from '@/services/api';
import { useFeedsStore } from '@/stores/feeds';
import BaseList from '@/components/common/BaseList.vue';
import FeedCard from './FeedCard.vue';
import ImportBundleModal from './ImportBundleModal.vue';
import type { Feed } from '@/types/entities';
import { Layers, Upload } from 'lucide-vue-next';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';
import { strings } from '@/i18n/en';

interface Emits {
  (e: 'edit', feed: Feed): void;
}

const emit = defineEmits<Emits>();
const queryClient = useQueryClient();
const toast = useToast();
const { confirmDelete } = useConfirm();

const runningFeeds = ref<Set<number>>(new Set());
const showImportModal = ref(false);

// Fetch feeds
const { data: feeds, isLoading, isError, error, refetch } = useQuery({
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
});

// Run feed mutation
const runFeedMutation = useMutation({
  mutationFn: async (feedId: number) => {
    runningFeeds.value.add(feedId);
    return await feedsApi.run(feedId);
  },
  onSuccess: (_data, feedId) => {
    const feed = feeds.value?.find(f => f.id === feedId);
    const feedName = feed?.name || 'Feed';
    toast.success(`${feedName} started successfully`);
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    queryClient.invalidateQueries({ queryKey: ['feed-runs'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
  },
  onError: (error: any, feedId) => {
    const feed = feeds.value?.find(f => f.id === feedId);
    const feedName = feed?.name || 'Feed';
    toast.error(`Failed to run ${feedName}: ${error.detail || error.message || 'Unknown error'}`);
  },
  onSettled: (_data, _error, feedId) => {
    // Keep running state for a bit to show feedback
    setTimeout(() => {
      runningFeeds.value.delete(feedId);
    }, 2000);
  },
});

// Toggle feed enabled status mutation
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

const feedsList = computed(() => {
  if (!feeds.value) return [];
  return [...feeds.value].sort((a, b) => {
    // Sort by last_run_at descending (newest first), nulls last
    const aDate = a.last_run_at ? new Date(a.last_run_at).getTime() : 0;
    const bDate = b.last_run_at ? new Date(b.last_run_at).getTime() : 0;
    return bDate - aDate;
  });
});

const handleRun = (feedId: number) => {
  runFeedMutation.mutate(feedId);
};

const handleToggle = (feedId: number, enabled: boolean) => {
  toggleFeedMutation.mutate({ feedId, enabled });
};

const handleEdit = (feed: Feed) => {
  emit('edit', feed);
};

const handleDelete = (feedId: number) => {
  const feed = feeds.value?.find(f => f.id === feedId);
  const feedName = feed?.name || 'this feed';

  if (confirmDelete(feedName, 'feed')) {
    deleteFeedMutation.mutate(feedId);
  }
};

const isRunning = (feedId: number) => {
  return runningFeeds.value.has(feedId);
};

// Export feed as bundle
const handleExport = async (feedId: number) => {
  const feed = feeds.value?.find(f => f.id === feedId);
  const feedName = feed?.name || 'Feed';

  try {
    await bundlesApi.downloadBundle(feedId);
    toast.success(`${feedName} exported successfully`);
  } catch (error: any) {
    toast.error(`Failed to export ${feedName}: ${error.detail || error.message || 'Unknown error'}`);
  }
};

// Handle successful import
const handleImportSuccess = () => {
  showImportModal.value = false;
  queryClient.invalidateQueries({ queryKey: ['feeds'] });
  queryClient.invalidateQueries({ queryKey: ['sources'] });
  queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
  queryClient.invalidateQueries({ queryKey: ['report-templates'] });
};
</script>

<template>
  <div>
    <!-- Import Button (placed above the list) -->
    <div class="mb-4 flex justify-end">
      <button
        @click="showImportModal = true"
        class="inline-flex items-center gap-2 rounded-lg bg-accent-primary/10 px-4 py-2 text-sm font-medium text-accent-primary transition-all hover:bg-accent-primary hover:text-white focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
      >
        <Upload :size="18" :stroke-width="2" />
        {{ strings.feeds.importBundle }}
      </button>
    </div>

    <BaseList
      :is-loading="isLoading"
      :is-error="isError"
      :error="error"
      :items="feedsList"
      entity-name="feed"
      :grid-cols="3"
      :skeleton-count="4"
      skeleton-height="h-80"
      :empty-title="strings.feeds.empty.title"
      :empty-message="strings.feeds.empty.message"
      :empty-icon="Layers"
      @retry="refetch"
    >
      <template #default>
        <FeedCard
          v-for="(feed, index) in feedsList"
          :key="feed.id"
          :feed="feed"
          :is-running="isRunning(feed.id)"
          :style="{ animationDelay: `${index * 50}ms` }"
          @run="handleRun"
          @toggle="handleToggle"
          @edit="handleEdit"
          @delete="handleDelete"
          @export="handleExport"
        />
      </template>
    </BaseList>

    <!-- Import Modal -->
    <ImportBundleModal
      :show="showImportModal"
      @close="showImportModal = false"
      @success="handleImportSuccess"
    />
  </div>
</template>
