<script setup lang="ts">
/**
 * Agent Run Modal component.
 * Shows full details of an agent run including:
 * - Run metadata (status, duration, tokens)
 * - Research prompt
 * - Tool calls with expandable details
 * - Sources consulted
 * - Result content
 * - Error log (if failed)
 */
import { ref, computed } from 'vue';
import type { AgentRun, AgentToolCall, AgentRunStatus } from '@/types/entities';
import {
  X,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Wrench,
  Globe,
  FileText,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  RotateCw,
  Coins,
  Hash,
} from 'lucide-vue-next';

interface Props {
  isOpen: boolean;
  run: AgentRun | null;
}

const props = defineProps<Props>();

defineEmits<{
  (e: 'close'): void;
}>();

// Track expanded tool calls
const expandedToolCalls = ref<Set<number>>(new Set());

// Track copied state
const copiedTraceId = ref(false);

// Toggle tool call expansion
const toggleToolCall = (index: number) => {
  if (expandedToolCalls.value.has(index)) {
    expandedToolCalls.value.delete(index);
  } else {
    expandedToolCalls.value.add(index);
  }
};

// Copy trace ID to clipboard
const copyTraceId = async () => {
  if (props.run?.trace_id) {
    await navigator.clipboard.writeText(props.run.trace_id);
    copiedTraceId.value = true;
    setTimeout(() => {
      copiedTraceId.value = false;
    }, 2000);
  }
};

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
const formatTokens = (count: number): string => {
  if (count >= 1000000) return `${(count / 1000000).toFixed(2)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toLocaleString();
};

// Format cost
const formatCost = (cost: number): string => {
  return `$${cost.toFixed(4)}`;
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
      return 'bg-text-secondary/10 text-text-secondary border-text-secondary/20';
    case 'running':
      return 'bg-accent-primary/10 text-accent-primary border-accent-primary/20';
    case 'completed':
      return 'bg-status-success/10 text-status-success border-status-success/20';
    case 'failed':
      return 'bg-status-failed/10 text-status-failed border-status-failed/20';
    default:
      return 'bg-text-secondary/10 text-text-secondary border-text-secondary/20';
  }
};

// Get status label
const getStatusLabel = (status: AgentRunStatus): string => {
  return status.charAt(0).toUpperCase() + status.slice(1);
};

// Get tool icon based on tool name
const getToolIcon = (toolName: string) => {
  if (toolName.toLowerCase().includes('search')) return Globe;
  if (toolName.toLowerCase().includes('fetch')) return Globe;
  return Wrench;
};
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen && run"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="$emit('close')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" />

        <!-- Modal -->
        <div
          class="relative w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface shadow-2xl shadow-black/50 flex flex-col"
        >
          <!-- Decorative gradient orb -->
          <div class="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-accent-primary/20 blur-3xl" />

          <!-- Header -->
          <div class="relative flex items-center justify-between border-b border-border-subtle p-6">
            <div class="flex items-center gap-4">
              <component
                :is="getStatusIcon(run.status)"
                :size="28"
                :class="getStatusClass(run.status)"
              />
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-xl font-bold text-text-primary">
                    Agent Run Details
                  </h2>
                  <span
                    :class="[
                      'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
                      getStatusBadgeClass(run.status),
                    ]"
                  >
                    {{ getStatusLabel(run.status) }}
                  </span>
                </div>
                <p class="mt-1 text-sm text-text-muted">
                  {{ run.source_name || `Source #${run.source_id}` }}
                </p>
              </div>
            </div>
            <button
              @click="$emit('close')"
              class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              <X :size="20" />
            </button>
          </div>

          <!-- Content (scrollable) -->
          <div class="relative flex-1 overflow-y-auto p-6 space-y-6">
            <!-- Stats Grid -->
            <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <!-- Duration -->
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <div class="flex items-center gap-2 text-text-muted">
                  <Clock :size="14" />
                  <span class="text-xs">Duration</span>
                </div>
                <p class="mt-1 text-lg font-semibold text-text-primary">
                  {{ formatDuration(run.duration_seconds) }}
                </p>
              </div>

              <!-- Iterations -->
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <div class="flex items-center gap-2 text-text-muted">
                  <RotateCw :size="14" />
                  <span class="text-xs">Iterations</span>
                </div>
                <p class="mt-1 text-lg font-semibold text-text-primary">
                  {{ run.iterations }}
                </p>
              </div>

              <!-- Tokens -->
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <div class="flex items-center gap-2 text-text-muted">
                  <Coins :size="14" />
                  <span class="text-xs">Tokens</span>
                </div>
                <p class="mt-1 text-lg font-semibold text-text-primary">
                  {{ formatTokens(run.tokens_in + run.tokens_out) }}
                </p>
                <p class="text-xs text-text-muted">
                  {{ formatTokens(run.tokens_in) }} in / {{ formatTokens(run.tokens_out) }} out
                </p>
              </div>

              <!-- Cost -->
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <div class="flex items-center gap-2 text-text-muted">
                  <Coins :size="14" />
                  <span class="text-xs">Est. Cost</span>
                </div>
                <p class="mt-1 text-lg font-semibold text-text-primary">
                  {{ formatCost(run.estimated_cost) }}
                </p>
              </div>
            </div>

            <!-- Trace ID -->
            <div v-if="run.trace_id" class="flex items-center gap-2">
              <Hash :size="14" class="text-text-muted" />
              <span class="text-xs text-text-muted">Trace ID:</span>
              <code class="rounded bg-bg-hover px-2 py-0.5 text-xs text-text-secondary font-mono">
                {{ run.trace_id }}
              </code>
              <button
                @click="copyTraceId"
                class="rounded p-1 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
              >
                <Check v-if="copiedTraceId" :size="14" class="text-status-success" />
                <Copy v-else :size="14" />
              </button>
            </div>

            <!-- Research Prompt -->
            <div>
              <h3 class="mb-2 text-sm font-medium text-text-primary">Research Prompt</h3>
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <p class="text-sm text-text-secondary whitespace-pre-wrap">{{ run.prompt }}</p>
              </div>
            </div>

            <!-- Tool Calls -->
            <div v-if="run.tool_calls && run.tool_calls.length > 0">
              <h3 class="mb-2 text-sm font-medium text-text-primary">
                Tool Calls ({{ run.tool_calls.length }})
              </h3>
              <div class="space-y-2">
                <div
                  v-for="(call, index) in run.tool_calls"
                  :key="index"
                  class="rounded-lg border border-border-subtle bg-bg-surface overflow-hidden"
                >
                  <!-- Tool Call Header -->
                  <button
                    @click="toggleToolCall(index)"
                    class="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-bg-hover"
                  >
                    <div class="flex items-center gap-2">
                      <component :is="getToolIcon(call.tool)" :size="16" class="text-accent-primary" />
                      <span class="font-medium text-text-primary">{{ call.tool }}</span>
                    </div>
                    <component
                      :is="expandedToolCalls.has(index) ? ChevronDown : ChevronRight"
                      :size="16"
                      class="text-text-muted"
                    />
                  </button>

                  <!-- Tool Call Details (expandable) -->
                  <Transition name="slide">
                    <div v-if="expandedToolCalls.has(index)" class="border-t border-border-subtle p-3 space-y-3">
                      <!-- Input -->
                      <div>
                        <span class="text-xs font-medium text-text-muted">Input:</span>
                        <pre class="mt-1 rounded bg-bg-hover p-2 text-xs text-text-secondary overflow-x-auto">{{ JSON.stringify(call.input, null, 2) }}</pre>
                      </div>
                      <!-- Output -->
                      <div>
                        <span class="text-xs font-medium text-text-muted">Output:</span>
                        <pre class="mt-1 rounded bg-bg-hover p-2 text-xs text-text-secondary overflow-x-auto max-h-48 overflow-y-auto">{{ call.output }}</pre>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>

            <!-- Sources Consulted -->
            <div v-if="run.sources_consulted && run.sources_consulted.length > 0">
              <h3 class="mb-2 text-sm font-medium text-text-primary">
                Sources Consulted ({{ run.sources_consulted.length }})
              </h3>
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <ul class="space-y-1">
                  <li
                    v-for="(source, index) in run.sources_consulted"
                    :key="index"
                    class="flex items-center gap-2 text-sm"
                  >
                    <Globe :size="12" class="text-text-muted flex-shrink-0" />
                    <a
                      :href="source"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-accent-primary hover:underline truncate"
                    >
                      {{ source }}
                    </a>
                  </li>
                </ul>
              </div>
            </div>

            <!-- Result -->
            <div v-if="run.result_title || run.result_content">
              <h3 class="mb-2 text-sm font-medium text-text-primary">Result</h3>
              <div class="rounded-lg border border-border-subtle bg-bg-surface p-4">
                <h4 v-if="run.result_title" class="font-medium text-text-primary mb-2">
                  {{ run.result_title }}
                </h4>
                <div
                  v-if="run.result_content"
                  class="prose prose-sm prose-invert max-w-none text-text-secondary"
                  v-html="run.result_content"
                />
              </div>
            </div>

            <!-- Error Log -->
            <div v-if="run.error_log">
              <h3 class="mb-2 text-sm font-medium text-status-failed">Error Log</h3>
              <div class="rounded-lg border border-status-failed/30 bg-status-failed/10 p-4">
                <pre class="text-sm text-status-failed whitespace-pre-wrap font-mono">{{ run.error_log }}</pre>
              </div>
            </div>

            <!-- Timestamps -->
            <div class="flex gap-6 text-xs text-text-muted">
              <div>
                <span class="font-medium">Created:</span>
                {{ formatDate(run.created_at) }}
              </div>
              <div v-if="run.started_at">
                <span class="font-medium">Started:</span>
                {{ formatDate(run.started_at) }}
              </div>
              <div v-if="run.completed_at">
                <span class="font-medium">Completed:</span>
                {{ formatDate(run.completed_at) }}
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="relative border-t border-border-subtle p-4 flex justify-end">
            <button
              @click="$emit('close')"
              class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95) translateY(20px);
  opacity: 0;
}

/* Slide transitions for expandable sections */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
