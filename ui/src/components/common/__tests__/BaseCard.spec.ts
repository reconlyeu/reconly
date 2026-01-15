import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import BaseCard from '../BaseCard.vue';

describe('BaseCard', () => {
  describe('slot rendering', () => {
    it('renders default slot content', () => {
      const wrapper = mount(BaseCard, {
        slots: {
          default: '<p>Card body content</p>',
        },
      });

      expect(wrapper.text()).toContain('Card body content');
    });

    it('renders header slot when provided', () => {
      const wrapper = mount(BaseCard, {
        slots: {
          header: '<h2>Header Content</h2>',
          default: '<p>Body</p>',
        },
      });

      expect(wrapper.text()).toContain('Header Content');
    });

    it('renders footer slot when provided', () => {
      const wrapper = mount(BaseCard, {
        slots: {
          footer: '<span>Footer Content</span>',
          default: '<p>Body</p>',
        },
      });

      expect(wrapper.text()).toContain('Footer Content');
    });

    it('does not render header wrapper when no header slot', () => {
      const wrapper = mount(BaseCard, {
        slots: {
          default: '<p>Body only</p>',
        },
      });

      // The header div should not be present (v-if="$slots.header")
      const headerDivs = wrapper.findAll('.mb-4');
      // The mb-4 class is only on the header slot wrapper, which should not exist
      expect(wrapper.html()).not.toContain('class="mb-4"');
    });

    it('does not render footer wrapper when no footer slot', () => {
      const wrapper = mount(BaseCard, {
        slots: {
          default: '<p>Body only</p>',
        },
      });

      // The footer has border-t class, which should not be present
      expect(wrapper.find('.border-t').exists()).toBe(false);
    });
  });

  describe('clickable prop behavior', () => {
    it('has cursor-pointer class when clickable is true', () => {
      const wrapper = mount(BaseCard, {
        props: { clickable: true },
        slots: { default: '<p>Content</p>' },
      });

      expect(wrapper.classes()).toContain('cursor-pointer');
    });

    it('does not have cursor-pointer class when clickable is false', () => {
      const wrapper = mount(BaseCard, {
        props: { clickable: false },
        slots: { default: '<p>Content</p>' },
      });

      expect(wrapper.classes()).not.toContain('cursor-pointer');
    });

    it('emits click event when clickable and clicked', async () => {
      const wrapper = mount(BaseCard, {
        props: { clickable: true },
        slots: { default: '<p>Content</p>' },
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeTruthy();
      expect(wrapper.emitted('click')).toHaveLength(1);
    });

    it('does not emit click event when not clickable', async () => {
      const wrapper = mount(BaseCard, {
        props: { clickable: false },
        slots: { default: '<p>Content</p>' },
      });

      await wrapper.trigger('click');

      expect(wrapper.emitted('click')).toBeFalsy();
    });
  });

  describe('glow color variants', () => {
    const glowColorTests = [
      { color: 'primary', expectedClass: 'bg-accent-primary' },
      { color: 'success', expectedClass: 'bg-status-success' },
      { color: 'warning', expectedClass: 'bg-amber-400' },
      { color: 'error', expectedClass: 'bg-status-failed' },
      { color: 'blue', expectedClass: 'bg-blue-400' },
      { color: 'purple', expectedClass: 'bg-purple-400' },
      { color: 'orange', expectedClass: 'bg-orange-400' },
    ] as const;

    glowColorTests.forEach(({ color, expectedClass }) => {
      it(`applies ${expectedClass} for glowColor="${color}"`, () => {
        const wrapper = mount(BaseCard, {
          props: { glowColor: color },
          slots: { default: '<p>Content</p>' },
        });

        // The decorative corner orb should have the glow color class
        expect(wrapper.html()).toContain(expectedClass);
      });
    });

    it('defaults to primary glow color', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: '<p>Content</p>' },
      });

      expect(wrapper.html()).toContain('bg-accent-primary');
    });
  });

  describe('static prop behavior', () => {
    it('disables hover effects when static is true', () => {
      const wrapper = mount(BaseCard, {
        props: { static: true },
        slots: { default: '<p>Content</p>' },
      });

      // When static, the hover glow and decorative orb should not be present
      // The hover effect div has opacity-0 and group-hover:opacity-100
      const html = wrapper.html();
      // With static=true, the v-if="!static" elements should not render
      expect(html).not.toContain('group-hover:opacity-100');
    });

    it('enables hover effects when static is false', () => {
      const wrapper = mount(BaseCard, {
        props: { static: false },
        slots: { default: '<p>Content</p>' },
      });

      const html = wrapper.html();
      expect(html).toContain('group-hover:opacity-100');
    });
  });

  describe('padded prop behavior', () => {
    it('has p-6 class when padded is true (default)', () => {
      const wrapper = mount(BaseCard, {
        slots: { default: '<p>Content</p>' },
      });

      expect(wrapper.classes()).toContain('p-6');
    });

    it('does not have p-6 class when padded is false', () => {
      const wrapper = mount(BaseCard, {
        props: { padded: false },
        slots: { default: '<p>Content</p>' },
      });

      expect(wrapper.classes()).not.toContain('p-6');
    });
  });
});
