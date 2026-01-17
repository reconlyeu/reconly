<script setup lang="ts">
/**
 * QuickChatPanel - Slide-up compact chat panel.
 *
 * Features:
 * - Slides up from FloatingChatTab
 * - 400x500px compact chat interface
 * - Dismiss with Escape or click outside
 * - Link to open full chat page
 * - Single conversation mode
 */

import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { X, ExternalLink, Loader2 } from 'lucide-vue-next';
import { useChatStore } from '@/stores/chat';
import { useChat } from '@/composables/useChat';
import ChatMessageList from './ChatMessageList.vue';
import ChatInput from './ChatInput.vue';
import { strings } from '@/i18n/en';

interface Props {
  /** Whether the panel is visible */
  visible: boolean;
}

interface Emits {
  (e: 'close'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const store = useChatStore();
const {
  quickChatConversationId,
  createNewConversation,
  loadConversation,
  sendStream,
  cancelStream,
} = useChat();

const panelRef = ref<HTMLElement | null>(null);
const inputRef = ref<InstanceType<typeof ChatInput> | null>(null);

// Messages for quick chat (separate from main chat)
const messages = ref<typeof store.activeMessages>([]);
const loading = ref(false);

// Initialize conversation when panel opens
watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      if (!store.quickChatConversationId) {
        // Create a new conversation for quick chat
        try {
          loading.value = true;
          const conv = await createNewConversation({ title: 'Quick Chat' }, false);
          store.setQuickChatConversation(conv.id);
        } finally {
          loading.value = false;
        }
      } else {
        // Load existing quick chat conversation
        try {
          loading.value = true;
          await loadConversation(store.quickChatConversationId);
        } finally {
          loading.value = false;
        }
      }

      // Focus input after opening
      nextTick(() => {
        inputRef.value?.focus();
      });
    }
  }
);

// Sync messages from store when quick chat conversation is active
watch(
  () => [store.quickChatConversationId, store.activeConversationId, store.activeMessages],
  () => {
    if (
      store.quickChatConversationId &&
      store.activeConversationId === store.quickChatConversationId
    ) {
      messages.value = store.activeMessages;
    }
  },
  { deep: true, immediate: true }
);

// Handle send message
const handleSend = (message: string) => {
  if (!store.quickChatConversationId) return;

  // Ensure this conversation is active in the store
  if (store.activeConversationId !== store.quickChatConversationId) {
    store.setActiveConversation(store.quickChatConversationId);
  }

  sendStream(message, store.quickChatConversationId);
};

// Handle cancel
const handleCancel = () => {
  cancelStream();
};

// Close panel
const close = () => {
  emit('close');
};

// Handle click outside
const handleClickOutside = (event: MouseEvent) => {
  if (panelRef.value && !panelRef.value.contains(event.target as Node)) {
    close();
  }
};

// Handle Escape key
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    close();
  }
};

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside);
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside);
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-4 scale-95"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 translate-y-4 scale-95"
  >
    <div
      v-if="visible"
      ref="panelRef"
      class="fixed bottom-20 right-6 z-50 w-[400px] h-[500px] bg-bg-surface rounded-2xl shadow-2xl border border-border-subtle overflow-hidden flex flex-col"
    >
      <!-- Header -->
      <header class="flex-shrink-0 h-12 px-4 flex items-center justify-between border-b border-border-subtle bg-bg-elevated">
        <h3 class="text-sm font-medium text-text-primary">
          {{ strings.chat?.quickChat || 'Quick Chat' }}
        </h3>
        <div class="flex items-center gap-2">
          <!-- Open full chat link -->
          <a
            href="/chat"
            class="flex items-center gap-1 text-xs text-text-muted hover:text-accent-primary transition-colors"
            title="Open full chat"
          >
            <span>{{ strings.chat?.openFullChat || 'Open full chat' }}</span>
            <ExternalLink class="w-3 h-3" />
          </a>
          <!-- Close button -->
          <button
            @click="close"
            class="p-1.5 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
            title="Close"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </header>

      <!-- Loading state -->
      <div v-if="loading" class="flex-1 flex items-center justify-center">
        <div class="flex flex-col items-center gap-2">
          <Loader2 class="w-6 h-6 animate-spin text-accent-primary" />
          <span class="text-sm text-text-muted">{{ strings.common.loading }}</span>
        </div>
      </div>

      <!-- Chat content -->
      <template v-else>
        <!-- Messages -->
        <ChatMessageList
          :messages="messages"
          :streaming="store.streaming"
          :loading="false"
          compact
          class="flex-1 min-h-0"
        />

        <!-- Input -->
        <ChatInput
          ref="inputRef"
          :streaming="store.streaming.isStreaming"
          compact
          @submit="handleSend"
          @cancel="handleCancel"
        />
      </template>
    </div>
  </Transition>
</template>
