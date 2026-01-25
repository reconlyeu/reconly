<script setup lang="ts">
/**
 * List component for displaying and managing email IMAP connections.
 * Uses TanStack Query for data fetching and mutations.
 * Provides grid layout for connection cards with empty state handling.
 */
import { ref, computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { Plus, Loader2, MailPlus, AlertTriangle } from 'lucide-vue-next';
import { connectionsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import { strings } from '@/i18n/en';
import type { Connection } from '@/types/entities';
import ConnectionCard from './ConnectionCard.vue';
import ConnectionModal from './ConnectionModal.vue';

const toast = useToast();
const queryClient = useQueryClient();

// Query connections
const { data: connectionsData, isLoading, error } = useQuery({
  queryKey: ['connections', 'email_imap'],
  queryFn: () => connectionsApi.list('email_imap'),
  staleTime: 30000,
});

const connections = computed(() => connectionsData.value?.items || []);

// Modal state
const isModalOpen = ref(false);
const editingConnection = ref<Connection | null>(null);

// Testing state (track which connection is being tested)
const testingConnectionId = ref<number | null>(null);

// Delete mutation
const deleteMutation = useMutation({
  mutationFn: (id: number) => connectionsApi.delete(id, false),
  onSuccess: () => {
    toast.success(strings.settings.email.connections.deleteSuccess);
    queryClient.invalidateQueries({ queryKey: ['connections'] });
  },
  onError: (error: any) => {
    toast.error(error.detail || strings.settings.email.connections.deleteFailed);
  },
});

// Test mutation
const testMutation = useMutation({
  mutationFn: (id: number) => connectionsApi.test(id),
  onSuccess: (result) => {
    if (result.success) {
      toast.success(strings.settings.email.connections.testSuccess);
    } else {
      toast.error(result.message || strings.settings.email.connections.testFailed);
    }
    // Invalidate to refresh health status
    queryClient.invalidateQueries({ queryKey: ['connections'] });
  },
  onError: (error: any) => {
    toast.error(error.detail || strings.settings.email.connections.testFailed);
  },
  onSettled: () => {
    testingConnectionId.value = null;
  },
});

// Handlers
function handleAddConnection() {
  editingConnection.value = null;
  isModalOpen.value = true;
}

function handleEditConnection(connection: Connection) {
  editingConnection.value = connection;
  isModalOpen.value = true;
}

function handleTestConnection(connection: Connection) {
  testingConnectionId.value = connection.id;
  testMutation.mutate(connection.id);
}

function handleDeleteConnection(connection: Connection) {
  // Show confirmation if connection is in use
  const message = connection.source_count > 0
    ? strings.settings.email.connections.deleteWarning.replace('{count}', String(connection.source_count))
    : strings.settings.email.connections.confirmDelete;

  if (confirm(message)) {
    deleteMutation.mutate(connection.id);
  }
}

function handleCloseModal() {
  isModalOpen.value = false;
  editingConnection.value = null;
}
</script>

<template>
  <div class="space-y-4">
    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <Loader2 :size="32" class="animate-spin text-accent-primary" />
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
      <AlertTriangle :size="32" class="mx-auto mb-3 text-red-400" />
      <p class="text-sm text-red-400">{{ strings.common.errorState.loadFailed.replace('{entity}', 'connections') }}</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="connections.length === 0" class="rounded-2xl border border-border-subtle bg-bg-surface/50 p-8 text-center">
      <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-primary/10">
        <MailPlus :size="28" class="text-accent-primary" />
      </div>
      <h3 class="mb-2 text-lg font-semibold text-text-primary">
        {{ strings.settings.email.connections.empty }}
      </h3>
      <p class="mb-6 text-sm text-text-muted">
        {{ strings.settings.email.connections.emptyDescription }}
      </p>
      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-primary/90"
        @click="handleAddConnection"
      >
        <Plus :size="18" />
        {{ strings.settings.email.connections.addConnection }}
      </button>
    </div>

    <!-- Connection cards grid -->
    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ConnectionCard
          v-for="connection in connections"
          :key="connection.id"
          :connection="connection"
          :is-testing="testingConnectionId === connection.id"
          @edit="handleEditConnection"
          @test="handleTestConnection"
          @delete="handleDeleteConnection"
        />
      </div>

      <!-- Add connection button -->
      <div class="pt-2">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-dashed border-border-subtle bg-bg-surface/50 px-4 py-2.5 text-sm font-medium text-text-secondary transition-colors hover:border-accent-primary hover:bg-accent-primary/5 hover:text-accent-primary"
          @click="handleAddConnection"
        >
          <Plus :size="18" />
          {{ strings.settings.email.connections.addConnection }}
        </button>
      </div>
    </template>

    <!-- Connection Modal -->
    <ConnectionModal
      :is-open="isModalOpen"
      :connection="editingConnection"
      @close="handleCloseModal"
    />
  </div>
</template>
