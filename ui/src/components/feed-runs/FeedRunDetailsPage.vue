<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import {
  ArrowLeft,
  Clock,
  AlertCircle,
  CheckCircle,
  Loader2,
  FileText,
  Activity,
  Zap,
} from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import { feedRunsApi } from '@/services/api';
import type { FeedRunStatus } from '@/types/entities';
import FeedRunSourceList from './FeedRunSourceList.vue';
import FeedRunErrorLog from './FeedRunErrorLog.vue';
import FeedRunDigests from './FeedRunDigests.vue';

const props = defineProps<{
  runId?: number;
}>();

// Get run ID from props or query params
const resolvedRunId = ref<number | null>(props.runId ?? null);

onMounted(() => {
  if (!resolvedRunId.value && typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const idParam = params.get('id');
    if (idParam) {
      resolvedRunId.value = parseInt(idParam, 10);
    }
  }
});

const { data: run, isLoading, error } = useQuery({
  queryKey: computed(() => ['feed-run', resolvedRunId.value]),
  queryFn: () => feedRunsApi.get(resolvedRunId.value!),
  enabled: computed(() => resolvedRunId.value !== null),
});

const { data: sourcesData } = useQuery({
  queryKey: computed(() => ['feed-run-sources', resolvedRunId.value]),
  queryFn: () => feedRunsApi.getSources(resolvedRunId.value!),
  enabled: computed(() => !!run.value),
});

const { data: digests } = useQuery({
  queryKey: computed(() => ['feed-run-digests', resolvedRunId.value]),
  queryFn: () => feedRunsApi.getDigests(resolvedRunId.value!),
  enabled: computed(() => !!run.value),
});

const sources = computed(() => sourcesData.value?.sources || []);

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

