<script setup lang="ts">
import { computed, ref } from 'vue';
import { Eye, Trash2, FileText, Tag, Download } from 'lucide-vue-next';
import BaseTable, { type TableColumn } from '@/components/common/BaseTable.vue';
import BulkActionBar from '@/components/common/BulkActionBar.vue';
import ExportDropdown from '@/components/common/ExportDropdown.vue';
import type { Digest, Exporter } from '@/types/entities';
import { useConfirm } from '@/composables/useConfirm';
import { features } from '@/config/features';

interface Props {
  digests: Digest[];
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | string | null;
}

interface Emits {
  (e: 'view', digest: Digest): void;
  (e: 'export', digest: Digest, exporter: Exporter): void;
  (e: 'export-selected', ids: number[], exporter: Exporter): void;
  (e: 'delete', digestId: number): void;
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

const columns = computed<TableColumn<Digest>[]>(() => [
  { key: 'title', label: 'Title', width: 'w-1/3' },
  { key: 'source_type', label: 'Type', width: 'w-16' },
  { key: 'provider', label: 'Provider', width: 'w-44' },
  { key: 'tags', label: 'Tags', width: 'w-40' },
  { key: 'created_at', label: 'Date', width: 'w-28' },
  { key: 'actions', label: 'Actions', width: 'w-32', align: 'right' as const },
]);

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

const handleView = (digest: Digest) => {
  emit('view', digest);
};

const handleExport = (digest: Digest, exporter: Exporter) => {
  emit('export', digest, exporter);
};

const handleExportSelected = (exporter: Exporter) => {
  if (selectedIds.value.length === 0) return;
  emit('export-selected', selectedIds.value, exporter);
};

const handleDelete = (digest: Digest, e: Event) => {
  e.stopPropagation();
  if (confirmDelete(digest.title || 'this digest', 'digest')) {
    emit('delete', digest.id);
  }
};

const handleDeleteSelected = () => {
  if (selectedIds.value.length === 0) return;
  const message = selectedIds.value.length === 1
    ? 'this digest'
    : `${selectedIds.value.length} digests`;
  if (confirmDelete(message, 'digest')) {
    isDeleting.value = true;
    emit('delete-selected', selectedIds.value);
    // Note: Parent should call clearSelection() on success
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
      :items="digests"
      :columns="columns"
      :is-loading="isLoading"
      :is-error="isError"
      :error="error"
      entity-name="digest"
      selectable
      row-clickable
      :skeleton-rows="10"
      @row-click="handleView"
      @selection-change="handleSelectionChange"
      @retry="$emit('retry')"
    >
    <!-- Title Cell -->
    <template #cell-title="{ item }">
      <div class="flex items-center gap-2">
        <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-500/10">
          <FileText :size="14" class="text-blue-400" :stroke-width="2" />
        </div>
        <span class="font-medium text-text-primary line-clamp-1">
          {{ item.title || 'Untitled' }}
        </span>
      </div>
    </template>

    <!-- Type Cell -->
    <template #cell-source_type="{ item }">
      <span class="rounded-full bg-bg-hover px-2.5 py-1 text-xs font-medium text-text-secondary capitalize">
        {{ item.source_type || 'article' }}
      </span>
    </template>

    <!-- Provider Cell -->
    <template #cell-provider="{ item }">
      <span v-if="item.provider" class="rounded-full bg-purple-500/10 px-2.5 py-1 text-xs font-medium text-purple-400">
        {{ item.provider }}
      </span>
      <span v-else class="text-text-muted">-</span>
    </template>

    <!-- Tags Cell -->
    <template #cell-tags="{ item }">
      <div v-if="item.tags && item.tags.length > 0" class="flex flex-wrap gap-1">
        <span
          v-for="tag in item.tags.slice(0, 2)"
          :key="tag"
          class="flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted"
        >
          <Tag :size="10" :stroke-width="2" />
          {{ tag }}
        </span>
        <span v-if="item.tags.length > 2" class="rounded-full bg-bg-hover px-2 py-0.5 text-xs text-text-muted">
          +{{ item.tags.length - 2 }}
        </span>
      </div>
      <span v-else class="text-text-muted">-</span>
    </template>

    <!-- Date Cell -->
    <template #cell-created_at="{ item }">
      <span class="text-text-secondary">{{ formatDate(item.created_at) }}</span>
    </template>

    <!-- Actions Cell -->
    <template #cell-actions="{ item }">
      <div class="flex items-center justify-end gap-1">
        <button
          @click.stop="handleView(item)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-bg-hover hover:text-accent-primary"
          title="View digest"
        >
          <Eye :size="16" :stroke-width="2" />
        </button>
        <ExportDropdown
          icon-only
          size="sm"
          @select="(exporter) => handleExport(item, exporter)"
        />
        <button
          @click="handleDelete(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-status-failed/10 hover:text-status-failed"
          title="Delete digest"
        >
          <Trash2 :size="16" :stroke-width="2" />
        </button>
      </div>
    </template>
    </BaseTable>

    <!-- Bulk Action Bar -->
    <BulkActionBar
      :count="selectedIds.length"
      entity-name="digest"
      :is-deleting="isDeleting"
      @deselect-all="handleDeselectAll"
      @delete="handleDeleteSelected"
    >
      <template #actions>
        <ExportDropdown
          size="sm"
          open-up
          @select="handleExportSelected"
        />
      </template>
    </BulkActionBar>
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
