<script setup lang="ts">
import { computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { sourcesApi } from '@/services/api';
import { useSourcesStore } from '@/stores/sources';
import BaseList from '@/components/common/BaseList.vue';
import SourceCard from './SourceCard.vue';
import type { Source } from '@/types/entities';
import { Rss } from 'lucide-vue-next';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';

interface Props {
  filterType?: string;
}

interface Emits {
  (e: 'edit', source: Source): void;
}

const props = withDefaults(defineProps<Props>(), {
  filterType: 'all',
});

const emit = defineEmits<Emits>();
const queryClient = useQueryClient();
const toast = useToast();
const { confirmDelete } = useConfirm();

// Reactive query key for filter changes
const queryKey = computed(() => ['sources', props.filterType]);

// Fetch sources with optional type filter
const { data: sources, isLoading, isError, error, refetch } = useQuery({
  queryKey,
  queryFn: async () => {
    const type = props.filterType === 'all' ? undefined : props.filterType;
    const result = await sourcesApi.list(type);
    // Access store inside queryFn to ensure Pinia is initialized
    const sourcesStore = useSourcesStore();
    sourcesStore.setSources(result);
    return result;
  },
  staleTime: 30000, // 30 seconds
  refetchInterval: 30000,
});

// Toggle source enabled status
const toggleMutation = useMutation({
  mutationFn: async ({ sourceId, enabled }: { sourceId: number; enabled: boolean }) => {
    return await sourcesApi.update(sourceId, { enabled });
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });
  },
});

// Delete source
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

const sourcesList = computed(() => sources.value || []);

const emptyMessage = computed(() => {
  if (props.filterType === 'all') {
    return 'No sources yet. Create your first source to get started.';
  }
  return `No ${props.filterType} sources found.`;
});

const handleToggle = (sourceId: number, enabled: boolean) => {
  toggleMutation.mutate({ sourceId, enabled });
};

const handleEdit = (source: Source) => {
  emit('edit', source);
};

const handleDelete = (sourceId: number) => {
  // Find source name for confirmation
  const source = sources.value?.find(s => s.id === sourceId);
  const sourceName = source?.name || 'this source';

  if (confirmDelete(sourceName, 'source')) {
    deleteMutation.mutate(sourceId);
  }
};
</script>

<template>
  <BaseList
    :is-loading="isLoading"
    :is-error="isError"
    :error="error"
    :items="sourcesList"
    entity-name="source"
    :grid-cols="3"
    :skeleton-count="6"
    skeleton-height="h-64"
    empty-title="No sources found"
    :empty-message="emptyMessage"
    :empty-icon="Rss"
    @retry="refetch"
  >
    <template #default>
      <SourceCard
        v-for="(source, index) in sourcesList"
        :key="source.id"
        :source="source"
        :style="{ animationDelay: `${index * 50}ms` }"
        @toggle="handleToggle"
        @edit="handleEdit"
        @delete="handleDelete"
      />
    </template>
  </BaseList>
</template>
