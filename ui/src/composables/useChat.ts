/**
 * Composable for chat functionality.
 *
 * Provides a high-level API for:
 * - Loading and managing conversations
 * - Sending messages (streaming and non-streaming)
 * - Creating and deleting conversations
 * - Quick chat panel management
 */

import { ref, computed, onUnmounted } from 'vue';
import { useChatStore } from '@/stores/chat';
import { storeToRefs } from 'pinia';
import { useToast } from '@/composables/useToast';
import {
  listConversations,
  createConversation,
  getConversation,
  updateConversation,
  deleteConversation,
  sendMessage,
  sendMessageStream,
  type ChatStreamHandlers,
} from '@/chatApi';
import type {
  ChatConversationCreate,
  ChatConversationUpdate,
  ChatMessage,
} from '@/types/entities';

export function useChat() {
  const store = useChatStore();
  const toast = useToast();

  // Use storeToRefs to maintain reactivity for ALL state
  // This ensures both primitives and arrays stay reactive when destructured
  const storeRefs = storeToRefs(store);

  // Track active stream for cleanup
  const activeStream = ref<{ close: () => void } | null>(null);

  // Cleanup on unmount
  onUnmounted(() => {
    if (activeStream.value) {
      activeStream.value.close();
      activeStream.value = null;
    }
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // CONVERSATION MANAGEMENT
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Load all conversations.
   */
  async function loadConversations(limit = 50, offset = 0) {
    store.setConversationsLoading(true);
    store.clearError();

    try {
      const result = await listConversations(limit, offset);
      store.setConversations(result.items, result.total);
    } catch (error) {
      const message = (error as Error).message || 'Failed to load conversations';
      store.setError(message);
      toast.error(message);
    } finally {
      store.setConversationsLoading(false);
    }
  }

  /**
   * Create a new conversation and optionally set it as active.
   */
  async function createNewConversation(
    data: ChatConversationCreate = {},
    setActive = true
  ) {
    try {
      const conversation = await createConversation(data);
      store.addConversation(conversation);

      if (setActive) {
        store.setActiveConversation(conversation.id);
        store.setMessages([]);
      }

      return conversation;
    } catch (error) {
      const message = (error as Error).message || 'Failed to create conversation';
      store.setError(message);
      toast.error(message);
      throw error;
    }
  }

  /**
   * Load a specific conversation with its messages.
   */
  async function loadConversation(conversationId: number) {
    store.setMessagesLoading(true);
    store.clearError();

    try {
      const detail = await getConversation(conversationId);
      store.setActiveConversation(conversationId);
      store.setMessages(detail.messages);

      // Update conversation in list if present
      store.updateConversation(conversationId, {
        message_count: detail.message_count,
        updated_at: detail.updated_at,
      });

      return detail;
    } catch (error) {
      const message = (error as Error).message || 'Failed to load conversation';
      store.setError(message);
      toast.error(message);
      throw error;
    } finally {
      store.setMessagesLoading(false);
    }
  }

  /**
   * Update a conversation's title or settings.
   */
  async function updateConversationData(
    conversationId: number,
    data: ChatConversationUpdate
  ) {
    try {
      const updated = await updateConversation(conversationId, data);
      store.updateConversation(conversationId, updated);
      return updated;
    } catch (error) {
      const message = (error as Error).message || 'Failed to update conversation';
      store.setError(message);
      toast.error(message);
      throw error;
    }
  }

  /**
   * Delete a conversation.
   */
  async function deleteConversationById(conversationId: number) {
    try {
      await deleteConversation(conversationId);
      store.removeConversation(conversationId);
      toast.success('Conversation deleted');
    } catch (error) {
      const message = (error as Error).message || 'Failed to delete conversation';
      store.setError(message);
      toast.error(message);
      throw error;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CHAT MESSAGING
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Send a message (non-streaming) to the active conversation.
   */
  async function send(message: string, conversationId?: number) {
    const targetConversationId = conversationId ?? store.activeConversationId;

    if (!targetConversationId) {
      throw new Error('No active conversation');
    }

    // Add user message optimistically
    const userMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      conversation_id: targetConversationId,
      role: 'user',
      content: message,
      tool_calls: null,
      tool_call_id: null,
      tokens_in: null,
      tokens_out: null,
      created_at: new Date().toISOString(),
    };
    store.addMessage(userMessage);

    try {
      const response = await sendMessage(targetConversationId, { message });

      // Add assistant response
      store.addMessage(response.message);

      return response;
    } catch (error) {
      const errorMessage = (error as Error).message || 'Failed to send message';
      store.setError(errorMessage);
      toast.error(errorMessage);
      throw error;
    }
  }

  /**
   * Send a message with streaming response.
   */
  function sendStream(
    message: string,
    conversationId?: number,
    onComplete?: () => void
  ) {
    const targetConversationId = conversationId ?? store.activeConversationId;

    if (!targetConversationId) {
      throw new Error('No active conversation');
    }

    // Cancel any existing stream
    if (activeStream.value) {
      activeStream.value.close();
      activeStream.value = null;
    }

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      conversation_id: targetConversationId,
      role: 'user',
      content: message,
      tool_calls: null,
      tool_call_id: null,
      tokens_in: null,
      tokens_out: null,
      created_at: new Date().toISOString(),
    };
    store.addMessage(userMessage);

    // Start streaming state
    store.startStreaming();

    // Add placeholder assistant message
    const assistantMessage: ChatMessage = {
      id: Date.now() + 1, // Temporary ID
      conversation_id: targetConversationId,
      role: 'assistant',
      content: '',
      tool_calls: null,
      tool_call_id: null,
      tokens_in: null,
      tokens_out: null,
      created_at: new Date().toISOString(),
    };
    store.addMessage(assistantMessage);

    const handlers: ChatStreamHandlers = {
      onContent: (event) => {
        store.appendStreamContent(event.content);
        // Update the last message with accumulated content
        store.updateLastMessage({ content: store.streaming.content });
      },

      onToolCall: (event) => {
        store.addStreamToolCall(event);
      },

      onToolResult: (event) => {
        store.addStreamToolResult(event);
      },

      onDone: (event) => {
        store.stopStreaming();
        // Update message with final token counts
        store.updateLastMessage({
          tokens_in: event.tokens_in,
          tokens_out: event.tokens_out,
        });

        // Refresh conversation to get proper message IDs
        loadConversation(targetConversationId).catch(console.error);

        onComplete?.();
      },

      onError: (event) => {
        store.stopStreaming();
        store.setError(event.error);
        toast.error(event.error);
        onComplete?.();
      },

      onClose: () => {
        activeStream.value = null;
        if (store.streaming.isStreaming) {
          store.stopStreaming();
        }
      },
    };

    activeStream.value = sendMessageStream(targetConversationId, { message }, handlers);

    return {
      cancel: () => {
        if (activeStream.value) {
          activeStream.value.close();
          activeStream.value = null;
          store.stopStreaming();
        }
      },
    };
  }

  /**
   * Cancel any active stream.
   */
  function cancelStream() {
    if (activeStream.value) {
      activeStream.value.close();
      activeStream.value = null;
      store.stopStreaming();
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // QUICK CHAT
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Open quick chat panel, creating a new conversation if needed.
   */
  async function openQuickChat() {
    store.openQuickChat();

    // Create a new conversation if we don't have one
    if (!store.quickChatConversationId) {
      try {
        const conversation = await createNewConversation(
          { title: 'Quick Chat' },
          false
        );
        store.setQuickChatConversation(conversation.id);
      } catch {
        // Error already handled in createNewConversation
      }
    }
  }

  /**
   * Close quick chat panel.
   */
  function closeQuickChat() {
    store.closeQuickChat();
    cancelStream();
  }

  /**
   * Toggle quick chat panel.
   */
  async function toggleQuickChat() {
    if (store.quickChatOpen) {
      closeQuickChat();
    } else {
      await openQuickChat();
    }
  }

  /**
   * Send message in quick chat.
   */
  function sendQuickChatMessage(message: string) {
    if (!store.quickChatConversationId) {
      toast.error('No conversation available');
      return;
    }

    return sendStream(message, store.quickChatConversationId);
  }

  // Computed getters that need to be derived
  const activeConversation = computed(() => store.activeConversation);
  const isStreaming = computed(() => store.isStreaming);

  return {
    // State (reactive refs from storeToRefs - use .value in scripts, auto-unwrapped in templates)
    conversations: storeRefs.conversations,
    totalConversations: storeRefs.totalConversations,
    conversationsLoading: storeRefs.conversationsLoading,
    activeConversationId: storeRefs.activeConversationId,
    activeConversation,
    activeMessages: storeRefs.activeMessages,
    messagesLoading: storeRefs.messagesLoading,
    streaming: storeRefs.streaming,
    isStreaming,
    quickChatOpen: storeRefs.quickChatOpen,
    quickChatConversationId: storeRefs.quickChatConversationId,
    error: storeRefs.error,

    // Conversation management
    loadConversations,
    createNewConversation,
    loadConversation,
    updateConversationData,
    deleteConversationById,
    setActiveConversation: store.setActiveConversation,

    // Messaging
    send,
    sendStream,
    cancelStream,

    // Quick chat
    openQuickChat,
    closeQuickChat,
    toggleQuickChat,
    sendQuickChatMessage,

    // Error handling
    clearError: store.clearError,
  };
}
