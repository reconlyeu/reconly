/**
 * Composable for managing multi-select state.
 * Used for batch operations in table views.
 */
import { ref, computed, watch, type Ref } from 'vue';

export interface UseSelectionOptions<T> {
  /** Items available for selection */
  items: Ref<T[]>;
  /** Function to extract ID from an item */
  getItemId: (item: T) => number;
}

export function useSelection<T>(options: UseSelectionOptions<T>) {
  const { items, getItemId } = options;

  // Track selected IDs as a Set for O(1) lookup
  const selectedIds = ref<Set<number>>(new Set());

  // Clear selection when items change (e.g., page change, filter change)
  watch(items, () => {
    selectedIds.value = new Set();
  }, { deep: false });

  const selectItem = (id: number) => {
    const newSet = new Set(selectedIds.value);
    newSet.add(id);
    selectedIds.value = newSet;
  };

  const deselectItem = (id: number) => {
    const newSet = new Set(selectedIds.value);
    newSet.delete(id);
    selectedIds.value = newSet;
  };

  const toggleItem = (id: number) => {
    if (selectedIds.value.has(id)) {
      deselectItem(id);
    } else {
      selectItem(id);
    }
  };

  const selectAll = () => {
    const allIds = items.value.map(getItemId);
    selectedIds.value = new Set(allIds);
  };

  const deselectAll = () => {
    selectedIds.value = new Set();
  };

  const toggleAll = () => {
    if (isAllSelected.value) {
      deselectAll();
    } else {
      selectAll();
    }
  };

  const isSelected = (id: number): boolean => {
    return selectedIds.value.has(id);
  };

  const selectedCount = computed(() => selectedIds.value.size);

  const hasSelection = computed(() => selectedIds.value.size > 0);

  const isAllSelected = computed(() => {
    if (items.value.length === 0) return false;
    return items.value.every(item => selectedIds.value.has(getItemId(item)));
  });

  const isSomeSelected = computed(() => {
    if (items.value.length === 0) return false;
    return hasSelection.value && !isAllSelected.value;
  });

  const selectedItems = computed(() => {
    return items.value.filter(item => selectedIds.value.has(getItemId(item)));
  });

  const selectedIdArray = computed(() => Array.from(selectedIds.value));

  return {
    // State
    selectedIds,
    selectedCount,
    hasSelection,
    isAllSelected,
    isSomeSelected,
    selectedItems,
    selectedIdArray,
    // Methods
    selectItem,
    deselectItem,
    toggleItem,
    selectAll,
    deselectAll,
    toggleAll,
    isSelected,
  };
}
