import { ref, triggerRef } from 'vue';
import { useQueryClient } from '@tanstack/vue-query';
import { feedRunsApi } from '@/services/api';
import type { FeedRun, FeedRunStatus } from '@/types/entities';

interface PollOptions {
  interval?: number;
  maxPolls?: number;
  onComplete?: (run: FeedRun) => void;
  onError?: (error: unknown) => void;
}

// Shared state across all component instances
const runningFeeds = ref<Set<number>>(new Set());
const activePolls = new Map<number, ReturnType<typeof setInterval>>();

// Helper to add feedId and trigger reactivity
const addRunningFeed = (feedId: number) => {
  runningFeeds.value.add(feedId);
  triggerRef(runningFeeds);
};

// Helper to remove feedId and trigger reactivity
const removeRunningFeed = (feedId: number) => {
  runningFeeds.value.delete(feedId);
  triggerRef(runningFeeds);
};

/**
 * Composable for polling feed run status until completion.
 * Uses shared state so all components see the same running feeds.
 * Automatically cleans up intervals on unmount.
 */
export function useFeedRunPolling() {
  const queryClient = useQueryClient();

  const isTerminalStatus = (status: FeedRunStatus): boolean => {
    return status === 'completed' || status === 'completed_with_errors' || status === 'failed';
  };

  const stopPolling = (feedId: number) => {
    const interval = activePolls.get(feedId);
    if (interval) {
      clearInterval(interval);
      activePolls.delete(feedId);
    }
    removeRunningFeed(feedId);
  };

  const startPolling = (feedId: number, runId: number, options: PollOptions = {}) => {
    const {
      interval = 2000,
      maxPolls = 300, // 10 minutes max
      onComplete,
      onError,
    } = options;

    // Clear any existing poll for this feed (but don't remove from runningFeeds yet)
    const existingInterval = activePolls.get(feedId);
    if (existingInterval) {
      clearInterval(existingInterval);
      activePolls.delete(feedId);
    }

    // Mark feed as running (with reactivity trigger)
    addRunningFeed(feedId);

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

  // Note: No onUnmounted cleanup since state is shared globally.
  // Polling continues until run completes, regardless of component lifecycle.

  return {
    runningFeeds,
    startPolling,
    stopPolling,
    addRunningFeed,
    removeRunningFeed,
  };
}
