import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import BaseList from '../BaseList.vue';
import {
  listComponentStubs,
  errorStateWithRetry,
  paginationWithEvents,
} from '@/test-utils';

describe('BaseList', () => {
  describe('empty state rendering', () => {
    it('renders EmptyState when items is empty array', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
          entityName: 'digest',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="loading-skeleton"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(false);
    });

    it('renders EmptyState when items is undefined/null treated as empty', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
    });

    it('renders empty-action slot content in EmptyState', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
        },
        slots: {
          'empty-action': '<button>Add Item</button>',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.text()).toContain('Add Item');
    });
  });

  describe('loading state', () => {
    it('renders loading skeletons when isLoading is true', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
          isLoading: true,
          skeletonCount: 4,
        },
        global: { stubs: listComponentStubs },
      });

      // Should render loading skeleton divs based on skeletonCount
      const skeletons = wrapper.findAll('.animate-pulse');
      expect(skeletons.length).toBe(4);
    });

    it('renders 6 skeletons by default', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
          isLoading: true,
        },
        global: { stubs: listComponentStubs },
      });

      const skeletons = wrapper.findAll('.animate-pulse');
      expect(skeletons.length).toBe(6);
    });

    it('applies custom skeleton height', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
          isLoading: true,
          skeletonCount: 1,
          skeletonHeight: 'h-40',
        },
        global: { stubs: listComponentStubs },
      });

      const skeleton = wrapper.find('.animate-pulse');
      expect(skeleton.classes()).toContain('h-40');
    });
  });

  describe('error state', () => {
    it('renders ErrorState when isError is true', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
          isError: true,
          error: new Error('Failed to load'),
          entityName: 'source',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true);
    });

    it('emits retry event when error state retry is triggered', async () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [],
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

  describe('item slot rendering', () => {
    it('renders items using default slot', () => {
      const items = [
        { id: 1, name: 'Item 1' },
        { id: 2, name: 'Item 2' },
        { id: 3, name: 'Item 3' },
      ];

      const wrapper = mount(BaseList, {
        props: { items },
        slots: {
          default: `
            <template #default="{ items }">
              <div v-for="item in items" :key="item.id" data-testid="list-item">
                {{ item.name }}
              </div>
            </template>
          `,
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.findAll('[data-testid="list-item"]').length).toBe(3);
      expect(wrapper.text()).toContain('Item 1');
      expect(wrapper.text()).toContain('Item 2');
      expect(wrapper.text()).toContain('Item 3');
    });

    it('applies correct grid columns class', () => {
      const items = [{ id: 1 }];

      // Test gridCols=3
      const wrapper = mount(BaseList, {
        props: { items, gridCols: 3 },
        slots: {
          default: '<div>Item</div>',
        },
        global: { stubs: listComponentStubs },
      });

      const grid = wrapper.find('.grid.gap-6');
      expect(grid.classes()).toContain('lg:grid-cols-3');
    });
  });

  describe('pagination', () => {
    it('renders pagination when showPagination is true and totalPages > 1', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [{ id: 1 }],
          showPagination: true,
          page: 1,
          totalPages: 5,
        },
        slots: {
          default: '<div>Item</div>',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="pagination"]').exists()).toBe(true);
    });

    it('does not render pagination when totalPages is 1', () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [{ id: 1 }],
          showPagination: true,
          page: 1,
          totalPages: 1,
        },
        slots: {
          default: '<div>Item</div>',
        },
        global: { stubs: listComponentStubs },
      });

      expect(wrapper.find('[data-testid="pagination"]').exists()).toBe(false);
    });

    it('emits prev-page event', async () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [{ id: 1 }],
          showPagination: true,
          page: 2,
          totalPages: 5,
        },
        slots: {
          default: '<div>Item</div>',
        },
        global: {
          stubs: {
            ...listComponentStubs,
            Pagination: paginationWithEvents,
          },
        },
      });

      await wrapper.findAll('button')[0].trigger('click');
      expect(wrapper.emitted('prev-page')).toBeTruthy();
    });

    it('emits next-page event', async () => {
      const wrapper = mount(BaseList, {
        props: {
          items: [{ id: 1 }],
          showPagination: true,
          page: 2,
          totalPages: 5,
        },
        slots: {
          default: '<div>Item</div>',
        },
        global: {
          stubs: {
            ...listComponentStubs,
            Pagination: paginationWithEvents,
          },
        },
      });

      await wrapper.findAll('button')[1].trigger('click');
      expect(wrapper.emitted('next-page')).toBeTruthy();
    });
  });
});
