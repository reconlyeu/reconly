<script setup lang="ts">
/**
 * SyncStatus component - Shows last sync time and feed health status
 *
 * Displays:
 * - Connection indicator (green pulse dot when connected)
 * - Relative time since last sync
 * - Warning icon if feeds are failing
 * - Detailed tooltip on hover with stats
 */
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { AlertTriangle, Clock } from 'lucide-vue-next';
import { dashboardApi, healthApi } from '@/services/api';
import { strings } from '@/i18n/en';

// Track health check status for connection indicator
const isDisconnected = ref(false);

// Health check query with callbacks to track connection status
useQuery({
  queryKey: ['health'],
  queryFn: async () => {
    const result = await healthApi.check();
    // On success, mark as connected
    isDisconnected.value = false;
    return result;
  },
  refetchInterval: 10000, // Check every 10 seconds
  retry: 1, // Only retry once
  retryDelay: 2000,
  staleTime: 5000,
  // Use gcTime (formerly cacheTime) to keep checking even when component is mounted
  gcTime: 0,
})

// Also set up an error boundary by catching fetch errors
const checkHealth = async () => {
  try {
    await healthApi.check();
    isDisconnected.value = false;
  } catch {
    isDisconnected.value = true;
  }
};

// Check immediately on mount and set up interval
let healthInterval: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  checkHealth();
  healthInterval = setInterval(checkHealth, 10000);
});

onUnmounted(() => {
  if (healthInterval) {
    clearInterval(healthInterval);
  }
});

// Cache last known sync time so it persists when backend goes offline
const cachedLastSync = ref<string | null>(null);
const cachedFeedsHealthy = ref(0);
const cachedFeedsFailing = ref(0);

// Fetch dashboard insights for sync status
const { data: insights, isLoading } = useQuery({
  queryKey: ['dashboard-insights'],
  queryFn: async () => {
    const result = await dashboardApi.getInsights();
    // Cache values when we successfully fetch
    if (result.last_sync_at) {
      cachedLastSync.value = result.last_sync_at;
    }
    cachedFeedsHealthy.value = result.feeds_healthy;
    cachedFeedsFailing.value = result.feeds_failing;
    return result;
  },
  refetchInterval: 30000,
  staleTime: 15000,
});

// Parse timestamp ensuring UTC - append Z if no timezone specified
function parseTimestamp(timestamp: string): Date {
  const isoTimestamp = timestamp.includes('Z') || timestamp.includes('+')
    ? timestamp
    : timestamp + 'Z';
  return new Date(isoTimestamp);
}

// Format relative time (e.g., "5m ago")
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return strings.syncStatus.neverSynced;

  const date = parseTimestamp(timestamp);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (seconds < 10) return strings.syncStatus.justNow;
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// Format exact time for tooltip
function formatExactTime(timestamp: string | null): string {
  if (!timestamp) return strings.syncStatus.neverSynced;
  return parseTimestamp(timestamp).toLocaleString();
}

// Computed values - use cached values as fallback when offline
const lastSyncTimestamp = computed(() =>
  insights.value?.last_sync_at ?? cachedLastSync.value
);

const lastSyncRelative = computed(() =>
  formatRelativeTime(lastSyncTimestamp.value)
);

const lastSyncExact = computed(() =>
  formatExactTime(lastSyncTimestamp.value)
);

const feedsHealthy = computed(() => insights.value?.feeds_healthy ?? cachedFeedsHealthy.value);
const feedsFailing = computed(() => insights.value?.feeds_failing ?? cachedFeedsFailing.value);
const hasFailing = computed(() => feedsFailing.value > 0);

// Build tooltip text with sync time and feed health stats
const tooltipText = computed(() => {
  const lines = [
    `${strings.syncStatus.lastSync}: ${lastSyncExact.value}`,
    `${strings.syncStatus.healthyFeeds}: ${feedsHealthy.value}`,
  ];

  if (hasFailing.value) {
    lines.push(`${strings.syncStatus.failingFeeds}: ${feedsFailing.value}`);
  }

  return lines.join('\n');
});
</script>

<template>
  <div
    class="flex items-center gap-3"
    :title="tooltipText"
  >
    <!-- Connection status indicator -->
    <div
      class="flex items-center gap-1.5 rounded-full px-2 py-1"
      :class="isDisconnected ? 'bg-status-failed/10' : 'bg-accent-success/10'"
    >
      <div
        class="h-2.5 w-2.5 rounded-full"
        :class="isDisconnected ? 'bg-status-failed' : 'bg-accent-success animate-pulse'"
      />
      <span
        class="text-xs font-medium"
        :class="isDisconnected ? 'text-status-failed' : 'text-accent-success'"
      >
        {{ isDisconnected ? 'Offline' : 'Online' }}
      </span>
    </div>

    <!-- Last sync text -->
    <span v-if="isLoading" class="text-sm text-text-muted">
      {{ strings.common.loading }}
    </span>
    <span v-else class="flex items-center gap-1.5 text-sm font-medium text-text-muted">
      <Clock class="h-3.5 w-3.5" />
      {{ strings.syncStatus.lastSync }}: {{ lastSyncRelative }}
    </span>

    <!-- Warning icon for failing feeds -->
    <div
      v-if="hasFailing && !isLoading"
      class="flex items-center gap-1 text-status-warning"
      :title="`${feedsFailing} ${strings.syncStatus.feedsNeedAttention}`"
    >
      <AlertTriangle class="h-4 w-4" />
      <span class="text-xs font-medium">{{ feedsFailing }}</span>
    </div>
  </div>
</template>
