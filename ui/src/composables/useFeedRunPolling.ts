import { ref, triggerRef } from 'vue';
import { useQueryClient } from '@tanstack/vue-query';
import { feedsApi } from '@/services/api';
import type { FeedRunStatus } from '@/types/entities';

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
  console.log('[useFeedRunPolling] addRunningFeed:', feedId);
  runningFeeds.value.add(feedId);
  triggerRef(runningFeeds);
  console.log('[useFeedRunPolling] runningFeeds after add:', [...runningFeeds.value]);
};

// Helper to remove feedId and trigger reactivity
const removeRunningFeed = (feedId: number) => {
  console.log('[useFeedRunPolling] removeRunningFeed:', feedId);
  runningFeeds.value.delete(feedId);
  triggerRef(runningFeeds);
  console.log('[useFeedRunPolling] runningFeeds after remove:', [...runningFeeds.value]);
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

  const startPolling = (feedId: number, options: PollOptions = {}) => {
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
    console.log('[useFeedRunPolling] startPolling: feedId=', feedId);

    let pollCount = 0;

    const pollInterval = setInterval(async () => {
      if (pollCount >= maxPolls) {
        console.log('[useFeedRunPolling] maxPolls reached, stopping');
        stopPolling(feedId);
        return;
      }
      pollCount++;
      console.log('[useFeedRunPolling] polling... count=', pollCount);

      try {
        // Get the latest run for this feed
        const { items } = await feedsApi.getRuns(feedId, 1, 1);
        const latestRun = items[0];

        if (!latestRun) {
          console.log('[useFeedRunPolling] no runs found yet, continuing...');
          return;
        }

        console.log('[useFeedRunPolling] poll result: status=', latestRun.status);

        if (isTerminalStatus(latestRun.status)) {
          stopPolling(feedId);
          // Invalidate queries to refresh data
          queryClient.invalidateQueries({ queryKey: ['feeds'] });
          queryClient.invalidateQueries({ queryKey: ['feed-runs'] });
          queryClient.invalidateQueries({ queryKey: ['digests'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
          queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
          onComplete?.(latestRun);
        }
      } catch (error) {
        console.error('[useFeedRunPolling] error:', error);
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
