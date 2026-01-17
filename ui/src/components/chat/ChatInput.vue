<script setup lang="ts">
/**
 * ChatInput - Input field with send button for chat messages.
 *
 * Features:
 * - Auto-resize textarea
 * - Submit on Enter (Shift+Enter for new line)
 * - Cancel button during streaming
 * - Disabled state while streaming
 */

import { ref, computed, watch, nextTick } from 'vue';
import { Send, Square, Loader2 } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  /** Disable input (e.g., while streaming) */
  disabled?: boolean;
  /** Show streaming state (cancel button instead of send) */
  streaming?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Compact mode for quick chat */
  compact?: boolean;
}

interface Emits {
  (e: 'submit', message: string): void;
  (e: 'cancel'): void;
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  streaming: false,
  placeholder: '',
  compact: false,
});

const emit = defineEmits<Emits>();

const message = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const canSubmit = computed(() => {
  return message.value.trim().length > 0 && !props.disabled && !props.streaming;
});

const placeholderText = computed(() => {
  return props.placeholder || strings.chat?.inputPlaceholder || 'Ask a question...';
});

// Auto-resize textarea
const resizeTextarea = () => {
  const textarea = textareaRef.value;
  if (textarea) {
    textarea.style.height = 'auto';
    const maxHeight = props.compact ? 100 : 200;
    textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
  }
};

watch(message, () => {
  nextTick(resizeTextarea);
});

// Handle submit
const handleSubmit = () => {
  if (!canSubmit.value) return;

  const trimmedMessage = message.value.trim();
  message.value = '';
  nextTick(resizeTextarea);

  emit('submit', trimmedMessage);
};

// Handle cancel
const handleCancel = () => {
  emit('cancel');
};

// Handle keydown
const handleKeydown = (event: KeyboardEvent) => {
  // Submit on Enter (without Shift)
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSubmit();
  }
};

// Focus input
const focus = () => {
  textareaRef.value?.focus();
};

defineExpose({ focus });
</script>

<template>
  <div
    class="border-t border-border-subtle bg-bg-surface"
    :class="compact ? 'p-2' : 'p-4'"
  >
    <div class="flex items-start gap-2">
      <!-- Input -->
      <div class="flex-1 relative">
        <textarea
          ref="textareaRef"
          v-model="message"
          @keydown="handleKeydown"
          :placeholder="placeholderText"
          :disabled="disabled || streaming"
          rows="1"
          class="w-full resize-none rounded-xl border border-border-subtle bg-bg-elevated text-sm text-text-primary placeholder-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :class="compact ? 'h-8 py-1.5 px-3' : 'h-10 py-2.5 px-4'"
        />
      </div>

      <!-- Send/Cancel button -->
      <button
        v-if="streaming"
        @click="handleCancel"
        type="button"
        class="flex-shrink-0 rounded-xl bg-status-failed text-white flex items-center justify-center hover:bg-status-failed/90 transition-colors"
        :class="compact ? 'w-8 h-8' : 'w-10 h-10'"
        title="Cancel"
      >
        <Square class="w-4 h-4" />
      </button>
      <button
        v-else
        @click="handleSubmit"
        type="button"
        :disabled="!canSubmit"
        class="flex-shrink-0 rounded-xl bg-accent-primary text-white flex items-center justify-center hover:bg-accent-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :class="compact ? 'w-8 h-8' : 'w-10 h-10'"
        title="Send message"
      >
        <Loader2 v-if="disabled" class="w-4 h-4 animate-spin" />
        <Send v-else class="w-4 h-4" />
      </button>
    </div>

    <!-- Hint text -->
    <p v-if="!compact" class="mt-2 text-xs text-text-muted text-center">
      Press Enter to send, Shift+Enter for new line
    </p>
  </div>
</template>
