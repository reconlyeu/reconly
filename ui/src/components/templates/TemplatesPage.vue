<script setup lang="ts">
import { ref, computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { strings } from '@/i18n/en';
import { promptTemplatesApi, reportTemplatesApi } from '@/services/api';
import { useTemplatesStore } from '@/stores/templates';
import PromptTemplateList from './PromptTemplateList.vue';
import ReportTemplateList from './ReportTemplateList.vue';
import TemplateTable from './TemplateTable.vue';
import PromptTemplateForm from './PromptTemplateForm.vue';
import ReportTemplateForm from './ReportTemplateForm.vue';
import ViewModeToggle from '@/components/common/ViewModeToggle.vue';
import { useViewMode } from '@/composables/useViewMode';
import { useToast } from '@/composables/useToast';
import { useConfirm } from '@/composables/useConfirm';
import type { PromptTemplate, ReportTemplate } from '@/types/entities';

// View mode state
const { viewMode, isCardView, isTableView } = useViewMode('templates');
const queryClient = useQueryClient();
const toast = useToast();
const { confirmDelete } = useConfirm();

type TabType = 'prompt' | 'report';

const activeTab = ref<TabType>('prompt');
const isPromptModalOpen = ref(false);
const isReportModalOpen = ref(false);
const editingPromptTemplate = ref<PromptTemplate | null>(null);
const editingReportTemplate = ref<ReportTemplate | null>(null);
const promptTableRef = ref<InstanceType<typeof TemplateTable> | null>(null);
const reportTableRef = ref<InstanceType<typeof TemplateTable> | null>(null);

// Fetch prompt templates for table view
const {
  data: promptTemplatesData,
  isLoading: isPromptLoading,
  isError: isPromptError,
  error: promptError,
  refetch: refetchPromptTemplates,
} = useQuery({
  queryKey: ['prompt-templates'],
  queryFn: async () => {
    const result = await promptTemplatesApi.list();
    // Access store inside queryFn to ensure Pinia is initialized
    const templatesStore = useTemplatesStore();
    templatesStore.setPromptTemplates(result);
    return result;
  },
  staleTime: 60000,
  refetchInterval: 60000,
  enabled: computed(() => isTableView.value && activeTab.value === 'prompt'),
});

// Fetch report templates for table view
const {
  data: reportTemplatesData,
  isLoading: isReportLoading,
  isError: isReportError,
  error: reportError,
  refetch: refetchReportTemplates,
} = useQuery({
  queryKey: ['report-templates'],
  queryFn: async () => {
    const result = await reportTemplatesApi.list();
    // Access store inside queryFn to ensure Pinia is initialized
    const templatesStore = useTemplatesStore();
    templatesStore.setReportTemplates(result);
    return result;
  },
  staleTime: 60000,
  refetchInterval: 60000,
  enabled: computed(() => isTableView.value && activeTab.value === 'report'),
});

const promptTemplates = computed(() => promptTemplatesData.value || []);
const reportTemplates = computed(() => reportTemplatesData.value || []);

// Prompt template mutations
const togglePromptMutation = useMutation({
  mutationFn: (templateId: number) => promptTemplatesApi.toggle(templateId),
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    toast.success(`Template ${data.is_active ? 'activated' : 'deactivated'}`);
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to toggle template');
  },
});

const deletePromptMutation = useMutation({
  mutationFn: (templateId: number) => promptTemplatesApi.delete(templateId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    toast.success('Prompt template deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete template');
  },
});

const batchDeletePromptMutation = useMutation({
  mutationFn: (ids: number[]) => promptTemplatesApi.batchDelete(ids),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    promptTableRef.value?.clearSelection();
    toast.success('Templates deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete templates');
  },
});

// Report template mutations
const toggleReportMutation = useMutation({
  mutationFn: (templateId: number) => reportTemplatesApi.toggle(templateId),
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    toast.success(`Template ${data.is_active ? 'activated' : 'deactivated'}`);
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to toggle template');
  },
});

const deleteReportMutation = useMutation({
  mutationFn: (templateId: number) => reportTemplatesApi.delete(templateId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    toast.success('Report template deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete template');
  },
});

const batchDeleteReportMutation = useMutation({
  mutationFn: (ids: number[]) => reportTemplatesApi.batchDelete(ids),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    reportTableRef.value?.clearSelection();
    toast.success('Templates deleted successfully');
  },
  onError: (error: any) => {
    toast.error(error.response?.data?.detail || 'Failed to delete templates');
  },
});

// Handler functions for table view
const handleTogglePrompt = (templateId: number) => {
  togglePromptMutation.mutate(templateId);
};