const formatTokens = (tokens: number): string => {
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(2)}M`;
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return tokens.toString();
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
    case 'pending': return 'text-text-secondary bg-text-secondary/10';
    case 'running': return 'text-accent-primary bg-accent-primary/10';
    case 'completed': return 'text-status-success bg-status-success/10';
    case 'completed_with_errors': return 'text-status-error bg-status-error/10';
    case 'failed': return 'text-status-error bg-status-error/10';
    default: return 'text-text-secondary bg-text-secondary/10';
  }
};

const getStatusLabel = (status: FeedRunStatus): string => {
  switch (status) {
    case 'completed_with_errors': return 'Errors';
    default: return strings.status[status] || status;
  }
};
</script>

<template>
  <div>
    <!-- Back link -->
    <a
      href="/feed-runs"
      class="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary mb-6"
    >
      <ArrowLeft :size="16" />
      {{ strings.feedRuns.backToFeedRuns }}
    </a>

    <!-- No ID provided -->
    <div v-if="!resolvedRunId" class="bg-status-warning/10 text-status-warning p-4 rounded-lg">
      {{ strings.feedRuns.noIdSpecified }}
    </div>

    <!-- Loading state -->
    <div v-else-if="isLoading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-primary"></div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="bg-status-error/10 text-status-error p-4 rounded-lg">
      {{ strings.errors.generic }}
    </div>

    <!-- Content -->
    <template v-else-if="run">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-text-primary">
              {{ run.feed_name || `Feed #${run.feed_id}` }}
            </h1>
            <p class="mt-1 text-sm text-text-secondary">
              Run #{{ run.id }} • Triggered by {{ run.triggered_by }}
            </p>
          </div>
          <span
            :class="[
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
              getStatusClass(run.status),
            ]"
          >
            <component
              :is="getStatusIcon(run.status)"
              :size="16"
              :class="run.status === 'running' ? 'animate-spin' : ''"
            />
            {{ getStatusLabel(run.status) }}
          </span>
        </div>
      </div>

      <!-- Overview Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-6">
        <!-- Timing -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div class="flex items-center gap-2 text-text-secondary mb-2">
            <Clock :size="14" />
            <span class="text-xs">{{ strings.feedRuns.details.duration }}</span>
          </div>
          <p class="text-lg font-semibold text-text-primary">
            {{ formatDuration(run.duration_seconds) }}
          </p>
        </div>

        <!-- Sources -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div class="flex items-center gap-2 text-text-secondary mb-2">
            <Activity :size="14" />
            <span class="text-xs">{{ strings.feedRuns.details.sources }}</span>
          </div>
          <p class="text-lg font-semibold text-text-primary">
            {{ run.sources_processed }}/{{ run.sources_total }}
            <span v-if="run.sources_failed > 0" class="text-sm text-status-error">
              ({{ run.sources_failed }} {{ strings.feedRuns.details.failed }})
            </span>
          </p>
        </div>

        <!-- Items -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div class="flex items-center gap-2 text-text-secondary mb-2">
            <FileText :size="14" />
            <span class="text-xs">{{ strings.feedRuns.details.items }}</span>
          </div>
          <p class="text-lg font-semibold text-text-primary">
            {{ run.items_processed }}
          </p>
        </div>

        <!-- Tokens -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div class="flex items-center gap-2 text-text-secondary mb-2">
            <Zap :size="14" />
            <span class="text-xs">{{ strings.feedRuns.details.tokens }}</span>
          </div>
          <p class="text-lg font-semibold text-text-primary">
            {{ formatTokens(run.total_tokens_in + run.total_tokens_out) }}
          </p>
          <p class="text-xs text-text-muted">
            {{ strings.feedRuns.details.tokensIn }} {{ formatTokens(run.total_tokens_in) }} / {{ strings.feedRuns.details.tokensOut }} {{ formatTokens(run.total_tokens_out) }}
          </p>
        </div>

        <!-- Digests -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <div class="flex items-center gap-2 text-text-secondary mb-2">
            <FileText :size="14" />
            <span class="text-xs">{{ strings.feedRuns.details.digests }}</span>
          </div>
          <p class="text-lg font-semibold text-text-primary">
            {{ run.digests_count || digests?.length || 0 }}
          </p>
        </div>
      </div>

      <!-- Details -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Timing details -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <h3 class="font-medium text-text-primary mb-4">{{ strings.feedRuns.details.timing }}</h3>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.created }}</dt>
              <dd class="text-text-primary">{{ formatDate(run.created_at) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.started }}</dt>
              <dd class="text-text-primary">{{ formatDate(run.started_at) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.completed }}</dt>
              <dd class="text-text-primary">{{ formatDate(run.completed_at) }}</dd>
            </div>
          </dl>
        </div>

        <!-- Run info -->
        <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
          <h3 class="font-medium text-text-primary mb-4">{{ strings.feedRuns.details.runInformation }}</h3>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.triggeredBy }}</dt>
              <dd class="text-text-primary capitalize">{{ run.triggered_by }}</dd>
            </div>
            <div v-if="run.llm_provider" class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.llmProvider }}</dt>
              <dd class="text-text-primary capitalize">{{ run.llm_provider }}</dd>
            </div>
            <div v-if="run.llm_model" class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.llmModel }}</dt>
              <dd class="text-text-primary font-mono text-xs">{{ run.llm_model }}</dd>
            </div>
            <div v-if="run.trace_id" class="flex justify-between">
              <dt class="text-text-secondary">{{ strings.feedRuns.details.traceId }}</dt>
              <dd class="text-text-primary font-mono text-xs">{{ run.trace_id }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- Sources -->
      <FeedRunSourceList :sources="sources" class="mb-6" />

      <!-- Errors -->
      <FeedRunErrorLog
        v-if="run.error_details || run.error_log"
        :errorDetails="run.error_details"
        :errorLog="run.error_log"
        class="mb-6"
      />

      <!-- Digests -->
      <FeedRunDigests :digests="digests || []" />
    </template>
  </div>
</template>
