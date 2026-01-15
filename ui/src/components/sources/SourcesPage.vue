<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { strings } from '@/i18n/en';
import { sourcesApi } from '@/services/api';
import { useSourcesStore } from '@/stores/sources';
import SourceList from './SourceList.vue';
import SourceTable from './SourceTable.vue';
import SourceForm from './SourceForm.vue';
import ViewModeToggle from '@/components/common/ViewModeToggle.vue';
import { useViewMode } from '@/composables/useViewMode';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';
import type { Source } from '@/types/entities';
import { Plus, CheckCircle, AlertCircle } from 'lucide-vue-next';

// View mode state
const { viewMode, isCardView, isTableView } = useViewMode('sources');
const queryClient = useQueryClient();
const sourcesStore = useSourcesStore();
const toast = useToast();
const { confirmDelete } = useConfirm();

const activeType = ref('all');
const isModalOpen = ref(false);
const editingSource = ref<Source | null>(null);
const sourceTableRef = ref<InstanceType<typeof SourceTable> | null>(null);

// OAuth callback message state
const oauthMessage = ref<{ type: 'success' | 'error'; message: string } | null>(null);

// Handle OAuth callback parameters from URL
onMounted(() => {
  const urlParams = new URLSearchParams(window.location.search);

  // Check for OAuth success
  if (urlParams.get('oauth_success') === 'true') {
    const provider = urlParams.get('oauth_provider') || 'email';
    oauthMessage.value = {
      type: 'success',
      message: `Successfully connected to ${provider.charAt(0).toUpperCase() + provider.slice(1)}. Your email source is now active.`
    };
    toast.success(oauthMessage.value.message);
    // Clean up URL parameters
    window.history.replaceState({}, '', window.location.pathname);
  }

  // Check for OAuth error
  const oauthError = urlParams.get('oauth_error');
  if (oauthError) {
    const errorDescription = urlParams.get('oauth_error_description') || 'Authentication failed';
    oauthMessage.value = {
      type: 'error',
      message: `OAuth Error: ${decodeURIComponent(errorDescription)}`
    };
    toast.error(oauthMessage.value.message);
    // Clean up URL parameters
    window.history.replaceState({}, '', window.location.pathname);
  }

  // Auto-dismiss message after 10 seconds
  if (oauthMessage.value) {
    setTimeout(() => {
      oauthMessage.value = null;
    }, 10000);
  }
});

// Fetch sources for table view
const {
  data: sourcesData,
  isLoading: isSourcesLoading,
  isError: isSourcesError,
  error: sourcesError,
  refetch: refetchSources,
} = useQuery({
  queryKey: ['sources', activeType],
  queryFn: async () => {
    const type = activeType.value === 'all' ? undefined : activeType.value;
    const result = await sourcesApi.list(type);
    sourcesStore.setSources(result);
    return result;
  },
  staleTime: 30000,
  refetchInterval: 30000,
  enabled: isTableView,
});

const sources = computed(() => sourcesData.value || []);

// Toggle mutation for table view
const toggleMutation = useMutation({
  mutationFn: async ({ sourceId, enabled }: { sourceId: number; enabled: boolean }) => {
    return await sourcesApi.update(sourceId, { enabled });
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
  },
});

// Delete mutation for table view
const deleteMutation = useMutation({
  mutationFn: async (sourceId: number) => {
    return await sourcesApi.delete(sourceId);
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
    toast.success('Source deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete source');
  },
});

// Batch delete mutation
const batchDeleteMutation = useMutation({
  mutationFn: (ids: number[]) => sourcesApi.batchDelete(ids),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
    sourceTableRef.value?.clearSelection();
    toast.success('Sources deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete sources');
  },
});

const handleToggle = (sourceId: number, enabled: boolean) => {
  toggleMutation.mutate({ sourceId, enabled });
};

