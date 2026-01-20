<script setup lang="ts">
/**
 * ChatMessageList - Scrollable container for chat messages.
 *
 * Features:
 * - Auto-scroll to bottom on new messages
 * - Streaming message indicator
 * - Empty state
 * - Loading state
 */

import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { MessageSquare, Loader2 } from 'lucide-vue-next';
import type { ChatMessage } from '@/types/entities';
import type { StreamingState } from '@/stores/chat';
import ChatMessageComponent from './ChatMessage.vue';
import { strings } from '@/i18n/en';

interface Props {
  messages: ChatMessage[];
  /** Streaming state for real-time updates */
  streaming?: StreamingState;
  /** Show loading indicator */
  loading?: boolean;
  /** Compact mode for quick chat */
  compact?: boolean;
  /** Show timestamps on messages */
  showTimestamps?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  streaming: undefined,
  loading: false,
  compact: false,
  showTimestamps: false,
});

const scrollContainer = ref<HTMLElement | null>(null);

// Filter out tool_result messages (internal protocol messages)
// The ChatToolCall component already shows tool execution status
const displayMessages = computed(() => {
  return props.messages.filter((msg) => msg.role !== 'tool_result');
});

// Auto-scroll to bottom when messages change
const scrollToBottom = () => {
  nextTick(() => {
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
    }
  });
};

// Watch for new messages
watch(
  () => props.messages.length,
  () => scrollToBottom()
);

// Watch streaming content changes
watch(
  () => props.streaming?.content,
  () => scrollToBottom()
);

// Initial scroll
onMounted(() => {
  scrollToBottom();
});

// Expose scroll method for parent components
defineExpose({ scrollToBottom });
</script>

<template>
  <div
    ref="scrollContainer"
    class="flex-1 overflow-y-auto"
    :class="compact ? 'p-2' : 'p-4'"
  >
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center h-full">
      <div class="flex flex-col items-center gap-3 text-text-muted">
        <Loader2 class="w-8 h-8 animate-spin" />
        <span>{{ strings.common.loading }}</span>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="displayMessages.length === 0 && !streaming?.isStreaming"
      class="flex items-center justify-center h-full"
    >
      <div class="flex flex-col items-center gap-4 text-center max-w-sm">
        <div class="w-16 h-16 rounded-full bg-accent-primary/10 flex items-center justify-center">
          <MessageSquare class="w-8 h-8 text-accent-primary" />
        </div>
        <div>
          <h3 class="text-lg font-medium text-text-primary mb-1">
            {{ strings.chat?.emptyTitle || 'Start a Conversation' }}
          </h3>
          <p class="text-sm text-text-secondary">
            {{ strings.chat?.emptyDescription || 'Ask me anything about your feeds, digests, or sources. I can help you search, create, and manage your content.' }}
          </p>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div v-else class="space-y-1">
      <ChatMessageComponent
        v-for="message in displayMessages"
        :key="message.id"
        :message="message"
        :compact="compact"
        :show-timestamp="showTimestamps"
      />

      <!-- Streaming indicator (shown while waiting for first content) -->
      <div
        v-if="streaming?.isStreaming && !streaming.content"
        class="flex gap-3 px-4 py-3"
      >
        <div class="flex-shrink-0 w-8 h-8 rounded-full bg-accent-primary/10 flex items-center justify-center">
          <Loader2 class="w-4 h-4 text-accent-primary animate-spin" />
        </div>
        <div class="flex items-center">
          <span class="text-sm text-text-muted">Thinking...</span>
        </div>
      </div>

      <!-- Streaming tool calls -->
      <div
        v-if="streaming?.isStreaming && streaming?.toolCalls.length"
        class="px-4 py-2 space-y-2"
      >
        <div
          v-for="tc in streaming.toolCalls"
          :key="tc.id"
          class="flex items-center gap-2 text-sm text-text-muted"
        >
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>Calling {{ tc.name }}...</span>
        </div>
      </div>
    </div>
  </div>
</template>
