<script setup lang="ts">
import { ChevronRight, Clock, AlertCircle, CheckCircle, Loader2 } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { FeedRun, FeedRunStatus } from '@/types/entities';

defineProps<{
  runs: FeedRun[];
}>();

const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString();
};

const formatDuration = (seconds: number | null | undefined): string => {
  if (seconds === null || seconds === undefined) return '-';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
};

const formatTokens = (tokensIn: number, tokensOut: number): string => {
  const total = tokensIn + tokensOut;
  if (total >= 1000000) return `${(total / 1000000).toFixed(1)}M`;
  if (total >= 1000) return `${(total / 1000).toFixed(1)}K`;
  return total.toString();
};

const getStatusIcon = (status: FeedRunStatus) => {
  switch (status) {
    case 'pending': return Clock;
    case 'running': return Loader2;
    case 'completed': return CheckCircle;
    case 'completed_with_errors': return AlertCircle;
    case 'failed': return AlertCircle;
    default: return Clock;
  }
};

const getStatusClass = (status: FeedRunStatus): string => {
  switch (status) {
    case 'pending': return 'text-text-secondary';
    case 'running': return 'text-accent-primary animate-spin';
    case 'completed': return 'text-status-success';
    case 'completed_with_errors': return 'text-status-error';
    case 'failed': return 'text-status-error';
    default: return 'text-text-secondary';
  }
};

const getStatusBadgeClass = (status: FeedRunStatus): string => {
  switch (status) {
    case 'pending': return 'bg-text-secondary/10 text-text-secondary';
    case 'running': return 'bg-accent-primary/10 text-accent-primary';
    case 'completed': return 'bg-status-success/10 text-status-success';
    case 'completed_with_errors': return 'bg-status-error/10 text-status-error';
    case 'failed': return 'bg-status-error/10 text-status-error';
    default: return 'bg-text-secondary/10 text-text-secondary';
  }
};

const getStatusLabel = (status: FeedRunStatus): string => {
  switch (status) {
    case 'completed_with_errors': return 'Errors';
    default: return strings.status[status] || status;
  }
};

const navigateToDetail = (runId: number) => {
  window.location.href = `/feed-runs/detail?id=${runId}`;
};
</script>

<template>
  <div class="bg-bg-surface rounded-lg border border-border-subtle overflow-hidden">
    <table class="w-full">
      <thead>
        <tr class="border-b border-border-subtle bg-bg-hover/50">
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.feed }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.status }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.sources }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.items }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.tokens }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.duration }}
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
            {{ strings.feedRuns.table.started }}
          </th>
          <th class="px-4 py-3 w-10"></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-subtle">
        <tr
          v-for="run in runs"
          :key="run.id"
          class="hover:bg-bg-hover/50 cursor-pointer transition-colors"
          @click="navigateToDetail(run.id)"
        >
          <td class="px-4 py-3">
            <span class="font-medium text-text-primary">
              {{ run.feed_name || `Feed #${run.feed_id}` }}
            </span>
          </td>
          <td class="px-4 py-3">
            <span :class="['inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium', getStatusBadgeClass(run.status)]">
              <component :is="getStatusIcon(run.status)" :size="12" :class="getStatusClass(run.status)" />
              {{ getStatusLabel(run.status) }}
            </span>
          </td>
          <td class="px-4 py-3 text-sm text-text-secondary">
            <span :class="run.sources_failed > 0 ? 'text-status-error' : ''">
              {{ run.sources_processed }}/{{ run.sources_total }}
            </span>
            <span v-if="run.sources_failed > 0" class="text-status-error text-xs ml-1">
              ({{ run.sources_failed }} failed)
            </span>
          </td>
          <td class="px-4 py-3 text-sm text-text-secondary">
            {{ run.items_processed }}
          </td>
          <td class="px-4 py-3 text-sm text-text-secondary">
            {{ formatTokens(run.total_tokens_in, run.total_tokens_out) }}
          </td>
          <td class="px-4 py-3 text-sm text-text-secondary">
            {{ formatDuration(run.duration_seconds) }}
          </td>
          <td class="px-4 py-3 text-sm text-text-secondary">
            {{ formatDate(run.started_at) }}
          </td>
          <td class="px-4 py-3">
            <ChevronRight :size="16" class="text-text-muted" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