const handleDelete = (sourceId: number) => {
  const source = sources.value?.find(s => s.id === sourceId);
  const sourceName = source?.name || 'this source';
  if (confirmDelete(sourceName, 'source')) {
    deleteMutation.mutate(sourceId);
  }
};

const handleBatchDelete = (ids: number[]) => {
  batchDeleteMutation.mutate(ids);
};

const openCreateModal = () => {
  editingSource.value = null;
  isModalOpen.value = true;
};

const openEditModal = (source: Source) => {
  editingSource.value = source;
  isModalOpen.value = true;
};

const closeModal = () => {
  isModalOpen.value = false;
  editingSource.value = null;
};

const handleSuccess = () => {
  // Modal will close automatically, could add toast notification here
  
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.sources.title }}</h1>
        <p class="mt-1 text-sm text-text-secondary">
          Manage content sources (RSS, YouTube, websites, blogs)
        </p>
      </div>
      <div class="flex items-center gap-3">
        <ViewModeToggle v-model="viewMode" />
        <button
          @click="openCreateModal"
          class="group flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 font-medium text-white transition-all hover:bg-accent-primary-hover hover:shadow-lg hover:shadow-accent-primary/20"
        >
          <Plus :size="18" class="transition-transform group-hover:rotate-90" />
          {{ strings.sources.addSource }}
        </button>
      </div>
    </div>

    <!-- OAuth Callback Message Banner -->
    <Transition name="banner">
      <div
        v-if="oauthMessage"
        class="mb-6 flex items-center gap-3 rounded-lg border p-4"
        :class="oauthMessage.type === 'success'
          ? 'border-status-success/30 bg-status-success/10'
          : 'border-status-failed/30 bg-status-failed/10'"
      >
        <CheckCircle
          v-if="oauthMessage.type === 'success'"
          :size="20"
          class="flex-shrink-0 text-status-success"
        />
        <AlertCircle
          v-else
          :size="20"
          class="flex-shrink-0 text-status-failed"
        />
        <span
          class="flex-1 text-sm"
          :class="oauthMessage.type === 'success' ? 'text-status-success' : 'text-status-failed'"
        >
          {{ oauthMessage.message }}
        </span>
        <button
          @click="oauthMessage = null"
          class="rounded p-1 transition-colors hover:bg-white/10"
          :class="oauthMessage.type === 'success' ? 'text-status-success' : 'text-status-failed'"
        >
          &times;
        </button>
      </div>
    </Transition>

    <!-- Type filter tabs -->
    <div class="mb-6 flex gap-2 border-b border-border-subtle">
      <button
        v-for="type in ['all', 'rss', 'youtube', 'website', 'blog', 'imap', 'agent']"
        :key="type"
        @click="activeType = type"
        class="border-b-2 px-4 py-3 text-sm font-medium transition-all"
        :class="
          activeType === type
            ? 'border-accent-primary text-accent-primary'
            : 'border-transparent text-text-muted hover:text-text-primary'
        "
      >
        {{ strings.sources.types[type as keyof typeof strings.sources.types] || type.toUpperCase() }}
      </button>
    </div>

    <!-- Source List (Card View) -->
    <div v-if="isCardView">
      <SourceList :filter-type="activeType" @edit="openEditModal" />
    </div>

    <!-- Source Table (Table View) -->
    <div v-else>
      <SourceTable
        ref="sourceTableRef"
        :sources="sources"
        :is-loading="isSourcesLoading"
        :is-error="isSourcesError"
        :error="sourcesError"
        @toggle="handleToggle"
        @edit="openEditModal"
        @delete="handleDelete"
        @delete-selected="handleBatchDelete"
        @retry="refetchSources"
      />
    </div>

    <!-- Create/Edit Modal -->
    <SourceForm
      :is-open="isModalOpen"
      :source="editingSource"
      @close="closeModal"
      @success="handleSuccess"
    />
  </div>
</template>

<style scoped>
/* Banner transition */
.banner-enter-active,
.banner-leave-active {
  transition: all 0.3s ease;
}

.banner-enter-from,
.banner-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