const handleDeletePrompt = (templateId: number) => {
  const template = promptTemplates.value?.find(t => t.id === templateId);
  const templateName = template?.name || 'this template';
  if (confirmDelete(templateName, 'prompt template')) {
    deletePromptMutation.mutate(templateId);
  }
};

const handleBatchDeletePrompt = (ids: number[]) => {
  batchDeletePromptMutation.mutate(ids);
};

const handleToggleReport = (templateId: number) => {
  toggleReportMutation.mutate(templateId);
};

const handleDeleteReport = (templateId: number) => {
  const template = reportTemplates.value?.find(t => t.id === templateId);
  const templateName = template?.name || 'this template';
  if (confirmDelete(templateName, 'report template')) {
    deleteReportMutation.mutate(templateId);
  }
};

const handleBatchDeleteReport = (ids: number[]) => {
  batchDeleteReportMutation.mutate(ids);
};

// Prompt Template Handlers
const openCreatePromptModal = () => {
  editingPromptTemplate.value = null;
  isPromptModalOpen.value = true;
};

const openEditPromptModal = (template: PromptTemplate) => {
  editingPromptTemplate.value = template;
  isPromptModalOpen.value = true;
};

const closePromptModal = () => {
  isPromptModalOpen.value = false;
  editingPromptTemplate.value = null;
};

// Report Template Handlers
const openCreateReportModal = () => {
  editingReportTemplate.value = null;
  isReportModalOpen.value = true;
};

const openEditReportModal = (template: ReportTemplate) => {
  editingReportTemplate.value = template;
  isReportModalOpen.value = true;
};

const closeReportModal = () => {
  isReportModalOpen.value = false;
  editingReportTemplate.value = null;
};

const handleSuccess = () => {
  
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.templates.title }}</h1>
        <p class="mt-1 text-sm text-text-secondary">
          {{ strings.pageSubtitles.templates }}
        </p>
      </div>
      <ViewModeToggle v-model="viewMode" />
    </div>

    <!-- Tabs -->
    <div class="mb-6 flex gap-4 border-b border-border-subtle">
      <button
        @click="activeTab = 'prompt'"
        class="border-b-2 px-4 py-3 font-medium transition-all"
        :class="
          activeTab === 'prompt'
            ? 'border-accent-primary text-accent-primary'
            : 'border-transparent text-text-muted hover:text-text-primary'
        "
      >
        {{ strings.templates.tabs.prompt }}
      </button>
      <button
        @click="activeTab = 'report'"
        class="border-b-2 px-4 py-3 font-medium transition-all"
        :class="
          activeTab === 'report'
            ? 'border-accent-primary text-accent-primary'
            : 'border-transparent text-text-muted hover:text-text-primary'
        "
      >
        {{ strings.templates.tabs.report }}
      </button>
    </div>

    <!-- Tab Content (Card View) -->
    <div v-if="isCardView">
      <PromptTemplateList
        v-if="activeTab === 'prompt'"
        @edit="openEditPromptModal"
        @create="openCreatePromptModal"
      />
      <ReportTemplateList
        v-if="activeTab === 'report'"
        @edit="openEditReportModal"
        @create="openCreateReportModal"
      />
    </div>

    <!-- Tab Content (Table View) -->
    <div v-else>
      <TemplateTable
        v-if="activeTab === 'prompt'"
        ref="promptTableRef"
        :templates="promptTemplates"
        type="prompt"
        :is-loading="isPromptLoading"
        :is-error="isPromptError"
        :error="promptError"
        @toggle="handleTogglePrompt"
        @edit="openEditPromptModal"
        @delete="handleDeletePrompt"
        @delete-selected="handleBatchDeletePrompt"
        @retry="refetchPromptTemplates"
      />
      <TemplateTable
        v-if="activeTab === 'report'"
        ref="reportTableRef"
        :templates="reportTemplates"
        type="report"
        :is-loading="isReportLoading"
        :is-error="isReportError"
        :error="reportError"
        @toggle="handleToggleReport"
        @edit="openEditReportModal"
        @delete="handleDeleteReport"
        @delete-selected="handleBatchDeleteReport"
        @retry="refetchReportTemplates"
      />
    </div>

    <!-- Modals - only mount when open to avoid Teleport conflicts -->
    <PromptTemplateForm
      v-if="isPromptModalOpen"
      :is-open="true"
      :template="editingPromptTemplate"
      @close="closePromptModal"
      @success="handleSuccess"
    />
    <ReportTemplateForm
      v-if="isReportModalOpen"
      :is-open="true"
      :template="editingReportTemplate"
      @close="closeReportModal"
      @success="handleSuccess"
    />
  </div>
</template>

