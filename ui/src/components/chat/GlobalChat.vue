<script setup lang="ts">
/**
 * GlobalChat - Container for floating chat tab and quick chat panel.
 *
 * This component should be placed in the layout to provide:
 * - FloatingChatTab in bottom-right corner
 * - QuickChatPanel that slides up when tab is clicked
 * - Keyboard shortcut (Cmd/Ctrl+K) support
 *
 * Note: Hidden on /chat page since it has full chat interface
 */

import { ref, onMounted } from 'vue';
import { useChatStore } from '@/stores/chat';
import FloatingChatTab from './FloatingChatTab.vue';
import QuickChatPanel from './QuickChatPanel.vue';

const store = useChatStore();

// Hide on chat page - already has full chat interface
const isOnChatPage = ref(false);
onMounted(() => {
  isOnChatPage.value = window.location.pathname === '/chat' || window.location.pathname === '/chat/';
});

const handleToggle = () => {
  store.toggleQuickChat();
};

const handleClose = () => {
  store.closeQuickChat();
};
</script>

<template>
  <!-- Hidden on chat page - already has full chat interface -->
  <template v-if="!isOnChatPage">
    <!-- Floating tab -->
    <FloatingChatTab @toggle="handleToggle" />

    <!-- Quick chat panel (slides up when open) -->
    <QuickChatPanel
      :visible="store.quickChatOpen"
      @close="handleClose"
    />
  </template>
</template>
