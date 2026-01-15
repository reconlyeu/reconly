<script setup lang="ts">
import { computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { promptTemplatesApi } from '@/services/api';
import { useTemplatesStore } from '@/stores/templates';
import ErrorState from '@/components/common/ErrorState.vue';
import EmptyState from '@/components/common/EmptyState.vue';
import TemplateCard from './TemplateCard.vue';
import type { PromptTemplate } from '@/types/entities';
import { Plus, FileCode } from 'lucide-vue-next';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';

interface Emits {
  (e: 'edit', template: PromptTemplate): void;
  (e: 'create'): void;
}

const emit = defineEmits<Emits>();
const queryClient = useQueryClient();
const toast = useToast();
const { confirmDelete } = useConfirm();

// Fetch prompt templates
const { data: templates, isLoading, isError, error, refetch } = useQuery({
  queryKey: ['prompt-templates'],
  queryFn: async () => {
    const result = await promptTemplatesApi.list();
    // Access store inside queryFn to ensure Pinia is initialized
    const templatesStore = useTemplatesStore();
    templatesStore.setPromptTemplates(result);
    return result;
  },
  staleTime: 60000, // 1 minute
  refetchInterval: 60000,
});

// Delete mutation
const deleteMutation = useMutation({
  mutationFn: async (templateId: number) => {
    return await promptTemplatesApi.delete(templateId);
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    toast.success('Prompt template deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete prompt template');
  },
});

// Toggle mutation
const toggleMutation = useMutation({
  mutationFn: async (templateId: number) => {
    return await promptTemplatesApi.toggle(templateId);
  },
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    toast.success(`Template ${data.is_active ? 'activated' : 'deactivated'}`);
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to toggle template');
  },
});

const systemTemplates = computed(() => {
  return templates.value?.filter(t => t.is_system) || [];
});

const userTemplates = computed(() => {
  return templates.value?.filter(t => !t.is_system) || [];
});

const handleEdit = (template: PromptTemplate) => {
  emit('edit', template);
};

const handleToggle = (templateId: number) => {
  toggleMutation.mutate(templateId);
};

const handleDelete = (templateId: number) => {
  const template = templates.value?.find(t => t.id === templateId);
  const templateName = template?.name || 'this template';

  if (confirmDelete(templateName, 'prompt template')) {
    deleteMutation.mutate(templateId);
  }
};
</script>

<template>
  <div class="space-y-8">
    <!-- Loading State -->
    <div v-if="isLoading">
      <div class="mb-6">
        <div class="mb-4 h-6 w-32 animate-pulse rounded bg-bg-hover" />
        <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="i in 3"
            :key="i"
            class="h-64 animate-pulse rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated/50 to-bg-surface/30"
          />
        </div>
      </div>
    </div>

    <!-- Error State -->
    <ErrorState
      v-else-if="isError"
      entity-name="prompt templates"
      :error="error"
      show-retry
      @retry="refetch"
    />

    <!-- Content -->
    <template v-else>
      <!-- System Templates -->
      <div>
        <h2 class="mb-4 text-lg font-semibold text-text-primary">System Templates</h2>
        <div v-if="systemTemplates.length > 0" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <TemplateCard
            v-for="(template, index) in systemTemplates"
            :key="template.id"
            :template="template"
            type="prompt"
            :style="{ animationDelay: `${index * 50}ms` }"
            @toggle="handleToggle"
            @edit="handleEdit"
            @delete="handleDelete"
          />
        </div>
        <EmptyState
          v-else
          title="No system templates"
          message="System templates will be available after initialization."
          :icon="FileCode"
        />
      </div>

      <!-- User Templates -->
      <div>
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-text-primary">User Templates</h2>
          <button
            @click="emit('create')"
            class="group flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-all hover:bg-accent-primary-hover hover:shadow-lg hover:shadow-accent-primary/20"
          >
            <Plus :size="16" class="transition-transform group-hover:rotate-90" />
            Create Template
          </button>
        </div>

        <div v-if="userTemplates.length > 0" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <TemplateCard
            v-for="(template, index) in userTemplates"
            :key="template.id"
            :template="template"
            type="prompt"
            :style="{ animationDelay: `${(systemTemplates.length + index) * 50}ms` }"
            @toggle="handleToggle"
            @edit="handleEdit"
            @delete="handleDelete"
          />
        </div>
        <EmptyState
          v-else
          title="No user templates yet"
          message="Create your first prompt template to customize content summarization"
          :icon="Plus"
        >
          <template #action>
            <button
              @click="emit('create')"
              class="rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white transition-all hover:bg-accent-primary-hover"
            >
              Create Template
            </button>
          </template>
        </EmptyState>
      </div>
    </template>
  </div>
</template>
