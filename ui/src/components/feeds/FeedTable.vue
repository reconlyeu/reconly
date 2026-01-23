<script setup lang="ts">
import { computed, ref } from 'vue';
import { Layers, PlayCircle, Edit, Trash2, Clock, CheckCircle2 } from 'lucide-vue-next';
import BaseTable, { type TableColumn } from '@/components/common/BaseTable.vue';
import BulkActionBar from '@/components/common/BulkActionBar.vue';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import type { Feed } from '@/types/entities';
import { useConfirm } from '@/composables/useConfirm';
import cronstrue from 'cronstrue';
import { strings } from '@/i18n/en';

interface Props {
  feeds: Feed[];
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | string | null;
  runningFeeds?: Set<number>;
}

interface Emits {
  (e: 'run', feedId: number): void;
  (e: 'toggle', feedId: number, enabled: boolean): void;
  (e: 'edit', feed: Feed): void;
  (e: 'delete', feedId: number): void;
  (e: 'delete-selected', ids: number[]): void;
  (e: 'retry'): void;
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
  isError: false,
  runningFeeds: () => new Set<number>(),
});

const emit = defineEmits<Emits>();
const { confirmDelete } = useConfirm();

const tableRef = ref<InstanceType<typeof BaseTable> | null>(null);
const selectedIds = ref<number[]>([]);
const isDeleting = ref(false);

const handleSelectionChange = (ids: number[]) => {
  selectedIds.value = ids;
};

const columns = computed<TableColumn<Feed>[]>(() => [
  { key: 'name', label: strings.feeds.table.name, width: 'w-1/4' },
  { key: 'sources', label: strings.feeds.table.sources, width: 'w-20', align: 'center' as const },
  { key: 'schedule', label: strings.feeds.table.schedule, width: 'w-48' },
  { key: 'last_run', label: strings.feeds.table.lastRun, width: 'w-28' },
  { key: 'enabled', label: strings.feeds.table.status, width: 'w-24', align: 'center' as const },
  { key: 'actions', label: strings.feeds.table.actions, width: 'w-36', align: 'right' as const },
]);

const getScheduleText = (cron?: string | null) => {
  if (!cron) return strings.feeds.schedulePresets.noSchedule;
  try {
    return cronstrue.toString(cron);
  } catch {
    return cron;
  }
};

const getLastRunConfig = (lastRunAt?: string | null) => {
  if (!lastRunAt) {
    return { text: strings.feeds.status.never, icon: Clock, color: 'text-text-muted' };
  }

  const date = new Date(lastRunAt);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);

  let text = '';
  if (diffMins < 1) text = strings.time.justNow;
  else if (diffMins < 60) text = strings.time.minutesAgo.replace('{count}', String(diffMins));
  else if (diffHours < 24) text = strings.time.hoursAgo.replace('{count}', String(diffHours));
  else text = date.toLocaleDateString();

  return { text, icon: CheckCircle2, color: 'text-status-success' };
};

const isRunning = (feedId: number) => props.runningFeeds.has(feedId);

const handleRun = (feed: Feed, e: Event) => {
  e.stopPropagation();
  emit('run', feed.id);
};

const handleToggle = (feed: Feed, enabled: boolean) => {
  emit('toggle', feed.id, enabled);
};

const handleEdit = (feed: Feed, e: Event) => {
  e.stopPropagation();
  emit('edit', feed);
};

const handleDelete = (feed: Feed, e: Event) => {
  e.stopPropagation();
  if (confirmDelete(feed.name, 'feed')) {
    emit('delete', feed.id);
  }
};

const handleDeleteSelected = () => {
  if (selectedIds.value.length === 0) return;
  const message = selectedIds.value.length === 1
    ? 'this feed'
    : `${selectedIds.value.length} feeds`;
  if (confirmDelete(message, 'feed')) {
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
      :items="feeds"
      :columns="columns"
      :is-loading="isLoading"
      :is-error="isError"
      :error="error"
      entity-name="feed"
      selectable
      :skeleton-rows="4"
      @selection-change="handleSelectionChange"
      @retry="$emit('retry')"
    >
    <!-- Name Cell -->
    <template #cell-name="{ item }">
      <div class="flex items-center gap-2">
        <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent-primary/10">
          <Layers :size="14" class="text-accent-primary" :stroke-width="2" />
        </div>
        <div>
          <div class="font-medium text-text-primary">{{ item.name }}</div>
          <div v-if="item.description" class="text-xs text-text-muted truncate max-w-48">
            {{ item.description }}
          </div>
        </div>
      </div>
    </template>

    <!-- Sources Cell -->
    <template #cell-sources="{ item }">
      <div class="flex justify-center">
        <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-500/10 text-xs font-bold text-blue-400">
          {{ item.feed_sources?.length || 0 }}
        </span>
      </div>
    </template>

    <!-- Schedule Cell -->
    <template #cell-schedule="{ item }">
      <span class="text-text-secondary text-sm">
        {{ getScheduleText(item.schedule_cron) }}
      </span>
    </template>

    <!-- Last Run Cell -->
    <template #cell-last_run="{ item }">
      <div class="flex items-center gap-1.5">
        <component
          :is="getLastRunConfig(item.last_run_at).icon"
          :size="14"
          :class="getLastRunConfig(item.last_run_at).color"
          :stroke-width="2"
        />
        <span :class="getLastRunConfig(item.last_run_at).color" class="text-sm">
          {{ getLastRunConfig(item.last_run_at).text }}
        </span>
      </div>
    </template>

    <!-- Status Cell -->
    <template #cell-enabled="{ item }">
      <div class="flex justify-center" @click.stop>
        <ToggleSwitch
          :model-value="item.schedule_enabled"
          @update:model-value="(v) => handleToggle(item, v)"
          size="sm"
        />
      </div>
    </template>

    <!-- Actions Cell -->
    <template #cell-actions="{ item }">
      <div class="flex items-center justify-end gap-1">
        <button
          @click="handleRun(item, $event)"
          :disabled="isRunning(item.id)"
          class="rounded-lg p-1.5 text-status-success transition-colors hover:bg-status-success/10 disabled:opacity-50 disabled:cursor-not-allowed"
          :title="isRunning(item.id) ? strings.feeds.running : strings.feeds.runNow"
        >
          <PlayCircle
            :size="16"
            :stroke-width="2"
            :class="isRunning(item.id) ? 'animate-spin' : ''"
          />
        </button>
        <button
          @click="handleEdit(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-bg-hover hover:text-accent-primary"
          :title="strings.feeds.actions.editFeed"
        >
          <Edit :size="16" :stroke-width="2" />
        </button>
        <button
          @click="handleDelete(item, $event)"
          class="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-status-failed/10 hover:text-status-failed"
          :title="strings.feeds.actions.deleteFeed"
        >
          <Trash2 :size="16" :stroke-width="2" />
        </button>
      </div>
    </template>
    </BaseTable>

    <!-- Bulk Action Bar -->
    <BulkActionBar
      :count="selectedIds.length"
      entity-name="feed"
      :is-deleting="isDeleting"
      @deselect-all="handleDeselectAll"
      @delete="handleDeleteSelected"
    />
  </div>
</template>
