<script setup lang="ts">
import { computed, ref } from 'vue';
import { Rss, Youtube, Globe, BookOpen, Edit, Trash2, ExternalLink, Mail, Bot, RefreshCw } from 'lucide-vue-next';
import BaseTable, { type TableColumn } from '@/components/common/BaseTable.vue';
import BulkActionBar from '@/components/common/BulkActionBar.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import type { Source } from '@/types/entities';
import { useConfirm } from '@/composables/useConfirm';
import {
  getAuthStatusConfig,
  needsReauthentication,
  handleReauthenticate,
  getReauthButtonTitle,
} from '@/composables/useAuthStatus';

interface Props {
  sources: Source[];
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | string | null;
}

interface Emits {
  (e: 'toggle', sourceId: number, enabled: boolean): void;
  (e: 'edit', source: Source): void;
  (e: 'delete', sourceId: number): void;
  (e: 'delete-selected', ids: number[]): void;
  (e: 'retry'): void;
  (e: 'reauthenticate', source: Source): void;
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

const columns = computed<TableColumn<Source>[]>(() => [
  { key: 'name', label: 'Name', width: 'w-1/4' },
  { key: 'type', label: 'Type', width: 'w-28' },
  { key: 'url', label: 'URL', width: 'w-1/3' },
  { key: 'enabled', label: 'Status', width: 'w-24', align: 'center' as const },
  { key: 'actions', label: 'Actions', width: 'w-28', align: 'right' as const },
]);

const typeConfig = (type: string) => {
  const configs: Record<string, { icon: typeof Rss; label: string; color: string; bgColor: string }> = {
    rss: { icon: Rss, label: 'RSS', color: 'text-orange-400', bgColor: 'bg-orange-400/10' },
    youtube: { icon: Youtube, label: 'YouTube', color: 'text-red-500', bgColor: 'bg-red-500/10' },
    website: { icon: Globe, label: 'Website', color: 'text-blue-400', bgColor: 'bg-blue-400/10' },
    blog: { icon: BookOpen, label: 'Blog', color: 'text-green-400', bgColor: 'bg-green-400/10' },
    imap: { icon: Mail, label: 'Email', color: 'text-purple-400', bgColor: 'bg-purple-400/10' },
    agent: { icon: Bot, label: 'Agent', color: 'text-cyan-400', bgColor: 'bg-cyan-400/10' },
  };
  return configs[type] || configs.rss;
};

// Handle re-authentication for IMAP sources
const onReauthenticate = async (source: Source, e: Event) => {
  e.stopPropagation();
  const isOAuthRedirect = await handleReauthenticate(source);
  if (!isOAuthRedirect) {
    emit('reauthenticate', source);
  }
};

const handleToggle = (source: Source, enabled: boolean) => {
  emit('toggle', source.id, enabled);
};

const handleEdit = (source: Source, e: Event) => {
  e.stopPropagation();
  emit('edit', source);
};

const handleDelete = (source: Source, e: Event) => {
  e.stopPropagation();
  if (confirmDelete(source.name, 'source')) {
    emit('delete', source.id);
  }
};

const handleDeleteSelected = () => {
  if (selectedIds.value.length === 0) return;
  const message = selectedIds.value.length === 1
    ? 'this source'
    : `${selectedIds.value.length} sources`;
  if (confirmDelete(message, 'source')) {
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
      :items="sources"
      :columns="columns"
      :is-loading="isLoading"
      :is-error="isError"
      :error="error"
      entity-name="source"
      selectable
      :skeleton-rows="6"
      @selection-change="handleSelectionChange"
      @retry="$emit('retry')"
    >
    <!-- Name Cell -->
    <template #cell-name="{ item }">
      <div class="flex items-center gap-2">
        <div
          class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
          :class="typeConfig(item.type).bgColor"
        >
          <component
            :is="typeConfig(item.type).icon"
            :size="14"
            :class="typeConfig(item.type).color"
            :stroke-width="2"
          />
        </div>
        <span class="font-medium text-text-primary">{{ item.name }}</span>
      </div>
    </template>

    <!-- Type Cell -->
    <template #cell-type="{ item }">
      <span
        class="rounded-full px-2.5 py-1 text-xs font-medium"
        :class="[typeConfig(item.type).bgColor, typeConfig(item.type).color]"
      >
        {{ typeConfig(item.type).label }}
      </span>
    </template>

    <!-- URL Cell -->
    <template #cell-url="{ item }">
      <div class="flex items-center gap-1.5">
        <span class="truncate text-text-secondary" :title="item.url">
          {{ item.url }}
        </span>
        <a
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          @click.stop
          class="flex-shrink-0 text-text-muted transition-colors hover:text-accent-primary"
          title="Open URL"
        >
          <ExternalLink :size="14" :stroke-width="2" />
        </a>
      </div>
    </template>

    <!-- Status Cell -->
    <template #cell-enabled="{ item }">
      <div class="flex items-center justify-center gap-2" @click.stop>
        <!-- Auth Status Badge for IMAP -->
        <span
          v-if="item.type === 'imap' && getAuthStatusConfig(item.auth_status, true)"
          class="rounded-full px-2 py-0.5 text-xs font-medium"
          :class="[getAuthStatusConfig(item.auth_status, true)?.bgColor, getAuthStatusConfig(item.auth_status, true)?.textColor]"
        >
          {{ getAuthStatusConfig(item.auth_status, true)?.label }}
        </span>
        <ToggleSwitch
          :model-value="item.enabled"
          @update:model-value="(v) => handleToggle(item, v)"
          size="sm"
        />
      </div>
    </template>

    <!-- Actions Cell -->
    <template #cell-actions="{ item }">
      <div class="flex items-center justify-end gap-1">
        <!-- Re-authenticate button for IMAP with pending/failed auth -->
        <button
          v-if="needsReauthentication(item)"
          @click="onReauthenticate(item, $event)"
          class="rounded-lg p-1.5 transition-colors"
          :class="item.auth_status === 'pending_oauth'
            ? 'text-amber-500 hover:bg-amber-500/10'
            : 'text-status-failed hover:bg-status-failed/10'"
          :title="getReauthButtonTitle(item.auth_status)"
        >
          <RefreshCw :size="16" :stroke-width="2" />
        </button>
        <button
          @click="handleEdit(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-bg-hover hover:text-accent-primary"
          title="Edit source"
        >
          <Edit :size="16" :stroke-width="2" />
        </button>
        <button
          @click="handleDelete(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-status-failed/10 hover:text-status-failed"
          title="Delete source"
        >
          <Trash2 :size="16" :stroke-width="2" />
        </button>
      </div>
    </template>
    </BaseTable>

    <!-- Bulk Action Bar -->
    <BulkActionBar
      :count="selectedIds.length"
      entity-name="source"
      :is-deleting="isDeleting"
      @deselect-all="handleDeselectAll"
      @delete="handleDeleteSelected"
    />
  </div>
</template>
