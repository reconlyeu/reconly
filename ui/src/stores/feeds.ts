/**
 * Pinia store for Feeds
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Feed, FeedRun } from '@/types/entities';

export const useFeedsStore = defineStore('feeds', () => {
  // State
  const feeds = ref<Feed[]>([]);
  const recentRuns = ref<FeedRun[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  // Getters
  const feedsCount = computed(() => feeds.value.length);

  const enabledFeeds = computed(() => {
    return feeds.value.filter((f) => f.schedule_enabled);
  });

  const feedById = computed(() => {
    return (id: number) => feeds.value.find((f) => f.id === id);
  });

  const runningFeeds = computed(() => {
    return recentRuns.value.filter((r) => r.status === 'running');
  });

  // Actions
  const setFeeds = (newFeeds: Feed[]) => {
    feeds.value = newFeeds;
  };

  const addFeed = (feed: Feed) => {
    feeds.value.push(feed);
  };

  const updateFeed = (id: number, updates: Partial<Feed>) => {
    const index = feeds.value.findIndex((f) => f.id === id);
    if (index !== -1) {
      feeds.value[index] = { ...feeds.value[index], ...updates };
    }
  };

  const removeFeed = (id: number) => {
    feeds.value = feeds.value.filter((f) => f.id !== id);
  };

  const setRecentRuns = (runs: FeedRun[]) => {
    recentRuns.value = runs;
  };

  const addRun = (run: FeedRun) => {
    recentRuns.value.unshift(run);
    // Keep only the most recent runs
    if (recentRuns.value.length > 20) {
      recentRuns.value.pop();
    }
  };

  const updateRun = (id: number, updates: Partial<FeedRun>) => {
    const index = recentRuns.value.findIndex((r) => r.id === id);
    if (index !== -1) {
      recentRuns.value[index] = { ...recentRuns.value[index], ...updates };
    }
  };

  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  const setError = (value: string | null) => {
    error.value = value;
  };

  return {
    // State
    feeds,
    recentRuns,
    loading,
    error,
    // Getters
    feedsCount,
    enabledFeeds,
    feedById,
    runningFeeds,
    // Actions
    setFeeds,
    addFeed,
    updateFeed,
    removeFeed,
    setRecentRuns,
    addRun,
    updateRun,
    setLoading,
    setError,
  };
});
