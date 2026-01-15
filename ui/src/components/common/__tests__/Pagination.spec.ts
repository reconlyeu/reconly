import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import Pagination from '../Pagination.vue';
import { iconStubs } from '@/test-utils';

const globalConfig = {
  global: { stubs: iconStubs },
};

describe('Pagination', () => {
  describe('page navigation with explicit hasNext/hasPrev', () => {
    // Note: In the test environment, optional boolean props (hasNext, hasPrev) are set to false
    // by default rather than undefined. The component uses ?? operator which doesn't work with false.
    // Therefore, we must explicitly pass hasNext/hasPrev props for proper behavior.

    it('emits prev event when previous button is clicked', async () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 2,
          totalPages: 5,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      const prevButton = wrapper.findAll('button')[0];
      await prevButton.trigger('click');

      expect(wrapper.emitted('prev')).toBeTruthy();
      expect(wrapper.emitted('prev')).toHaveLength(1);
    });

    it('emits next event when next button is clicked', async () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 2,
          totalPages: 5,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      const nextButton = wrapper.findAll('button')[1];
      await nextButton.trigger('click');

      expect(wrapper.emitted('next')).toBeTruthy();
      expect(wrapper.emitted('next')).toHaveLength(1);
    });

    it('disables prev button when hasPrev is false', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 1,
          totalPages: 5,
          hasPrev: false,
          hasNext: true,
        },
        ...globalConfig,
      });

      const prevButton = wrapper.findAll('button')[0];
      expect(prevButton.attributes()).toHaveProperty('disabled');
    });

    it('disables next button when hasNext is false', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 5,
          totalPages: 5,
          hasPrev: true,
          hasNext: false,
        },
        ...globalConfig,
      });

      const nextButton = wrapper.findAll('button')[1];
      expect(nextButton.attributes()).toHaveProperty('disabled');
    });

    it('enables both buttons when hasPrev and hasNext are true', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 3,
          totalPages: 5,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      const buttons = wrapper.findAll('button');
      expect((buttons[0].element as HTMLButtonElement).disabled).toBe(false);
      expect((buttons[1].element as HTMLButtonElement).disabled).toBe(false);
    });
  });

  describe('hasNext/hasPrev props control', () => {
    it('respects hasNext=true even on last page', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 5,
          totalPages: 5,
          hasNext: true,
          hasPrev: true,
        },
        ...globalConfig,
      });

      const nextButton = wrapper.findAll('button')[1];
      expect((nextButton.element as HTMLButtonElement).disabled).toBe(false);
    });

    it('respects hasPrev=true even on first page', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 1,
          totalPages: 5,
          hasNext: true,
          hasPrev: true,
        },
        ...globalConfig,
      });

      const prevButton = wrapper.findAll('button')[0];
      expect((prevButton.element as HTMLButtonElement).disabled).toBe(false);
    });

    it('disables buttons when hasNext/hasPrev are false', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 3,
          totalPages: 5,
          hasNext: false,
          hasPrev: false,
        },
        ...globalConfig,
      });

      const buttons = wrapper.findAll('button');
      expect(buttons[0].attributes()).toHaveProperty('disabled');
      expect(buttons[1].attributes()).toHaveProperty('disabled');
    });
  });

  describe('page info display', () => {
    it('shows page info by default', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 3,
          totalPages: 10,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      expect(wrapper.text()).toContain('Page 3 of 10');
    });

    it('hides page info when showPageInfo is false', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 3,
          totalPages: 10,
          showPageInfo: false,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      expect(wrapper.text()).not.toContain('Page 3 of 10');
    });
  });

  describe('button content', () => {
    it('displays Previous and Next text', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 2,
          totalPages: 5,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      expect(wrapper.text()).toContain('Previous');
      expect(wrapper.text()).toContain('Next');
    });

    it('renders chevron icons (as stubs)', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 2,
          totalPages: 5,
          hasPrev: true,
          hasNext: true,
        },
        ...globalConfig,
      });

      // With { stubs: { ChevronLeft: true } }, components are rendered as <chevronleft-stub>
      // However, lucide icons are still rendered as SVG elements because they are imported directly
      // Check that SVG icons are present
      const svgs = wrapper.findAll('svg');
      expect(svgs.length).toBe(2);
    });
  });

  describe('edge cases', () => {
    it('handles single page correctly (both disabled)', () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 1,
          totalPages: 1,
          hasPrev: false,
          hasNext: false,
        },
        ...globalConfig,
      });

      const buttons = wrapper.findAll('button');
      expect(buttons[0].attributes()).toHaveProperty('disabled');
      expect(buttons[1].attributes()).toHaveProperty('disabled');
    });

    it('does not emit click event for disabled button in happy-dom', async () => {
      const wrapper = mount(Pagination, {
        props: {
          page: 1,
          totalPages: 1,
          hasPrev: false,
          hasNext: false,
        },
        ...globalConfig,
      });

      const prevButton = wrapper.findAll('button')[0];
      await prevButton.trigger('click');

      // In happy-dom, disabled buttons do not emit click events
      // This differs from real browser behavior where the event fires but is often ignored
      expect(wrapper.emitted('prev')).toBeFalsy();
    });
  });
});
