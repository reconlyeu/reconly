<script setup lang="ts" generic="T extends { id: number }">
/**
 * Base table component with selection support.
 * Renders items in a table with configurable columns.
 */
import { computed, ref, watch } from 'vue';
import { useSelection } from '@/composables/useSelection';
import LoadingSkeleton from './LoadingSkeleton.vue';
import ErrorState from './ErrorState.vue';
import EmptyState from './EmptyState.vue';

export interface TableColumn<T> {
  /** Unique key for the column */
  key: string;
  /** Display label for the column header */
  label: string;
  /** Width class (e.g., 'w-48', 'w-1/4') */
  width?: string;
  /** Alignment */
  align?: 'left' | 'center' | 'right';
  /** Whether the column is sortable (future feature) */
  sortable?: boolean;
  /** Custom accessor function */
  accessor?: (item: T) => unknown;
}

interface Props {
  /** Items to render */
  items: T[];
  /** Column definitions */
  columns: TableColumn<T>[];
  /** Loading state */
  isLoading?: boolean;
  /** Error state */
  isError?: boolean;
  /** Error object or message */
  error?: Error | string | null;
  /** Entity name for messages */
  entityName?: string;
  /** Enable row selection with checkboxes */
  selectable?: boolean;
  /** Make rows clickable */
  rowClickable?: boolean;
  /** Number of skeleton rows while loading */
  skeletonRows?: number;
  /** Function to compute custom row classes */
  rowClass?: (item: T) => string;
}

interface Emits {
  (e: 'row-click', item: T): void;
  (e: 'selection-change', ids: number[]): void;
  (e: 'delete-selected', ids: number[]): void;
  (e: 'retry'): void;
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
  isError: false,
  entityName: 'item',
  selectable: false,
  rowClickable: false,
  skeletonRows: 5,
});

const emit = defineEmits<Emits>();

// Items ref for selection composable
const itemsRef = computed(() => props.items);

// Selection state (only if selectable)
const selection = props.selectable
  ? useSelection({
      items: itemsRef,
      getItemId: (item: T) => item.id,
    })
  : null;

// Watch selection changes
if (selection) {
  watch(
    () => selection.selectedIdArray.value,
    (ids) => {
      emit('selection-change', ids);
    }
  );
}

const handleRowClick = (item: T) => {
  if (props.rowClickable) {
    emit('row-click', item);
  }
};

const handleCheckboxClick = (e: Event, id: number) => {
  e.stopPropagation();
  selection?.toggleItem(id);
};

const handleSelectAllClick = (e: Event) => {
  e.stopPropagation();
  selection?.toggleAll();
};

const getCellValue = (item: T, column: TableColumn<T>): unknown => {
  if (column.accessor) {
    return column.accessor(item);
  }
  return (item as Record<string, unknown>)[column.key];
};

const alignmentClass = (align?: 'left' | 'center' | 'right') => {
  switch (align) {
    case 'center':
      return 'text-center';
    case 'right':
      return 'text-right';
    default:
      return 'text-left';
  }
};

// Expose selection methods for parent components
defineExpose({
  selection,
  getSelectedIds: () => selection?.selectedIdArray.value ?? [],
  clearSelection: () => selection?.deselectAll(),
});
</script>

<template>
  <div>
    <!-- Loading State -->
    <div v-if="isLoading" class="overflow-hidden rounded-xl border border-border-subtle">
      <table class="w-full">
        <thead class="bg-bg-elevated">
          <tr>
            <th v-if="selectable" class="w-12 py-3 pl-4 pr-2 text-left">
              <div class="h-4 w-4 rounded bg-bg-hover" />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3"
              :class="[column.width, alignmentClass(column.align)]"
            >
              <div class="h-4 w-20 rounded bg-bg-hover" />
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-subtle">
          <tr v-for="i in skeletonRows" :key="i" class="animate-pulse">
            <td v-if="selectable" class="py-4 pl-4 pr-2">
              <div class="h-4 w-4 rounded bg-bg-hover" />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-4"
            >
              <div class="h-4 rounded bg-bg-hover" :class="column.width || 'w-24'" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Error State -->
    <ErrorState
      v-else-if="isError"
      :entity-name="entityName + 's'"
      :error="error"
      show-retry
      @retry="$emit('retry')"
    />

    <!-- Empty State -->
    <EmptyState
      v-else-if="!items || items.length === 0"
      :title="`No ${entityName}s found`"
      :message="`${entityName.charAt(0).toUpperCase() + entityName.slice(1)}s will appear here once they are created.`"
    >
      <template #action>
        <slot name="empty-action" />
      </template>
    </EmptyState>

    <!-- Table -->
    <div v-else class="overflow-hidden rounded-xl border border-border-subtle">
      <table class="w-full">
        <thead class="bg-bg-elevated">
          <tr>
            <!-- Select All Checkbox - entire cell is clickable -->
            <th
              v-if="selectable"
              class="w-12 py-3 pl-4 pr-2 text-left cursor-pointer"
              @click="handleSelectAllClick"
            >
              <input
                type="checkbox"
                :checked="selection?.isAllSelected.value"
                :indeterminate="selection?.isSomeSelected.value"
                class="h-4 w-4 rounded border-border-subtle bg-bg-surface text-accent-primary focus:ring-accent-primary focus:ring-offset-bg-base pointer-events-none"
              />
            </th>
            <!-- Column Headers -->
            <th
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-muted"
              :class="[column.width, alignmentClass(column.align)]"
            >
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-subtle bg-bg-surface">
          <tr
            v-for="item in items"
            :key="item.id"
            @click="handleRowClick(item)"
            class="transition-colors duration-150"
            :class="[
              rowClickable ? 'cursor-pointer hover:bg-bg-hover' : '',
              selection?.isSelected(item.id) ? 'bg-accent-primary/5' : '',
              rowClass?.(item) ?? '',
            ]"
          >
            <!-- Row Checkbox - entire cell is clickable -->
            <td
              v-if="selectable"
              class="py-4 pl-4 pr-2 cursor-pointer"
              @click="(e) => handleCheckboxClick(e, item.id)"
            >
              <input
                type="checkbox"
                :checked="selection?.isSelected(item.id)"
                class="h-4 w-4 rounded border-border-subtle bg-bg-surface text-accent-primary focus:ring-accent-primary focus:ring-offset-bg-base pointer-events-none"
              />
            </td>
            <!-- Data Cells -->
            <td
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-4 text-sm"
              :class="[alignmentClass(column.align), column.key === 'actions' ? 'actions-cell' : '']"
            >
              <!-- Named slot for custom cell rendering -->
              <slot
                :name="`cell-${column.key}`"
                :item="item"
                :value="getCellValue(item, column)"
                :column="column"
              >
                <!-- Default: render value as text -->
                <span class="text-text-primary">
                  {{ getCellValue(item, column) }}
                </span>
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination slot -->
    <slot name="pagination" />
  </div>
</template>

<style scoped>
/* Ensure action buttons have adequate click/tap targets (min 44px recommended) */
.actions-cell :deep(button),
.actions-cell :deep(a) {
  min-width: 36px;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
