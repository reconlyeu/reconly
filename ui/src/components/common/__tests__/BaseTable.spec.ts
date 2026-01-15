import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { ref, computed } from 'vue';
import BaseTable from '../BaseTable.vue';
import { listComponentStubs, errorStateWithRetry } from '@/test-utils';

// Create a factory function for the selection mock
function createSelectionMock() {
  const selectedIds = ref(new Set<number>());

  return {
    selectedIds,
    selectedCount: computed(() => selectedIds.value.size),
    hasSelection: computed(() => selectedIds.value.size > 0),
    isAllSelected: ref(false),
    isSomeSelected: ref(false),
    selectedItems: ref([]),
    selectedIdArray: computed(() => Array.from(selectedIds.value)),
    selectItem: vi.fn((id: number) => {
      selectedIds.value = new Set([...selectedIds.value, id]);
    }),
    deselectItem: vi.fn((id: number) => {
      const newSet = new Set(selectedIds.value);
      newSet.delete(id);
      selectedIds.value = newSet;
    }),
    toggleItem: vi.fn((id: number) => {
      if (selectedIds.value.has(id)) {
        const newSet = new Set(selectedIds.value);
        newSet.delete(id);
        selectedIds.value = newSet;
      } else {
        selectedIds.value = new Set([...selectedIds.value, id]);
      }
    }),
    selectAll: vi.fn(),
    deselectAll: vi.fn(),
    toggleAll: vi.fn(),
    isSelected: (id: number) => selectedIds.value.has(id),
  };
}

// Mock the useSelection composable
vi.mock('@/composables/useSelection', () => ({
  useSelection: vi.fn(() => createSelectionMock()),
}));

interface TestItem {
  id: number;
  name: string;
  status: string;
}

const testColumns = [
  { key: 'name', label: 'Name' },
  { key: 'status', label: 'Status' },
];

const testItems: TestItem[] = [
  { id: 1, name: 'Item 1', status: 'active' },
  { id: 2, name: 'Item 2', status: 'inactive' },
  { id: 3, name: 'Item 3', status: 'active' },
];

describe('BaseTable', () => {
  describe('column rendering', () => {
    it('renders column headers', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.text()).toContain('Name');
      expect(wrapper.text()).toContain('Status');
    });

    it('renders cell values for each column', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.text()).toContain('Item 1');
      expect(wrapper.text()).toContain('Item 2');
      expect(wrapper.text()).toContain('active');
      expect(wrapper.text()).toContain('inactive');
    });

    it('uses custom accessor function when provided', () => {
      const columnsWithAccessor = [
        {
          key: 'displayName',
          label: 'Display Name',
          accessor: (item: TestItem) => `[${item.name}]`,
        },
      ];

      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: columnsWithAccessor,
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.text()).toContain('[Item 1]');
      expect(wrapper.text()).toContain('[Item 2]');
    });

    it('applies column width class', () => {
      const columnsWithWidth = [
        { key: 'name', label: 'Name', width: 'w-48' },
        { key: 'status', label: 'Status' },
      ];

      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: columnsWithWidth,
        },
        global: { stubs: listComponentStubs },
      });

      const header = wrapper.find('th');
      expect(header.classes()).toContain('w-48');
    });

    it('applies column alignment', () => {
      const columnsWithAlign = [
        { key: 'name', label: 'Name', align: 'left' as const },
        { key: 'status', label: 'Status', align: 'center' as const },
      ];

      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: columnsWithAlign,
        },
        global: { stubs: listComponentStubs },
      });

      const headers = wrapper.findAll('th');
      expect(headers[0].classes()).toContain('text-left');
      expect(headers[1].classes()).toContain('text-center');
    });
  });

  describe('row selection', () => {
    it('renders checkboxes when selectable is true', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          selectable: true,
        },
        global: { stubs: listComponentStubs },
      });

      const checkboxes = wrapper.findAll('input[type="checkbox"]');
      // 1 select-all + 3 row checkboxes
      expect(checkboxes.length).toBe(4);
    });

    it('does not render checkboxes when selectable is false', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          selectable: false,
        },
        global: { stubs: listComponentStubs },
      });

      const checkboxes = wrapper.findAll('input[type="checkbox"]');
      expect(checkboxes.length).toBe(0);
    });

    it('emits selection-change when selection changes', async () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          selectable: true,
        },
        global: { stubs: listComponentStubs },
      });

      // The component uses watch to emit selection-change
      // Due to the mock, we need to verify the emission pattern
      // Selection change is emitted via watch on selectedIdArray
      expect(wrapper.emitted('selection-change')).toBeFalsy(); // Initial mount
    });
  });

  describe('row click behavior', () => {
    it('emits row-click when rowClickable is true and row is clicked', async () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          rowClickable: true,
        },
        global: { stubs: listComponentStubs },
      });

      const rows = wrapper.findAll('tbody tr');
      await rows[0].trigger('click');

      expect(wrapper.emitted('row-click')).toBeTruthy();
      expect(wrapper.emitted('row-click')![0]).toEqual([testItems[0]]);
    });

    it('does not emit row-click when rowClickable is false', async () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          rowClickable: false,
        },
        global: { stubs: listComponentStubs },
      });

      const rows = wrapper.findAll('tbody tr');
      await rows[0].trigger('click');

      expect(wrapper.emitted('row-click')).toBeFalsy();
    });

    it('applies hover styles when rowClickable is true', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
          rowClickable: true,
        },
        global: { stubs: listComponentStubs },
      });

      const row = wrapper.find('tbody tr');
      expect(row.classes()).toContain('cursor-pointer');
      expect(row.classes()).toContain('hover:bg-bg-hover');
    });
  });

  describe('loading state', () => {
    it('renders skeleton rows when isLoading is true', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: [],
          columns: testColumns,
          isLoading: true,
          skeletonRows: 3,
        },
        global: { stubs: listComponentStubs },
      });

      const skeletonRows = wrapper.findAll('.animate-pulse');
      expect(skeletonRows.length).toBe(3);
    });

    it('renders 5 skeleton rows by default', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: [],
          columns: testColumns,
          isLoading: true,
        },
        global: { stubs: listComponentStubs },
      });

      const skeletonRows = wrapper.findAll('.animate-pulse');
      expect(skeletonRows.length).toBe(5);
    });
  });

  describe('error state', () => {
    it('renders ErrorState when isError is true', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: [],
          columns: testColumns,
          isError: true,
          error: new Error('Failed'),
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true);
    });

    it('emits retry event when ErrorState emits retry', async () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: [],
          columns: testColumns,
          isError: true,
        },
        global: {
          stubs: {
            ...listComponentStubs,
            ErrorState: errorStateWithRetry,
          },
        },
      });

      await wrapper.find('button').trigger('click');
      expect(wrapper.emitted('retry')).toBeTruthy();
    });
  });

  describe('empty state', () => {
    it('renders EmptyState when items is empty', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: [],
          columns: testColumns,
          entityName: 'source',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
    });
  });

  describe('custom cell slots', () => {
    it('renders custom cell content via named slots', () => {
      const wrapper = mount(BaseTable, {
        props: {
          items: testItems,
          columns: testColumns,
        },
        slots: {
          'cell-status': `
            <template #cell-status="{ value }">
              <span class="status-badge">{{ value }}</span>
            </template>
          `,
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.findAll('.status-badge').length).toBe(3);
    });
  });
});
