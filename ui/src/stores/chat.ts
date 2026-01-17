/**
 * Pinia store for Chat conversations and messages.
 *
 * Manages:
 * - Conversation list state
 * - Active conversation and messages
 * - Streaming message state
 * - Quick chat panel visibility
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  ChatConversation,
  ChatMessage,
  ChatStreamToolCallEvent,
  ChatStreamToolResultEvent,
} from '@/types/entities';

export interface StreamingState {
  isStreaming: boolean;
  content: string;
  toolCalls: ChatStreamToolCallEvent[];
  toolResults: ChatStreamToolResultEvent[];
}

export const useChatStore = defineStore('chat', () => {
  // ═══════════════════════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════════════════════

  // Conversation list
  const conversations = ref<ChatConversation[]>([]);
  const totalConversations = ref(0);
  const conversationsLoading = ref(false);

  // Active conversation
  const activeConversationId = ref<number | null>(null);
  const activeMessages = ref<ChatMessage[]>([]);
  const messagesLoading = ref(false);

  // Streaming state
  const streaming = ref<StreamingState>({
    isStreaming: false,
    content: '',
    toolCalls: [],
    toolResults: [],
  });

  // Quick chat panel
  const quickChatOpen = ref(false);
  const quickChatConversationId = ref<number | null>(null);

  // Error state
  const error = ref<string | null>(null);

  // ═══════════════════════════════════════════════════════════════════════════
  // GETTERS
  // ═══════════════════════════════════════════════════════════════════════════

  const activeConversation = computed(() => {
    if (!activeConversationId.value) return null;
    return conversations.value.find((c) => c.id === activeConversationId.value) || null;
  });

  const conversationById = computed(() => {
    return (id: number) => conversations.value.find((c) => c.id === id);
  });

  const hasConversations = computed(() => conversations.value.length > 0);

  const isStreaming = computed(() => streaming.value.isStreaming);

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIONS - Conversations
  // ═══════════════════════════════════════════════════════════════════════════

  const setConversations = (items: ChatConversation[], total: number) => {
    conversations.value = items;
    totalConversations.value = total;
  };

  const addConversation = (conversation: ChatConversation) => {
    // Add at the beginning (most recent first)
    conversations.value.unshift(conversation);
    totalConversations.value++;
  };

  const updateConversation = (id: number, updates: Partial<ChatConversation>) => {
    const index = conversations.value.findIndex((c) => c.id === id);
    if (index !== -1) {
      conversations.value[index] = { ...conversations.value[index], ...updates };
    }
  };

  const removeConversation = (id: number) => {
    conversations.value = conversations.value.filter((c) => c.id !== id);
    totalConversations.value = Math.max(0, totalConversations.value - 1);

    // Clear active if it was the deleted conversation
    if (activeConversationId.value === id) {
      activeConversationId.value = null;
      activeMessages.value = [];
    }

    // Clear quick chat if it was the deleted conversation
    if (quickChatConversationId.value === id) {
      quickChatConversationId.value = null;
    }
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIONS - Active Conversation
  // ═══════════════════════════════════════════════════════════════════════════

  const setActiveConversation = (id: number | null) => {
    activeConversationId.value = id;
    if (id === null) {
      activeMessages.value = [];
    }
  };

  const setMessages = (messages: ChatMessage[]) => {
    activeMessages.value = messages;
  };

  const addMessage = (message: ChatMessage) => {
    activeMessages.value.push(message);

    // Update conversation message count
    if (activeConversationId.value) {
      updateConversation(activeConversationId.value, {
        message_count: activeMessages.value.length,
        updated_at: new Date().toISOString(),
      });
    }
  };

  const updateLastMessage = (updates: Partial<ChatMessage>) => {
    const lastIndex = activeMessages.value.length - 1;
    if (lastIndex >= 0) {
      activeMessages.value[lastIndex] = {
        ...activeMessages.value[lastIndex],
        ...updates,
      };
    }
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIONS - Streaming
  // ═══════════════════════════════════════════════════════════════════════════

  const startStreaming = () => {
    streaming.value = {
      isStreaming: true,
      content: '',
      toolCalls: [],
      toolResults: [],
    };
  };

  const appendStreamContent = (content: string) => {
    streaming.value.content += content;
  };

  const addStreamToolCall = (toolCall: ChatStreamToolCallEvent) => {
    streaming.value.toolCalls.push(toolCall);
  };

  const addStreamToolResult = (toolResult: ChatStreamToolResultEvent) => {
    streaming.value.toolResults.push(toolResult);
  };

  const stopStreaming = () => {
    streaming.value.isStreaming = false;
  };

  const resetStreaming = () => {
    streaming.value = {
      isStreaming: false,
      content: '',
      toolCalls: [],
      toolResults: [],
    };
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIONS - Quick Chat
  // ═══════════════════════════════════════════════════════════════════════════

  const openQuickChat = () => {
    quickChatOpen.value = true;
  };

  const closeQuickChat = () => {
    quickChatOpen.value = false;
  };

  const toggleQuickChat = () => {
    quickChatOpen.value = !quickChatOpen.value;
  };

  const setQuickChatConversation = (id: number | null) => {
    quickChatConversationId.value = id;
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // ACTIONS - Loading & Error
  // ═══════════════════════════════════════════════════════════════════════════

  const setConversationsLoading = (loading: boolean) => {
    conversationsLoading.value = loading;
  };

  const setMessagesLoading = (loading: boolean) => {
    messagesLoading.value = loading;
  };

  const setError = (err: string | null) => {
    error.value = err;
  };

  const clearError = () => {
    error.value = null;
  };

  return {
    // State
    conversations,
    totalConversations,
    conversationsLoading,
    activeConversationId,
    activeMessages,
    messagesLoading,
    streaming,
    quickChatOpen,
    quickChatConversationId,
    error,

    // Getters
    activeConversation,
    conversationById,
    hasConversations,
    isStreaming,

    // Actions - Conversations
    setConversations,
    addConversation,
    updateConversation,
    removeConversation,

    // Actions - Active Conversation
    setActiveConversation,
    setMessages,
    addMessage,
    updateLastMessage,

    // Actions - Streaming
    startStreaming,
    appendStreamContent,
    addStreamToolCall,
    addStreamToolResult,
    stopStreaming,
    resetStreaming,

    // Actions - Quick Chat
    openQuickChat,
    closeQuickChat,
    toggleQuickChat,
    setQuickChatConversation,

    // Actions - Loading & Error
    setConversationsLoading,
    setMessagesLoading,
    setError,
    clearError,
  };
});
