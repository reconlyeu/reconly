<script setup lang="ts">
import { computed, ref } from 'vue';
import { Languages, Code, Shield, FileText, Edit, Trash2 } from 'lucide-vue-next';
import BaseTable, { type TableColumn } from '@/components/common/BaseTable.vue';
import BulkActionBar from '@/components/common/BulkActionBar.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import type { PromptTemplate, ReportTemplate } from '@/types/entities';
import { useConfirm } from '@/composables/useConfirm';

type Template = PromptTemplate | ReportTemplate;

interface Props {
  templates: Template[];
  type: 'prompt' | 'report';
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | string | null;
}

interface Emits {
  (e: 'toggle', templateId: number): void;
  (e: 'edit', template: Template): void;
  (e: 'delete', templateId: number): void;
  (e: 'delete-selected', ids: number[]): void;
  (e: 'retry'): void;
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
  isError: false,
});

const emit = defineEmits<Emits>();
const { confirmDelete } = useConfirm();

const tableRef = ref<InstanceType<typeof BaseTable> | null>(null);
const selectedIds = ref<number[]>([]);
const isDeleting = ref(false);

const handleSelectionChange = (ids: number[]) => {
  selectedIds.value = ids;
};

const columns = computed<TableColumn<Template>[]>(() => [
  { key: 'name', label: 'Name', width: 'w-1/4' },
  { key: 'category', label: 'Category', width: 'w-24' },
  { key: 'meta', label: props.type === 'prompt' ? 'Language' : 'Format', width: 'w-28' },
  { key: 'description', label: 'Description', width: 'w-1/3' },
  { key: 'is_active', label: 'Status', width: 'w-24', align: 'center' as const },
  { key: 'actions', label: 'Actions', width: 'w-28', align: 'right' as const },
]);

const typeConfig = computed(() => {
  if (props.type === 'prompt') {
    return {
      icon: Languages,
      label: 'Prompt',
      color: 'text-purple-400',
      bgColor: 'bg-purple-400/10',
    };
  }
  return {
    icon: Code,
    label: 'Report',
    color: 'text-orange-400',
    bgColor: 'bg-orange-400/10',
  };
});

const getCategoryConfig = (isSystem: boolean) => {
  if (isSystem) {
    return {
      label: 'Built-in',
      color: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      icon: Shield,
    };
  }
  return {
    label: 'Custom',
    color: 'bg-green-500/10 text-green-400 border-green-500/20',
    icon: FileText,
  };
};

const getMetaText = (template: Template) => {
  if (props.type === 'prompt') {
    const pt = template as PromptTemplate;
    return pt.language || 'English';
  }
  const rt = template as ReportTemplate;
  return rt.format || 'markdown';
};

const handleToggle = (template: Template) => {
  emit('toggle', template.id);
};

const handleEdit = (template: Template, e: Event) => {
  e.stopPropagation();
  emit('edit', template);
};

const handleDelete = (template: Template, e: Event) => {
  e.stopPropagation();
  const templateType = props.type === 'prompt' ? 'prompt template' : 'report template';
  if (confirmDelete(template.name, templateType)) {
    emit('delete', template.id);
  }
};

const handleDeleteSelected = () => {
  if (selectedIds.value.length === 0) return;
  const templateType = props.type === 'prompt' ? 'prompt template' : 'report template';
  const message = selectedIds.value.length === 1
    ? `this ${templateType}`
    : `${selectedIds.value.length} ${templateType}s`;
  if (confirmDelete(message, templateType)) {
    isDeleting.value = true;
    emit('delete-selected', selectedIds.value);
  }
};

const handleDeselectAll = () => {
  tableRef.value?.clearSelection();
  selectedIds.value = [];
};

// Expose method to clear selection from parent
defineExpose({
  clearSelection: () => {
    tableRef.value?.clearSelection();
    selectedIds.value = [];
    isDeleting.value = false;
  },
  getSelectedIds: () => tableRef.value?.getSelectedIds() ?? [],
});
</script>

<template>
  <div>
    <BaseTable
      ref="tableRef"
      :items="templates"
      :columns="columns"
      :is-loading="isLoading"
      :is-error="isError"
      :error="error"
      :entity-name="type === 'prompt' ? 'prompt template' : 'report template'"
      selectable
      :skeleton-rows="4"
      @selection-change="handleSelectionChange"
      @retry="$emit('retry')"
    >
    <!-- Name Cell -->
    <template #cell-name="{ item }">
      <div class="flex items-center gap-2">
        <div
          class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
          :class="typeConfig.bgColor"
        >
          <component
            :is="typeConfig.icon"
            :size="14"
            :class="typeConfig.color"
            :stroke-width="2"
          />
        </div>
        <span class="font-medium text-text-primary">{{ item.name }}</span>
      </div>
    </template>

    <!-- Category Cell -->
    <template #cell-category="{ item }">
      <span
        class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium"
        :class="getCategoryConfig(item.is_system).color"
      >
        <component :is="getCategoryConfig(item.is_system).icon" :size="12" :stroke-width="2" />
        {{ getCategoryConfig(item.is_system).label }}
      </span>
    </template>

    <!-- Meta Cell (Language/Format) -->
    <template #cell-meta="{ item }">
      <span class="rounded-full bg-bg-hover px-2.5 py-1 text-xs font-medium text-text-secondary capitalize">
        {{ getMetaText(item) }}
      </span>
    </template>

    <!-- Description Cell -->
    <template #cell-description="{ item }">
      <span v-if="item.description" class="text-text-secondary text-sm line-clamp-1">
        {{ item.description }}
      </span>
      <span v-else class="text-text-muted">-</span>
    </template>

    <!-- Status Cell -->
    <template #cell-is_active="{ item }">
      <div class="flex justify-center" @click.stop>
        <ToggleSwitch
          :model-value="item.is_active"
          @update:model-value="() => handleToggle(item)"
          size="sm"
        />
      </div>
    </template>

    <!-- Actions Cell -->
    <template #cell-actions="{ item }">
      <div class="flex items-center justify-end gap-1">
        <button
          @click="handleEdit(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-bg-hover hover:text-accent-primary"
          title="Edit template"
        >
          <Edit :size="16" :stroke-width="2" />
        </button>
        <button
          @click="handleDelete(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-status-failed/10 hover:text-status-failed"
          title="Delete template"
        >
          <Trash2 :size="16" :stroke-width="2" />
        </button>
      </div>
    </template>
    </BaseTable>

    <!-- Bulk Action Bar -->
    <BulkActionBar
      :count="selectedIds.length"
      :entity-name="type === 'prompt' ? 'prompt template' : 'report template'"
      :is-deleting="isDeleting"
      @deselect-all="handleDeselectAll"
      @delete="handleDeleteSelected"
    />
  </div>
</template>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
