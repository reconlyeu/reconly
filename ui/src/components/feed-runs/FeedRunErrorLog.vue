<script setup lang="ts">
import { AlertTriangle, AlertCircle, Clock } from 'lucide-vue-next';
import { strings } from '@/i18n/en';
import type { ErrorDetails, ErrorType } from '@/types/entities';

defineProps<{
  errorDetails?: ErrorDetails | null;
  errorLog?: string | null;
}>();

const getErrorTypeLabel = (errorType: ErrorType): string => {
  return strings.feedRuns.errorTypes[errorType] || errorType;
};

const getErrorTypeClass = (errorType: ErrorType): string => {
  switch (errorType) {
    case 'TimeoutError':
      return 'bg-status-error/10 border-status-error/30';
    case 'FetchError':
      return 'bg-status-warning/10 border-status-warning/30';
    case 'ParseError':
      return 'bg-orange-500/10 border-orange-500/30';
    case 'SummarizeError':
      return 'bg-status-error/10 border-status-error/30';
    case 'SaveError':
      return 'bg-red-600/10 border-red-600/30';
    default:
      return 'bg-text-secondary/10 border-text-secondary/30';
  }
};

const getErrorTypeIconClass = (errorType: ErrorType): string => {
  switch (errorType) {
    case 'TimeoutError':
    case 'SummarizeError':
    case 'SaveError':
      return 'text-status-error';
    case 'FetchError':
      return 'text-status-warning';
    case 'ParseError':
      return 'text-orange-500';
    default:
      return 'text-text-secondary';
  }
};

const formatTimestamp = (timestamp: string): string => {
  return new Date(timestamp).toLocaleTimeString();
};
</script>

<template>
  <div class="bg-bg-surface rounded-lg border border-border-subtle p-4">
    <div class="flex items-center gap-2 mb-4">
      <AlertTriangle :size="18" class="text-status-error" />
      <h3 class="font-medium text-text-primary">{{ strings.feedRuns.details.errors }}</h3>
    </div>

    <!-- Structured errors -->
    <div v-if="errorDetails?.errors?.length" class="space-y-3 mb-4">
      <div class="text-sm text-text-secondary mb-2" v-if="errorDetails.summary">
        {{ errorDetails.summary }}
      </div>

      <div
        v-for="(error, index) in errorDetails.errors"
        :key="index"
        :class="['p-3 rounded-lg border', getErrorTypeClass(error.error_type)]"
      >
        <div class="flex items-start justify-between mb-2">
          <div :class="['flex items-center gap-2', getErrorTypeIconClass(error.error_type)]">
            <AlertCircle :size="14" />
            <span class="font-medium text-sm">{{ getErrorTypeLabel(error.error_type) }}</span>
          </div>
          <div class="flex items-center gap-1 text-xs text-text-muted">
            <Clock :size="12" />
            {{ formatTimestamp(error.timestamp) }}
          </div>
        </div>
        <p class="text-sm font-medium text-text-primary mb-1">
          {{ error.source_name || `Source #${error.source_id}` }}
        </p>
        <p class="text-sm text-text-secondary">{{ error.message }}</p>
      </div>
    </div>

    <!-- Legacy error log (fallback) -->
    <div v-else-if="errorLog" class="bg-bg-primary rounded p-3 font-mono text-xs text-text-secondary whitespace-pre-wrap">
      {{ errorLog }}
    </div>

    <div v-else class="text-sm text-text-secondary">
      {{ strings.feedRuns.details.noErrors }}
    </div>
  </div>
</template>
