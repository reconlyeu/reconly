<script setup lang="ts">
/**
 * ConversationSidebar - List of chat conversations with create button.
 *
 * Features:
 * - Conversation list with timestamps
 * - Create new conversation button
 * - Active conversation highlighting
 * - Delete conversation option
 * - Loading state
 */

import { computed, onMounted } from 'vue';
import { Plus, MessageSquare, Trash2, Loader2 } from 'lucide-vue-next';
import { useQuery } from '@tanstack/vue-query';
import { useChat } from '@/composables/useChat';
import { settingsApi } from '@/services/api';
import { strings } from '@/i18n/en';

interface Props {
  /** Currently active conversation ID */
  activeId?: number | null;
}

interface Emits {
  (e: 'select', id: number): void;
  (e: 'create'): void;
  (e: 'delete', id: number): void;
}

const props = withDefaults(defineProps<Props>(), {
  activeId: null,
});

const emit = defineEmits<Emits>();

const {
  conversations,
  conversationsLoading,
  loadConversations,
  activeConversation,
} = useChat();

// Fetch default LLM settings
const { data: llmSettings } = useQuery({
  queryKey: ['settings-v2', 'llm'],
  queryFn: () => settingsApi.getV2({ groups: ['provider'] }),
  staleTime: 60000, // Cache for 1 minute
});

// Display provider and model info
const poweredByText = computed(() => {
  // First check conversation-specific settings
  let provider = activeConversation.value?.model_provider;
  let model = activeConversation.value?.model_name;

  // Fall back to default settings if not set on conversation
  if (!provider && llmSettings.value?.provider?.default_provider?.value) {
    provider = String(llmSettings.value.provider.default_provider.value);
  }
  if (!model && llmSettings.value?.provider?.default_model?.value) {
    model = String(llmSettings.value.provider.default_model.value);
  }

  if (provider && model) {
    return `Powered by ${provider} / ${model}`;
  } else if (provider) {
    return `${provider} (no model selected)`;
  } else if (model) {
    return `Powered by ${model}`;
  }
  return 'LLM not configured';
});

// Format relative time
const formatRelativeTime = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return strings.time.justNow;
  if (diffMins < 60) return strings.time.minutesAgo.replace('{count}', diffMins.toString());
  if (diffHours < 24) return strings.time.hoursAgo.replace('{count}', diffHours.toString());
  if (diffDays < 7) return strings.time.daysAgo.replace('{count}', diffDays.toString());

  return date.toLocaleDateString();
};

// Sorted conversations (most recent first)
// Note: With storeToRefs, conversations is a ref - use .value in scripts
const sortedConversations = computed(() => {
  const list = conversations.value || [];
  if (list.length === 0) {
    return [];
  }
  return [...list].sort((a, b) => {
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });
});

// Handle conversation click
const handleSelect = (id: number) => {
  emit('select', id);
};

// Handle delete with confirmation
const handleDelete = (event: MouseEvent, id: number) => {
  event.stopPropagation();
  if (window.confirm('Delete this conversation? This cannot be undone.')) {
    emit('delete', id);
  }
};

// Load conversations on mount
onMounted(() => {
  loadConversations();
});
</script>

<template>
  <div class="flex flex-col h-full bg-bg-surface border-r border-border-subtle">
    <!-- Header with create button -->
    <div class="flex-shrink-0 p-4 border-b border-border-subtle">
      <button
        @click="emit('create')"
        class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-accent-primary text-white hover:bg-accent-primary-hover transition-colors font-medium"
      >
        <Plus class="w-5 h-5" />
        <span>{{ strings.chat?.newConversation || 'New Chat' }}</span>
      </button>
    </div>

    <!-- Conversation list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading state -->
      <div v-if="conversationsLoading" class="flex items-center justify-center py-8">
        <Loader2 class="w-6 h-6 animate-spin text-text-muted" />
      </div>

      <!-- Empty state -->
      <div
        v-else-if="sortedConversations.length === 0"
        class="flex flex-col items-center justify-center py-8 px-4 text-center"
      >
        <MessageSquare class="w-12 h-12 text-text-muted mb-3" />
        <p class="text-sm text-text-muted">
          {{ strings.chat?.noConversations || 'No conversations yet' }}
        </p>
        <p class="text-xs text-text-muted mt-1">
          {{ strings.chat?.startConversation || 'Start a new conversation to get started' }}
        </p>
      </div>

      <!-- Conversations -->
      <div v-else class="py-2">
        <div
          v-for="conv in sortedConversations"
          :key="conv.id"
          role="button"
          tabindex="0"
          @click="handleSelect(conv.id)"
          @keydown.enter="handleSelect(conv.id)"
          @keydown.space.prevent="handleSelect(conv.id)"
          class="group w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-bg-hover transition-colors cursor-pointer"
          :class="activeId === conv.id ? 'bg-accent-primary/10 border-l-2 border-accent-primary' : 'border-l-2 border-transparent'"
        >
          <!-- Icon -->
          <div
            class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
            :class="activeId === conv.id ? 'bg-accent-primary/20' : 'bg-bg-elevated'"
          >
            <MessageSquare
              class="w-4 h-4"
              :class="activeId === conv.id ? 'text-accent-primary' : 'text-text-muted'"
            />
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <h3
              class="text-sm font-medium truncate"
              :class="activeId === conv.id ? 'text-accent-primary' : 'text-text-primary'"
            >
              {{ conv.title }}
            </h3>
            <p class="text-xs text-text-muted mt-0.5">
              {{ formatRelativeTime(conv.updated_at) }}
              <span v-if="conv.message_count > 0" class="ml-1">
                &middot; {{ conv.message_count }} messages
              </span>
            </p>
          </div>

          <!-- Delete button (visible on hover) -->
          <button
            @click="handleDelete($event, conv.id)"
            class="flex-shrink-0 p-1.5 rounded-lg text-text-muted hover:text-status-failed hover:bg-status-failed/10 opacity-0 group-hover:opacity-100 transition-all"
            title="Delete conversation"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Footer info -->
    <div class="flex-shrink-0 p-4 border-t border-border-subtle">
      <p class="text-xs text-text-muted text-center">
        {{ poweredByText }}
      </p>
    </div>
  </div>
</template>
