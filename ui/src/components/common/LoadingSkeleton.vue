<script setup lang="ts">
/**
 * Reusable loading skeleton component.
 * Displays an animated placeholder while content is loading.
 */

interface Props {
  /** Height of the skeleton (CSS value or Tailwind class) */
  height?: string;
  /** Width of the skeleton (CSS value or Tailwind class) */
  width?: string;
  /** Border radius variant */
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
  /** Number of skeleton lines to show */
  lines?: number;
  /** Gap between lines */
  gap?: string;
}

withDefaults(defineProps<Props>(), {
  height: 'h-4',
  width: 'w-full',
  rounded: 'md',
  lines: 1,
  gap: 'gap-2',
});

const roundedClasses = {
  none: 'rounded-none',
  sm: 'rounded-sm',
  md: 'rounded',
  lg: 'rounded-lg',
  xl: 'rounded-xl',
  '2xl': 'rounded-2xl',
  full: 'rounded-full',
};
</script>

<template>
  <div v-if="lines === 1" class="animate-pulse">
    <div
      class="bg-bg-hover"
      :class="[height, width, roundedClasses[rounded]]"
    />
  </div>
  <div v-else class="animate-pulse flex flex-col" :class="gap">
    <div
      v-for="i in lines"
      :key="i"
      class="bg-bg-hover"
      :class="[
        height,
        i === lines ? 'w-2/3' : width,
        roundedClasses[rounded],
      ]"
    />
  </div>
</template>
