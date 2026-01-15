import { describe, it, expect } from 'vitest';
import { ref, nextTick } from 'vue';
import { useSelection } from '../useSelection';

interface TestItem {
  id: number;
  name: string;
}

describe('useSelection', () => {
  const createItems = () => [
    { id: 1, name: 'Item 1' },
    { id: 2, name: 'Item 2' },
    { id: 3, name: 'Item 3' },
  ];

  describe('initialization', () => {
    it('starts with empty selection', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectedIds, selectedCount, hasSelection } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      expect(selectedIds.value.size).toBe(0);
      expect(selectedCount.value).toBe(0);
      expect(hasSelection.value).toBe(false);
    });
  });

  describe('selectItem', () => {
    it('adds item to selection', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectItem, selectedIds, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(1);

      expect(selectedIds.value.has(1)).toBe(true);
      expect(selectedCount.value).toBe(1);
    });

    it('can select multiple items', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectItem, selectedIds, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(1);
      selectItem(2);

      expect(selectedIds.value.has(1)).toBe(true);
      expect(selectedIds.value.has(2)).toBe(true);
      expect(selectedCount.value).toBe(2);
    });
  });

  describe('deselectItem', () => {
    it('removes item from selection', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectItem, deselectItem, selectedIds, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(1);
      selectItem(2);
      deselectItem(1);

      expect(selectedIds.value.has(1)).toBe(false);
      expect(selectedIds.value.has(2)).toBe(true);
      expect(selectedCount.value).toBe(1);
    });

    it('handles deselecting non-selected item', () => {
      const items = ref<TestItem[]>(createItems());
      const { deselectItem, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      deselectItem(999);

      expect(selectedCount.value).toBe(0);
    });
  });

  describe('toggleItem', () => {
    it('selects item if not selected', () => {
      const items = ref<TestItem[]>(createItems());
      const { toggleItem, isSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      toggleItem(1);

      expect(isSelected(1)).toBe(true);
    });

    it('deselects item if already selected', () => {
      const items = ref<TestItem[]>(createItems());
      const { toggleItem, selectItem, isSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(1);
      toggleItem(1);

      expect(isSelected(1)).toBe(false);
    });
  });

  describe('selectAll', () => {
    it('selects all items', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectAll, selectedCount, isAllSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectAll();

      expect(selectedCount.value).toBe(3);
      expect(isAllSelected.value).toBe(true);
    });
  });

  describe('deselectAll', () => {
    it('clears all selections', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectAll, deselectAll, selectedCount, hasSelection } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectAll();
      deselectAll();

      expect(selectedCount.value).toBe(0);
      expect(hasSelection.value).toBe(false);
    });
  });

  describe('toggleAll', () => {
    it('selects all when none selected', () => {
      const items = ref<TestItem[]>(createItems());
      const { toggleAll, isAllSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      toggleAll();

      expect(isAllSelected.value).toBe(true);
    });

    it('selects all when some selected', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectItem, toggleAll, isAllSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(1);
      toggleAll();

      expect(isAllSelected.value).toBe(true);
    });

    it('deselects all when all selected', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectAll, toggleAll, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectAll();
      toggleAll();

      expect(selectedCount.value).toBe(0);
    });
  });

  describe('isSelected', () => {
    it('returns true for selected item', () => {
      const items = ref<TestItem[]>(createItems());
      const { selectItem, isSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectItem(2);

      expect(isSelected(2)).toBe(true);
    });

    it('returns false for non-selected item', () => {
      const items = ref<TestItem[]>(createItems());
      const { isSelected } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      expect(isSelected(2)).toBe(false);
    });
  });

  describe('computed properties', () => {
    describe('isAllSelected', () => {
      it('returns false when empty items', () => {
        const items = ref<TestItem[]>([]);
        const { isAllSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        expect(isAllSelected.value).toBe(false);
      });

      it('returns false when some items selected', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectItem, isAllSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectItem(1);

        expect(isAllSelected.value).toBe(false);
      });

      it('returns true when all items selected', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectAll, isAllSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectAll();

        expect(isAllSelected.value).toBe(true);
      });
    });

    describe('isSomeSelected', () => {
      it('returns false when no items selected', () => {
        const items = ref<TestItem[]>(createItems());
        const { isSomeSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        expect(isSomeSelected.value).toBe(false);
      });

      it('returns true when some items selected', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectItem, isSomeSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectItem(1);

        expect(isSomeSelected.value).toBe(true);
      });

      it('returns false when all items selected', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectAll, isSomeSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectAll();

        expect(isSomeSelected.value).toBe(false);
      });

      it('returns false when empty items', () => {
        const items = ref<TestItem[]>([]);
        const { isSomeSelected } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        expect(isSomeSelected.value).toBe(false);
      });
    });

    describe('selectedItems', () => {
      it('returns array of selected items', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectItem, selectedItems } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectItem(1);
        selectItem(3);

        expect(selectedItems.value).toEqual([
          { id: 1, name: 'Item 1' },
          { id: 3, name: 'Item 3' },
        ]);
      });
    });

    describe('selectedIdArray', () => {
      it('returns array of selected IDs', () => {
        const items = ref<TestItem[]>(createItems());
        const { selectItem, selectedIdArray } = useSelection({
          items,
          getItemId: (item) => item.id,
        });

        selectItem(1);
        selectItem(3);

        expect(selectedIdArray.value).toContain(1);
        expect(selectedIdArray.value).toContain(3);
        expect(selectedIdArray.value.length).toBe(2);
      });
    });
  });

  describe('items change behavior', () => {
    it('clears selection when items change', async () => {
      const items = ref<TestItem[]>(createItems());
      const { selectAll, selectedCount } = useSelection({
        items,
        getItemId: (item) => item.id,
      });

      selectAll();
      expect(selectedCount.value).toBe(3);

      // Change items (simulating page change)
      items.value = [
        { id: 4, name: 'Item 4' },
        { id: 5, name: 'Item 5' },
      ];

      await nextTick();

      expect(selectedCount.value).toBe(0);
    });
  });
});
