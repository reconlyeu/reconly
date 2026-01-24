import { ref, onUnmounted } from 'vue';
import { useQueryClient } from '@tanstack/vue-query';
import { feedRunsApi } from '@/services/api';
import type { FeedRun, FeedRunStatus } from '@/types/entities';

interface PollOptions {
  interval?: number;
  maxPolls?: number;
  onComplete?: (run: FeedRun) => void;
  onError?: (error: unknown) => void;
}

/**
 * Composable for polling feed run status until completion.
 * Automatically cleans up intervals on unmount.
 */
export function useFeedRunPolling() {
  const queryClient = useQueryClient();
  const runningFeeds = ref<Set<number>>(new Set());
  const activePolls = new Map<number, ReturnType<typeof setInterval>>();

  const isTerminalStatus = (status: FeedRunStatus): boolean => {
    return status === 'completed' || status === 'completed_with_errors' || status === 'failed';
  };

  const stopPolling = (feedId: number) => {
    const interval = activePolls.get(feedId);
    if (interval) {
      clearInterval(interval);
      activePolls.delete(feedId);
    }
    runningFeeds.value.delete(feedId);
  };

  const startPolling = (feedId: number, runId: number, options: PollOptions = {}) => {
    const {
      interval = 2000,
      maxPolls = 300, // 10 minutes max
      onComplete,
      onError,
    } = options;

    // Mark feed as running
    runningFeeds.value.add(feedId);

    // Clear any existing poll for this feed
    stopPolling(feedId);

    let pollCount = 0;

    const pollInterval = setInterval(async () => {
      if (pollCount >= maxPolls) {
        stopPolling(feedId);
        return;
      }
      pollCount++;

      try {
        const run = await feedRunsApi.get(runId);

        if (isTerminalStatus(run.status)) {
          stopPolling(feedId);
          // Invalidate queries to refresh data
          queryClient.invalidateQueries({ queryKey: ['feeds'] });
          queryClient.invalidateQueries({ queryKey: ['feed-runs'] });
          queryClient.invalidateQueries({ queryKey: ['digests'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
          queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
          onComplete?.(run);
        }
      } catch (error) {
        stopPolling(feedId);
        onError?.(error);
      }
    }, interval);

    activePolls.set(feedId, pollInterval);
  };

  // Cleanup all polls on unmount
  onUnmounted(() => {
    for (const [feedId] of activePolls) {
      stopPolling(feedId);
    }
  });

  return {
    runningFeeds,
    startPolling,
    stopPolling,
  };
}
