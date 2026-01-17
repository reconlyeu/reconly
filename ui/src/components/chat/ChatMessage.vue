<script setup lang="ts">
/**
 * ChatMessage - Displays a single chat message (user, assistant, or tool).
 *
 * Features:
 * - Different styling for user vs assistant messages
 * - Markdown rendering for assistant content
 * - Tool call display integration
 * - Timestamp display
 */

import { computed } from 'vue';
import { User, Bot, Clock } from 'lucide-vue-next';
import { marked } from 'marked';
import type { ChatMessage } from '@/types/entities';
import ChatToolCall from './ChatToolCall.vue';

// Configure marked for safe rendering
marked.setOptions({
  breaks: true, // Convert \n to <br>
  gfm: true, // GitHub Flavored Markdown
});

interface Props {
  message: ChatMessage;
  /** Show timestamp */
  showTimestamp?: boolean;
  /** Compact mode for quick chat */
  compact?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  showTimestamp: false,
  compact: false,
});

const isUser = computed(() => props.message.role === 'user');

const formattedTime = computed(() => {
  if (!props.message.created_at) return '';
  const date = new Date(props.message.created_at);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
});

// Parse tool call for display
const parsedToolCalls = computed(() => {
  if (!props.message.tool_calls) return [];
  return props.message.tool_calls.map((tc) => ({
    id: tc.id,
    name: tc.name,
    arguments: tc.parameters || {},
  }));
});

// Render markdown content for assistant messages
const renderedContent = computed(() => {
  if (!props.message.content) return '';
  if (isUser.value) return props.message.content; // Don't render markdown for user messages
  return marked.parse(props.message.content) as string;
});
</script>

<template>
  <div
    class="flex gap-3"
    :class="[
      isUser ? 'justify-end' : 'justify-start',
      compact ? 'px-2 py-1' : 'px-4 py-3',
    ]"
  >
    <!-- Avatar (assistant only, left side) -->
    <div
      v-if="!isUser"
      class="flex-shrink-0 w-8 h-8 rounded-full bg-accent-primary/10 flex items-center justify-center"
    >
      <Bot class="w-4 h-4 text-accent-primary" />
    </div>

    <!-- Message content -->
    <div
      class="max-w-[80%] min-w-0"
      :class="compact ? 'max-w-[90%]' : 'max-w-[80%]'"
    >
      <!-- Message bubble -->
      <div
        class="rounded-2xl"
        :class="[
          isUser
            ? 'bg-accent-primary text-white rounded-br-md'
            : 'bg-bg-elevated border border-border-subtle rounded-bl-md',
          compact ? 'px-3 py-2' : 'px-4 py-3',
        ]"
      >
        <!-- Text content -->
        <div
          v-if="message.content && isUser"
          class="whitespace-pre-wrap break-words text-sm leading-relaxed text-white"
        >
          {{ message.content }}
        </div>
        <!-- Markdown content for assistant -->
        <div
          v-else-if="message.content"
          class="prose prose-sm prose-invert max-w-none break-words text-text-primary
                 prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5
                 prose-a:text-accent-primary prose-a:no-underline hover:prose-a:underline
                 prose-code:bg-bg-surface prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                 prose-pre:bg-bg-surface prose-pre:p-3 prose-pre:rounded-lg prose-pre:whitespace-pre-wrap prose-pre:break-words"
          v-html="renderedContent"
        />

        <!-- Tool calls (for assistant messages requesting tools) -->
        <!-- These are completed tool calls from saved messages, so success=true -->
        <div v-if="parsedToolCalls.length > 0" class="mt-2 space-y-2">
          <ChatToolCall
            v-for="tc in parsedToolCalls"
            :key="tc.id"
            :name="tc.name"
            :arguments="tc.arguments"
            :success="true"
          />
        </div>
      </div>

      <!-- Timestamp -->
      <div
        v-if="showTimestamp && formattedTime"
        class="flex items-center gap-1 mt-1 text-xs text-text-muted"
        :class="isUser ? 'justify-end' : 'justify-start'"
      >
        <Clock class="w-3 h-3" />
        <span>{{ formattedTime }}</span>
      </div>
    </div>

    <!-- Avatar (user only, right side) -->
    <div
      v-if="isUser"
      class="flex-shrink-0 w-8 h-8 rounded-full bg-accent-primary flex items-center justify-center"
    >
      <User class="w-4 h-4 text-white" />
    </div>
  </div>
</template>
