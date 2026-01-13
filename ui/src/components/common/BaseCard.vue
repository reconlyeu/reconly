<script setup lang="ts">
/**
 * Base card component with shared styling.
 * Provides hover glow, decorative orb, and gradient background.
 * Use slots for header, default (body), and footer content.
 */

interface Props {
  /** Make the card clickable with cursor-pointer */
  clickable?: boolean;
  /** Color for the decorative glow effect */
  glowColor?: 'primary' | 'success' | 'warning' | 'error' | 'blue' | 'purple' | 'orange';
  /** Disable hover effects */
  static?: boolean;
  /** Add padding to the card */
  padded?: boolean;
}

interface Emits {
  (e: 'click'): void;
}

const props = withDefaults(defineProps<Props>(), {
  clickable: false,
  glowColor: 'primary',
  static: false,
  padded: true,
});

defineEmits<Emits>();

const glowColors = {
  primary: 'bg-accent-primary',
  success: 'bg-status-success',
  warning: 'bg-amber-400',
  error: 'bg-status-failed',
  blue: 'bg-blue-400',
  purple: 'bg-purple-400',
  orange: 'bg-orange-400',
};
</script>

<template>
  <div
    @click="clickable ? $emit('click') : undefined"
    class="group relative overflow-hidden rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated to-bg-surface transition-all duration-500"
    :class="[
      padded ? 'p-6' : '',
      clickable ? 'cursor-pointer' : '',
      !static ? 'hover:border-border-default hover:shadow-2xl hover:shadow-accent-primary/5' : '',
      clickable && !static ? 'hover:-translate-y-1' : '',
    ]"
  >
    <!-- Hover glow effect -->
    <div
      v-if="!static"
      class="absolute inset-0 bg-gradient-to-br from-accent-primary/[0.02] to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
    />

    <!-- Decorative corner orb -->
    <div
      v-if="!static"
      class="absolute -right-16 -top-16 h-40 w-40 rounded-full opacity-0 blur-3xl transition-all duration-700 group-hover:opacity-20"
      :class="glowColors[glowColor]"
    />

    <!-- Content wrapper -->
    <div class="relative flex h-full flex-col">
      <!-- Header slot -->
      <div v-if="$slots.header" class="mb-4">
        <slot name="header" />
      </div>

      <!-- Default slot (body) -->
      <div class="flex-1">
        <slot />
      </div>

      <!-- Footer slot -->
      <div v-if="$slots.footer" class="mt-4 border-t border-border-subtle pt-4">
        <slot name="footer" />
      </div>
    </div>
  </div>
</template>
