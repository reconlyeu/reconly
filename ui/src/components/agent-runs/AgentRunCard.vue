<script setup lang="ts">
/**
 * Agent Run Card component.
 * Displays a summary card for a single agent run.
 * Shows status, iterations, duration, and token usage.
 */
import type { AgentRun, AgentRunStatus } from '@/types/entities';
import {
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
  RotateCw,
  Coins,
  Zap,
  BookOpen,
  Search,
} from 'lucide-vue-next';
import BaseCard from '@/components/common/BaseCard.vue';

interface Props {
  run: AgentRun;
}

const props = defineProps<Props>();

defineEmits<{
  (e: 'click'): void;
}>();

// Format date
const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString();
};

// Format duration
const formatDuration = (seconds: number | null | undefined): string => {
  if (seconds === null || seconds === undefined) return '-';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
};

// Format tokens
const formatTokens = (tokensIn: number, tokensOut: number): string => {
  const total = tokensIn + tokensOut;
  if (total >= 1000000) return `${(total / 1000000).toFixed(1)}M`;
  if (total >= 1000) return `${(total / 1000).toFixed(1)}K`;
  return total.toString();
};

// Get status icon component
const getStatusIcon = (status: AgentRunStatus) => {
  switch (status) {
    case 'pending':
      return Clock;
    case 'running':
      return Loader2;
    case 'completed':
      return CheckCircle;
    case 'failed':
      return AlertCircle;
    default:
      return Clock;
  }
};

// Get status color class
const getStatusClass = (status: AgentRunStatus): string => {
  switch (status) {
    case 'pending':
      return 'text-text-secondary';
    case 'running':
      return 'text-accent-primary animate-spin';
    case 'completed':
      return 'text-status-success';
    case 'failed':
      return 'text-status-failed';
    default:
      return 'text-text-secondary';
  }
};

// Get status badge class
const getStatusBadgeClass = (status: AgentRunStatus): string => {
  switch (status) {
    case 'pending':
      return 'bg-text-secondary/10 text-text-secondary';
    case 'running':
      return 'bg-accent-primary/10 text-accent-primary';
    case 'completed':
      return 'bg-status-success/10 text-status-success';
    case 'failed':
      return 'bg-status-failed/10 text-status-failed';
    default:
      return 'bg-text-secondary/10 text-text-secondary';
  }
};

// Get status label
const getStatusLabel = (status: AgentRunStatus): string => {
  return status.charAt(0).toUpperCase() + status.slice(1);
};

// Get glow color based on status
const getGlowColor = (status: AgentRunStatus): 'primary' | 'success' | 'error' => {
  switch (status) {
    case 'running':
      return 'primary';
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    default:
      return 'primary';
  }
};

// Get strategy icon
const getStrategyIcon = (strategy: string | null | undefined) => {
  switch (strategy) {
    case 'comprehensive':
      return BookOpen;
    case 'deep':
      return Search;
    default:
      return Zap;
  }
};

// Get strategy badge class
const getStrategyBadgeClass = (strategy: string | null | undefined): string => {
  switch (strategy) {
    case 'comprehensive':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'deep':
      return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    default:
      return 'bg-text-muted/10 text-text-muted border-text-muted/20';
  }
};

// Get strategy label
const getStrategyLabel = (strategy: string | null | undefined): string => {
  if (!strategy) return 'Simple';
  return strategy.charAt(0).toUpperCase() + strategy.slice(1);
};
</script>

<template>
  <BaseCard
    clickable
    :glow-color="getGlowColor(run.status)"
    class="cursor-pointer"
    @click="$emit('click')"
  >
    <div class="flex items-center justify-between gap-4">
      <!-- Left: Status and Title -->
      <div class="flex items-center gap-4 min-w-0">
        <!-- Status Icon -->
        <div class="flex-shrink-0">
          <component
            :is="getStatusIcon(run.status)"
            :size="24"
            :class="getStatusClass(run.status)"
          />
        </div>

        <!-- Title and Meta -->
        <div class="min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span
              :class="[
                'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                getStatusBadgeClass(run.status),
              ]"
            >
              {{ getStatusLabel(run.status) }}
            </span>
            <!-- Strategy Badge -->
            <span
              :class="[
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
                getStrategyBadgeClass(run.research_strategy),
              ]"
              :title="`Research strategy: ${getStrategyLabel(run.research_strategy)}`"
            >
              <component :is="getStrategyIcon(run.research_strategy)" :size="10" />
              {{ getStrategyLabel(run.research_strategy) }}
            </span>
            <span class="text-xs text-text-muted">
              {{ formatDate(run.started_at || run.created_at) }}
            </span>
          </div>
          <h4
            v-if="run.result_title"
            class="mt-1 truncate text-sm font-medium text-text-primary"
          >
            {{ run.result_title }}
          </h4>
          <p class="mt-1 text-xs text-text-muted line-clamp-1">
            {{ run.prompt }}
          </p>
        </div>
      </div>

      <!-- Right: Stats -->
      <div class="flex items-center gap-4 flex-shrink-0">
        <!-- Iterations -->
        <div class="text-center">
          <div class="flex items-center gap-1 text-text-muted">
            <RotateCw :size="12" />
            <span class="text-xs">Iterations</span>
          </div>
          <p class="text-sm font-medium text-text-primary">
            {{ run.iterations }}
          </p>
        </div>

        <!-- Duration -->
        <div class="text-center">
          <div class="flex items-center gap-1 text-text-muted">
            <Clock :size="12" />
            <span class="text-xs">Duration</span>
          </div>
          <p class="text-sm font-medium text-text-primary">
            {{ formatDuration(run.duration_seconds) }}
          </p>
        </div>

        <!-- Tokens -->
        <div class="text-center">
          <div class="flex items-center gap-1 text-text-muted">
            <Coins :size="12" />
            <span class="text-xs">Tokens</span>
          </div>
          <p class="text-sm font-medium text-text-primary">
            {{ formatTokens(run.tokens_in, run.tokens_out) }}
          </p>
        </div>

        <!-- Source Count (if available) -->
        <div v-if="run.source_count" class="text-center">
          <div class="flex items-center gap-1 text-text-muted">
            <Search :size="12" />
            <span class="text-xs">Sources</span>
          </div>
          <p class="text-sm font-medium text-text-primary">
            {{ run.source_count }}
          </p>
        </div>

        <!-- Chevron -->
        <ChevronRight :size="16" class="text-text-muted" />
      </div>
    </div>
  </BaseCard>
</template>
