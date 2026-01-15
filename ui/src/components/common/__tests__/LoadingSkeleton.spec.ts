import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LoadingSkeleton from '../LoadingSkeleton.vue';

describe('LoadingSkeleton', () => {
  describe('single line skeleton', () => {
    it('renders single skeleton line by default', () => {
      const wrapper = mount(LoadingSkeleton);

      const skeletonDivs = wrapper.findAll('.bg-bg-hover');
      expect(skeletonDivs.length).toBe(1);
    });

    it('applies animate-pulse class', () => {
      const wrapper = mount(LoadingSkeleton);

      expect(wrapper.find('.animate-pulse').exists()).toBe(true);
    });

    it('applies default height (h-4)', () => {
      const wrapper = mount(LoadingSkeleton);

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('h-4');
    });

    it('applies default width (w-full)', () => {
      const wrapper = mount(LoadingSkeleton);

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('w-full');
    });

    it('applies default rounded class (rounded)', () => {
      const wrapper = mount(LoadingSkeleton);

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('rounded');
    });
  });

  describe('custom dimensions', () => {
    it('applies custom height', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { height: 'h-8' },
      });

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('h-8');
    });

    it('applies custom width', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { width: 'w-1/2' },
      });

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('w-1/2');
    });
  });

  describe('rounded variants', () => {
    const roundedTests = [
      { variant: 'none', expectedClass: 'rounded-none' },
      { variant: 'sm', expectedClass: 'rounded-sm' },
      { variant: 'md', expectedClass: 'rounded' },
      { variant: 'lg', expectedClass: 'rounded-lg' },
      { variant: 'xl', expectedClass: 'rounded-xl' },
      { variant: '2xl', expectedClass: 'rounded-2xl' },
      { variant: 'full', expectedClass: 'rounded-full' },
    ] as const;

    roundedTests.forEach(({ variant, expectedClass }) => {
      it(`applies ${expectedClass} for rounded="${variant}"`, () => {
        const wrapper = mount(LoadingSkeleton, {
          props: { rounded: variant },
        });

        const skeleton = wrapper.find('.bg-bg-hover');
        expect(skeleton.classes()).toContain(expectedClass);
      });
    });
  });

  describe('multiple lines', () => {
    it('renders multiple skeleton lines when lines > 1', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 3 },
      });

      const skeletonDivs = wrapper.findAll('.bg-bg-hover');
      expect(skeletonDivs.length).toBe(3);
    });

    it('applies flex-col layout for multiple lines', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 3 },
      });

      const container = wrapper.find('.animate-pulse');
      expect(container.classes()).toContain('flex');
      expect(container.classes()).toContain('flex-col');
    });

    it('makes last line shorter (w-2/3)', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 3 },
      });

      const skeletonDivs = wrapper.findAll('.bg-bg-hover');
      // Last line should have w-2/3
      expect(skeletonDivs[2].classes()).toContain('w-2/3');
      // Other lines should have the default width
      expect(skeletonDivs[0].classes()).toContain('w-full');
      expect(skeletonDivs[1].classes()).toContain('w-full');
    });

    it('applies custom gap between lines', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 3, gap: 'gap-4' },
      });

      const container = wrapper.find('.animate-pulse');
      expect(container.classes()).toContain('gap-4');
    });

    it('uses default gap (gap-2) for multiple lines', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 3 },
      });

      const container = wrapper.find('.animate-pulse');
      expect(container.classes()).toContain('gap-2');
    });
  });

  describe('edge cases', () => {
    it('handles lines=1 correctly (single line mode)', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: { lines: 1 },
      });

      // Should use single line template (no flex-col)
      const container = wrapper.find('.animate-pulse');
      expect(container.classes()).not.toContain('flex-col');
    });

    it('applies all props together', () => {
      const wrapper = mount(LoadingSkeleton, {
        props: {
          height: 'h-6',
          width: 'w-3/4',
          rounded: 'lg',
          lines: 1,
        },
      });

      const skeleton = wrapper.find('.bg-bg-hover');
      expect(skeleton.classes()).toContain('h-6');
      expect(skeleton.classes()).toContain('w-3/4');
      expect(skeleton.classes()).toContain('rounded-lg');
    });
  });
});
