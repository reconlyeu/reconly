<script setup lang="ts">
/**
 * FloatingChatTab - Persistent bottom-right tab to open quick chat.
 *
 * Features:
 * - Fixed position in bottom-right corner
 * - Click to toggle QuickChatPanel
 * - Keyboard shortcut (Cmd/Ctrl+K)
 * - Subtle animation on hover
 * - Badge for unread/streaming status
 */

import { onMounted, onUnmounted, computed } from 'vue';
import { MessageSquare, Loader2 } from 'lucide-vue-next';
import { useChatStore } from '@/stores/chat';
import { strings } from '@/i18n/en';

interface Emits {
  (e: 'toggle'): void;
}

const emit = defineEmits<Emits>();

const store = useChatStore();

const isStreaming = computed(() => store.streaming.isStreaming);
const isOpen = computed(() => store.quickChatOpen);

// Check if Mac for keyboard shortcut display (SSR-safe)
const isMac = computed(() => {
  if (typeof navigator === 'undefined') return false;
  return navigator.platform?.includes('Mac') ?? false;
});

// Handle keyboard shortcut (Cmd/Ctrl+K)
const handleKeydown = (event: KeyboardEvent) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
    event.preventDefault();
    emit('toggle');
  }
};

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});

const handleClick = () => {
  emit('toggle');
};
</script>

<template>
  <button
    @click="handleClick"
    class="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full bg-accent-primary text-white shadow-lg hover:bg-accent-primary-hover hover:shadow-xl hover:scale-105 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
    :class="isOpen ? 'opacity-50' : 'opacity-100'"
    :aria-label="strings.chat?.askAI || 'Ask AI'"
    :title="`${strings.chat?.askAI || 'Ask AI'} (Ctrl+K)`"
  >
    <!-- Icon -->
    <Loader2 v-if="isStreaming" class="w-5 h-5 animate-spin" />
    <MessageSquare v-else class="w-5 h-5" />

    <!-- Label -->
    <span class="text-sm font-medium whitespace-nowrap">
      {{ strings.chat?.askAI || 'Ask AI' }}
    </span>

    <!-- Keyboard shortcut hint -->
    <kbd class="hidden sm:inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-white/20 ml-1">
      <span class="text-[10px]">{{ isMac ? '&#8984;' : 'Ctrl' }}</span>
      <span class="ml-0.5">K</span>
    </kbd>
  </button>
</template>
