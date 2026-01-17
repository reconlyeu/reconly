<script setup lang="ts">
/**
 * ChatContainer - Main chat interface combining message list and input.
 *
 * Features:
 * - Message list with streaming support
 * - Input with send/cancel functionality
 * - Header with conversation title
 * - Empty state for new conversations
 */

import { ref, computed, onMounted, watch } from 'vue';
import { Trash2, Edit2, Check, X } from 'lucide-vue-next';
import { useChat } from '@/composables/useChat';
import ChatMessageList from './ChatMessageList.vue';
import ChatInput from './ChatInput.vue';
import { strings } from '@/i18n/en';

interface Props {
  /** Conversation ID to display */
  conversationId?: number | null;
  /** Compact mode for quick chat */
  compact?: boolean;
  /** Show header */
  showHeader?: boolean;
  /** Show timestamps on messages */
  showTimestamps?: boolean;
}

interface Emits {
  (e: 'delete'): void;
}

const props = withDefaults(defineProps<Props>(), {
  conversationId: null,
  compact: false,
  showHeader: true,
  showTimestamps: false,
});

const emit = defineEmits<Emits>();

const {
  activeMessages,
  activeConversation,
  messagesLoading,
  streaming,
  isStreaming,
  loadConversation,
  sendStream,
  cancelStream,
  updateConversationData,
} = useChat();

const messageListRef = ref<InstanceType<typeof ChatMessageList> | null>(null);
const inputRef = ref<InstanceType<typeof ChatInput> | null>(null);

// Title editing
const isEditingTitle = ref(false);
const editedTitle = ref('');

const conversationTitle = computed(() => {
  return activeConversation.value?.title || strings.chat?.newConversation || 'New Conversation';
});

// Load conversation when ID changes
watch(
  () => props.conversationId,
  async (newId) => {
    if (newId) {
      await loadConversation(newId);
    }
  },
  { immediate: true }
);

// Handle send message
const handleSend = (message: string) => {
  if (!props.conversationId) return;
  sendStream(message, props.conversationId);
};

// Handle cancel stream
const handleCancel = () => {
  cancelStream();
};

// Title editing
const startEditingTitle = () => {
  editedTitle.value = activeConversation.value?.title || '';
  isEditingTitle.value = true;
};

const saveTitle = async () => {
  if (!props.conversationId || !editedTitle.value.trim()) {
    isEditingTitle.value = false;
    return;
  }

  try {
    await updateConversationData(props.conversationId, {
      title: editedTitle.value.trim(),
    });
  } finally {
    isEditingTitle.value = false;
  }
};

const cancelEditTitle = () => {
  isEditingTitle.value = false;
};

// Focus input on mount
onMounted(() => {
  inputRef.value?.focus();
});
</script>

<template>
  <div class="flex flex-col h-full bg-bg-base">
    <!-- Header -->
    <header
      v-if="showHeader"
      class="flex-shrink-0 h-14 px-4 flex items-center justify-between border-b border-border-subtle bg-bg-surface"
    >
      <!-- Title -->
      <div class="group flex items-center gap-2 min-w-0 flex-1">
        <template v-if="isEditingTitle">
          <input
            v-model="editedTitle"
            @keyup.enter="saveTitle"
            @keyup.escape="cancelEditTitle"
            type="text"
            class="flex-1 bg-bg-elevated border border-border-subtle rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent-primary"
            autofocus
          />
          <button
            @click="saveTitle"
            class="p-1 text-status-success hover:bg-status-success/10 rounded"
          >
            <Check class="w-4 h-4" />
          </button>
          <button
            @click="cancelEditTitle"
            class="p-1 text-text-muted hover:bg-bg-hover rounded"
          >
            <X class="w-4 h-4" />
          </button>
        </template>
        <template v-else>
          <h2 class="text-base font-medium text-text-primary truncate">
            {{ conversationTitle }}
          </h2>
          <button
            v-if="conversationId"
            @click="startEditingTitle"
            class="p-1 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Edit2 class="w-4 h-4" />
          </button>
        </template>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-1">
        <button
          v-if="conversationId"
          @click="emit('delete')"
          class="p-2 text-text-muted hover:text-status-failed hover:bg-status-failed/10 rounded-lg transition-colors"
          title="Delete conversation"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </header>

    <!-- Messages -->
    <ChatMessageList
      ref="messageListRef"
      :messages="activeMessages"
      :streaming="streaming"
      :loading="messagesLoading"
      :compact="compact"
      :show-timestamps="showTimestamps"
      class="flex-1 min-h-0"
    />

    <!-- Input -->
    <ChatInput
      ref="inputRef"
      :disabled="messagesLoading"
      :streaming="isStreaming"
      :compact="compact"
      @submit="handleSend"
      @cancel="handleCancel"
    />
  </div>
</template>
