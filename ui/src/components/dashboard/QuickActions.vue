<script setup lang="ts">
/**
 * QuickActions component - horizontal action bar for common workflows
 *
 * Provides quick access to:
 * - Run all feeds
 * - Add new source
 *
 * Positioned at the bottom of the dashboard for easy access.
 * Note: Chat is accessible via the floating "Ask AI" button.
 */
import { computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { Play, Plus, Loader2 } from 'lucide-vue-next';
import { feedsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import { strings } from '@/i18n/en';

const queryClient = useQueryClient();
const toast = useToast();

// Fetch feeds list for "Run All" functionality
const { data: feeds } = useQuery({
  queryKey: ['feeds'],
  queryFn: feedsApi.list,
  staleTime: 30000,
});

// Get enabled feeds only
const enabledFeeds = computed(() => {
  if (!feeds.value) return [];
  return feeds.value.filter((f) => f.schedule_enabled !== false);
});

// Run all feeds mutation
const runAllFeedsMutation = useMutation({
  mutationFn: async () => {
    const feedsToRun = enabledFeeds.value;
    if (feedsToRun.length === 0) {
      throw new Error('No enabled feeds to run');
    }

    const results = await Promise.allSettled(
      feedsToRun.map((feed) => feedsApi.run(feed.id))
    );

    const succeeded = results.filter((r) => r.status === 'fulfilled').length;

    return { succeeded, total: feedsToRun.length };
  },
  onSuccess: ({ succeeded, total }) => {
    if (succeeded === total) {
      toast.success(strings.quickActions.runAllSuccess.replace('{count}', String(total)));
    } else {
      toast.warning(
        strings.quickActions.runAllPartial
          .replace('{succeeded}', String(succeeded))
          .replace('{total}', String(total))
      );
    }
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    queryClient.invalidateQueries({ queryKey: ['feed-runs'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard-insights'] });
  },
  onError: (error: Error) => {
    toast.error(error.message || strings.quickActions.runAllError);
  },
});

function handleRunAllFeeds(): void {
  if (enabledFeeds.value.length === 0) {
    toast.warning(strings.quickActions.noFeedsToRun);
    return;
  }
  runAllFeedsMutation.mutate();
}

const isRunning = computed(() => runAllFeedsMutation.isPending.value);
</script>

<template>
  <div class="flex flex-wrap items-center justify-center gap-3">
    <!-- Run Feeds Button -->
    <button
      @click="handleRunAllFeeds"
      :disabled="isRunning || enabledFeeds.length === 0"
      class="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium shadow-lg transition-all hover:shadow-xl hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-lg"
      :class="[
        isRunning
          ? 'bg-accent-warning text-white shadow-accent-warning/20'
          : 'bg-accent-success text-white shadow-accent-success/20 hover:bg-accent-success/90',
      ]"
    >
      <Loader2 v-if="isRunning" class="h-4 w-4 animate-spin" />
      <Play v-else class="h-4 w-4" />
      {{ isRunning ? strings.quickActions.runningFeeds : strings.quickActions.runFeeds }}
    </button>

    <!-- Add Source Button -->
    <a
      href="/sources?action=create"
      class="inline-flex items-center gap-2 rounded-xl border border-border-default bg-bg-elevated px-4 py-2.5 text-sm font-medium text-text-primary shadow-lg transition-all hover:border-accent-primary hover:bg-bg-hover hover:shadow-xl hover:-translate-y-0.5"
    >
      <Plus class="h-4 w-4" />
      {{ strings.quickActions.addSource }}
    </a>
  </div>
</template>
