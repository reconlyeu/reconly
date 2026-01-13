<script setup lang="ts">
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import {
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  FileText,
  Layers,
  ChevronRight,
  AlertTriangle,
  Zap,
} from 'lucide-vue-next';
import { dashboardApi } from '@/services/api';
import { strings } from '@/i18n/en';
import type { FeedRun } from '@/types/entities';

const { data: runs, isLoading } = useQuery({
  queryKey: ['recent-runs'],
  queryFn: () => dashboardApi.getRecentRuns(8),
  refetchInterval: 10000, // Refresh every 10 seconds for live updates
});

const getStatusConfig = (status: string) => {
  const configs = {
    pending: {
      icon: Clock,
      color: 'text-status-pending',
      bgColor: 'bg-status-pending/10',
      label: strings.status.pending,
    },
    running: {
      icon: Loader2,
      color: 'text-status-running',
      bgColor: 'bg-status-running/10',
      label: strings.status.running,
      animate: 'animate-spin',
    },
    completed: {
      icon: CheckCircle2,
      color: 'text-status-success',
      bgColor: 'bg-status-success/10',
      label: strings.status.completed,
    },
    completed_with_errors: {
      icon: XCircle,
      color: 'text-status-error',
      bgColor: 'bg-status-error/10',
      label: 'Errors',
    },
    failed: {
      icon: XCircle,
      color: 'text-status-failed',
      bgColor: 'bg-status-failed/10',
      label: strings.status.failed,
    },
  };
  return configs[status as keyof typeof configs] || configs.pending;
};

const formatDuration = (run: FeedRun) => {
  if (!run.started_at || !run.completed_at) return '-';
  const duration = run.duration_seconds || 0;
  if (duration < 60) return `${Math.round(duration)}s`;
  return `${Math.floor(duration / 60)}m ${Math.round(duration % 60)}s`;
};

const formatTime = (timestamp: string | null) => {
  if (!timestamp) return '-';
  // Ensure UTC parsing - append Z if no timezone specified
  const isoTimestamp = timestamp.includes('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
  const date = new Date(isoTimestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);

  if (seconds < 0) return 'Just now'; // Handle slight clock drift
  if (seconds < 10) return 'Just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
};

const formatExactTime = (timestamp: string | null) => {
  if (!timestamp) return '';
  const isoTimestamp = timestamp.includes('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z';
  const date = new Date(isoTimestamp);
  return date.toLocaleString();
};
</script>

<template>
  <div class="space-y-3">
    <!-- Loading skeleton -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-24 animate-pulse rounded-xl bg-bg-elevated"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!runs || runs.length === 0"
      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-bg-surface/50 py-12"
    >
      <Clock class="mb-3 h-12 w-12 text-text-muted opacity-50" />
      <p class="text-sm text-text-muted">{{ strings.dashboard.noRuns }}</p>
    </div>

    <!-- Feed runs -->
    <a
      v-else
      v-for="(run, index) in runs"
      :key="run.id"
      :href="`/feed-runs/detail?id=${run.id}`"
      class="group animate-slide-in-right-fast relative block overflow-hidden rounded-xl border border-border-subtle bg-gradient-to-br from-bg-elevated/80 to-bg-elevated/50 p-4 transition-all duration-300 hover:border-border-default hover:shadow-lg hover:shadow-black/10 cursor-pointer"
      :style="{ animationDelay: `${index * 100}ms` }"
    >
      <!-- Glow effect for running feeds -->
      <div
        v-if="run.status === 'running'"
        class="absolute inset-0 bg-gradient-to-r from-status-running/5 to-transparent opacity-0 animate-pulse"
      />

      <div class="relative z-10 flex items-center justify-between">
        <!-- Left: Status and info -->
        <div class="flex items-center gap-4">
          <!-- Status indicator with icon -->
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl"
            :class="getStatusConfig(run.status).bgColor"
          >
            <component
              :is="getStatusConfig(run.status).icon"
              class="h-6 w-6"
              :class="[
                getStatusConfig(run.status).color,
                getStatusConfig(run.status).animate,
              ]"
            />
          </div>

          <!-- Feed info -->
          <div class="min-w-0">
            <div class="mb-1 flex items-center gap-2">
              <h4 class="truncate font-semibold text-text-primary">
                {{ run.feed_name || `Feed #${run.feed_id}` }}
              </h4>
              <span
                class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                :class="getStatusConfig(run.status).bgColor + ' ' + getStatusConfig(run.status).color"
              >
                {{ getStatusConfig(run.status).label }}
              </span>
            </div>
            <div class="flex items-center gap-3 text-sm text-text-muted">
              <span class="flex items-center gap-1" :title="formatExactTime(run.started_at)">
                <Clock class="h-3.5 w-3.5" />
                {{ formatTime(run.started_at) }}
              </span>
              <span v-if="run.status === 'completed' || run.status === 'completed_with_errors'" class="flex items-center gap-1">
                <Zap class="h-3.5 w-3.5" />
                {{ formatDuration(run) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Right: Fixed metrics layout -->
        <div class="flex items-center gap-4">
          <!-- Items column -->
          <div class="text-right min-w-[60px]">
            <div class="flex items-center justify-end gap-1 text-sm font-medium text-text-primary">
              <FileText class="h-4 w-4" />
              {{ run.items_processed }}
            </div>
            <div class="text-xs text-text-muted">items</div>
          </div>

          <!-- Sources column -->
          <div class="text-right min-w-[80px]">
            <!-- All succeeded -->
            <template v-if="run.sources_failed === 0 && run.status !== 'pending' && run.status !== 'running'">
              <div class="flex items-center justify-end gap-1 text-sm font-medium text-status-success">
                <CheckCircle2 class="h-4 w-4" />
                {{ run.sources_processed }}/{{ run.sources_total }}
              </div>
              <div class="text-xs text-text-muted">sources</div>
            </template>
            <!-- Some or all failed -->
            <template v-else-if="run.sources_failed > 0">
              <div class="flex items-center justify-end gap-1 text-sm font-medium text-status-error">
                <AlertTriangle class="h-4 w-4" />
                {{ run.sources_processed }}/{{ run.sources_total }}
              </div>
              <div class="text-xs text-status-error">{{ run.sources_failed }} failed</div>
            </template>
            <!-- Running or pending -->
            <template v-else>
              <div class="flex items-center justify-end gap-1 text-sm font-medium text-text-secondary">
                <Layers class="h-4 w-4" />
                {{ run.sources_processed }}/{{ run.sources_total }}
              </div>
              <div class="text-xs text-text-muted">sources</div>
            </template>
          </div>

          <!-- View details arrow -->
          <ChevronRight
            class="h-5 w-5 text-text-muted opacity-0 transition-all duration-300 group-hover:translate-x-1 group-hover:opacity-100"
          />
        </div>
      </div>

      <!-- Progress bar for running feeds -->
      <div
        v-if="run.status === 'running'"
        class="mt-3 h-1 overflow-hidden rounded-full bg-bg-surface"
      >
        <div
          class="h-full bg-gradient-to-r from-status-running to-accent-primary animate-pulse"
          :style="{
            width: run.sources_total
              ? `${(run.sources_processed / run.sources_total) * 100}%`
              : '50%',
          }"
        />
      </div>
    </a>
  </div>
</template>

