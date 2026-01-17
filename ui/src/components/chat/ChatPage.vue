<script setup lang="ts">
/**
 * ChatPage - Full chat page with sidebar and main chat area.
 *
 * Features:
 * - Conversation sidebar on the left
 * - Main chat container on the right
 * - Create/select/delete conversations
 * - URL-based conversation selection
 */

import { ref, computed, onMounted, watch } from 'vue';
import { useChat } from '@/composables/useChat';
import ConversationSidebar from './ConversationSidebar.vue';
import ChatContainer from './ChatContainer.vue';
import { MessageSquare } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

const {
  conversations,
  activeConversationId,
  loadConversations,
  loadConversation,
  createNewConversation,
  deleteConversationById,
  setActiveConversation,
} = useChat();

const sidebarCollapsed = ref(false);

// Get conversation ID from URL hash
const getConversationIdFromUrl = () => {
  if (typeof window === 'undefined') return null;
  const hash = window.location.hash;
  if (hash.startsWith('#conversation/')) {
    const id = parseInt(hash.replace('#conversation/', ''), 10);
    return isNaN(id) ? null : id;
  }
  return null;
};

// Update URL when conversation changes
const updateUrl = (conversationId: number | null) => {
  if (typeof window === 'undefined') return;
  if (conversationId) {
    window.history.replaceState(null, '', `#conversation/${conversationId}`);
  } else {
    window.history.replaceState(null, '', window.location.pathname);
  }
};

// Handle conversation selection
const handleSelectConversation = async (id: number) => {
  try {
    await loadConversation(id);
    updateUrl(id);
  } catch {
    // Conversation not found - refresh list and show empty state
    await loadConversations();
    updateUrl(null);
  }
};

// Handle create conversation
const handleCreateConversation = async () => {
  try {
    const conversation = await createNewConversation({});
    updateUrl(conversation.id);
  } catch {
    // Error handled in createNewConversation
  }
};

// Handle delete conversation
const handleDeleteConversation = async (id: number) => {
  try {
    await deleteConversationById(id);

    // If deleted the active conversation, clear selection
    if (activeConversationId.value === id) {
      setActiveConversation(null);
      updateUrl(null);
    }
  } catch {
    // Error handled in deleteConversationById
  }
};

// Handle delete from container
const handleDeleteFromContainer = () => {
  if (activeConversationId.value) {
    if (window.confirm('Delete this conversation? This cannot be undone.')) {
      handleDeleteConversation(activeConversationId.value);
    }
  }
};

// Initialize
onMounted(async () => {
  // Load conversations
  await loadConversations();

  // Check URL for conversation ID
  const urlConversationId = getConversationIdFromUrl();
  if (urlConversationId) {
    try {
      await loadConversation(urlConversationId);
    } catch {
      // Conversation not found - clear URL and show empty state
      updateUrl(null);
    }
  } else if (conversations.value && conversations.value.length > 0) {
    // Select most recent conversation
    const mostRecent = conversations.value[0];
    try {
      await loadConversation(mostRecent.id);
      updateUrl(mostRecent.id);
    } catch {
      // Conversation not found - show empty state
      updateUrl(null);
    }
  }
});

// Handle browser back/forward
if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', async () => {
    const id = getConversationIdFromUrl();
    if (id && id !== activeConversationId.value) {
      try {
        await loadConversation(id);
      } catch {
        updateUrl(null);
      }
    }
  });
}
</script>

<template>
  <div class="flex h-[calc(100vh-8rem)] bg-bg-base rounded-xl overflow-hidden border border-border-subtle">
    <!-- Sidebar -->
    <div
      class="flex-shrink-0 transition-all duration-300"
      :class="sidebarCollapsed ? 'w-0' : 'w-72'"
    >
      <ConversationSidebar
        v-show="!sidebarCollapsed"
        :active-id="activeConversationId"
        @select="handleSelectConversation"
        @create="handleCreateConversation"
        @delete="handleDeleteConversation"
      />
    </div>

    <!-- Main content -->
    <div class="flex-1 min-w-0">
      <!-- Chat container when conversation is selected -->
      <ChatContainer
        v-if="activeConversationId"
        :conversation-id="activeConversationId"
        show-header
        show-timestamps
        @delete="handleDeleteFromContainer"
      />

      <!-- Empty state when no conversation is selected -->
      <div
        v-else
        class="h-full flex items-center justify-center"
      >
        <div class="flex flex-col items-center gap-6 text-center max-w-md px-6">
          <div class="w-20 h-20 rounded-full bg-accent-primary/10 flex items-center justify-center">
            <MessageSquare class="w-10 h-10 text-accent-primary" />
          </div>
          <div>
            <h2 class="text-2xl font-semibold text-text-primary mb-2">
              {{ strings.chat?.welcomeTitle || 'Welcome to Chat' }}
            </h2>
            <p class="text-text-secondary">
              {{ strings.chat?.welcomeDescription || 'Start a new conversation or select an existing one from the sidebar. I can help you manage your feeds, search digests, and answer questions about your content.' }}
            </p>
          </div>
          <button
            @click="handleCreateConversation"
            class="px-6 py-3 rounded-xl bg-accent-primary text-white hover:bg-accent-primary-hover transition-colors font-medium"
          >
            {{ strings.chat?.startConversation || 'Start a Conversation' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
