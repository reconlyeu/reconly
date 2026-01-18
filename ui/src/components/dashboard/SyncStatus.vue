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
import { ref, computed, watch } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { AlertTriangle, Clock } from 'lucide-vue-next';
import { dashboardApi, healthApi } from '@/services/api';
import { strings } from '@/i18n/en';

// Track health check status for connection indicator
const failureCount = ref(0);
const isDisconnected = ref(false);

const { isError: healthError, isSuccess: healthSuccess } = useQuery({
  queryKey: ['health'],
  queryFn: healthApi.check,
  refetchInterval: 15000,
  retry: 2,
  retryDelay: 1000,
  staleTime: 10000,
});

// Track connection status based on health check results
watch([healthError, healthSuccess], ([error, success]) => {
  if (success) {
    failureCount.value = 0;
    isDisconnected.value = false;
  } else if (error) {
    failureCount.value++;
    // Only show disconnected after 2 consecutive failures
    if (failureCount.value >= 2) {
      isDisconnected.value = true;
    }
  }
});

// Fetch dashboard insights for sync status
const { data: insights, isLoading } = useQuery({
  queryKey: ['dashboard-insights'],
  queryFn: dashboardApi.getInsights,
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

// Computed values
const lastSyncRelative = computed(() =>
  formatRelativeTime(insights.value?.last_sync_at ?? null)
);

const lastSyncExact = computed(() =>
  formatExactTime(insights.value?.last_sync_at ?? null)
);

const feedsHealthy = computed(() => insights.value?.feeds_healthy ?? 0);
const feedsFailing = computed(() => insights.value?.feeds_failing ?? 0);
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
    class="flex items-center gap-2"
    :title="tooltipText"
  >
    <!-- Connection status dot -->
    <div
      class="h-2 w-2 rounded-full"
      :class="isDisconnected ? 'bg-status-failed' : 'bg-accent-success animate-pulse'"
    />

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
