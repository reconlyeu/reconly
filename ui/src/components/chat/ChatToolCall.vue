<script setup lang="ts">
/**
 * ChatToolCall - Displays a tool call with collapsible details.
 *
 * Features:
 * - Collapsible arguments view
 * - Status indicator (pending, success, error)
 * - Formatted argument display
 */

import { ref, computed } from 'vue';
import { Wrench, ChevronDown, ChevronRight, Check, X, Loader2 } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  /** Tool name */
  name: string;
  /** Tool arguments (parsed JSON object) */
  arguments: Record<string, unknown>;
  /** Result of the tool call (if completed) */
  result?: unknown;
  /** Whether the tool call succeeded */
  success?: boolean | null;
  /** Error message if failed */
  error?: string | null;
  /** Whether the tool is currently executing */
  pending?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  result: undefined,
  success: null,
  error: null,
  pending: false,
});

const expanded = ref(false);

const toggleExpanded = () => {
  expanded.value = !expanded.value;
};

// Format tool name for display (snake_case to Title Case)
const displayName = computed(() => {
  return props.name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
});

// Status styling
const statusClass = computed(() => {
  if (props.pending) return 'text-status-running';
  if (props.success === true) return 'text-status-success';
  if (props.success === false) return 'text-status-failed';
  return 'text-text-muted';
});

// Format arguments for display
const formattedArgs = computed(() => {
  return JSON.stringify(props.arguments, null, 2);
});

// Format result for display
const formattedResult = computed(() => {
  if (props.result === undefined) return null;
  return typeof props.result === 'string'
    ? props.result
    : JSON.stringify(props.result, null, 2);
});
</script>

<template>
  <div class="border border-border-subtle rounded-lg bg-bg-surface overflow-hidden">
    <!-- Header (clickable to expand) -->
    <button
      @click="toggleExpanded"
      class="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-bg-hover transition-colors"
    >
      <!-- Expand/collapse icon -->
      <component
        :is="expanded ? ChevronDown : ChevronRight"
        class="w-4 h-4 text-text-muted flex-shrink-0"
      />

      <!-- Tool icon -->
      <Wrench class="w-4 h-4 text-accent-primary flex-shrink-0" />

      <!-- Tool name -->
      <span class="font-medium text-text-primary flex-1 text-left">
        {{ displayName }}
      </span>

      <!-- Status indicator -->
      <span class="flex-shrink-0" :class="statusClass">
        <Loader2 v-if="pending" class="w-4 h-4 animate-spin" />
        <Check v-else-if="success === true" class="w-4 h-4" />
        <X v-else-if="success === false" class="w-4 h-4" />
      </span>
    </button>

    <!-- Expanded content -->
    <div v-if="expanded" class="border-t border-border-subtle">
      <!-- Arguments -->
      <div class="px-3 py-2">
        <div class="text-xs text-text-muted mb-1">{{ strings.chat.toolCall.arguments }}</div>
        <pre class="text-xs text-text-secondary bg-bg-base p-2 rounded whitespace-pre-wrap break-words">{{ formattedArgs }}</pre>
      </div>

      <!-- Result (if available) -->
      <div v-if="formattedResult !== null" class="px-3 py-2 border-t border-border-subtle">
        <div class="text-xs text-text-muted mb-1">{{ strings.chat.toolCall.result }}</div>
        <pre class="text-xs text-text-secondary bg-bg-base p-2 rounded whitespace-pre-wrap break-words max-h-40 overflow-y-auto">{{ formattedResult }}</pre>
      </div>

      <!-- Error (if failed) -->
      <div v-if="error" class="px-3 py-2 border-t border-border-subtle">
        <div class="text-xs text-status-failed mb-1">{{ strings.chat.toolCall.error }}</div>
        <pre class="text-xs text-status-failed/80 bg-status-failed/5 p-2 rounded whitespace-pre-wrap break-words">{{ error }}</pre>
      </div>
    </div>
  </div>
</template>
