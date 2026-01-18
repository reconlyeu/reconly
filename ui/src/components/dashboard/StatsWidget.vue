<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  label: string;
  value: string | number;
  icon?: any;
  variant?: 'default' | 'success' | 'warning' | 'primary';
  trend?: {
    value: number;
    direction: 'up' | 'down';
  };
  loading?: boolean;
  href?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  loading: false,
  href: undefined,
});

const variantClasses = computed(() => {
  const variants = {
    default: 'from-bg-elevated/50 to-bg-elevated/30',
    success: 'from-accent-success/10 to-accent-success/5',
    warning: 'from-accent-warning/10 to-accent-warning/5',
    primary: 'from-accent-primary/10 to-accent-primary/5',
  };
  return variants[props.variant];
});

const iconColor = computed(() => {
  const colors = {
    default: 'text-text-muted',
    success: 'text-accent-success',
    warning: 'text-accent-warning',
    primary: 'text-accent-primary',
  };
  return colors[props.variant];
});
</script>

<template>
  <component
    :is="href ? 'a' : 'div'"
    :href="href"
    class="group relative block overflow-hidden rounded-2xl border border-border-subtle bg-gradient-to-br p-6 transition-all duration-300 hover:border-border-default hover:shadow-xl hover:shadow-black/20 animate-slide-in-right-fast"
    :class="[variantClasses, href && 'cursor-pointer']"
  >
    <!-- Animated gradient overlay on hover -->
    <div
      class="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
    />

    <!-- Content -->
    <div class="relative z-10">
      <!-- Icon and label -->
      <div class="mb-4 flex items-center justify-between">
        <span class="text-sm font-medium tracking-wide text-text-muted uppercase">
          {{ label }}
        </span>
        <component
          v-if="icon"
          :is="icon"
          class="h-5 w-5 transition-transform duration-300 group-hover:scale-110"
          :class="iconColor"
        />
      </div>

      <!-- Value with loading state -->
      <div class="mb-2">
        <div
          v-if="loading"
          class="h-10 w-24 animate-pulse rounded-lg bg-bg-hover"
        />
        <div
          v-else
          class="text-4xl font-bold tracking-tight text-text-primary transition-transform duration-300 group-hover:scale-105"
        >
          {{ value }}
        </div>
      </div>

      <!-- Trend indicator -->
      <div v-if="trend && !loading" class="flex items-center gap-1.5">
        <svg
          v-if="trend.direction === 'up'"
          class="h-4 w-4"
          :class="trend.value > 0 ? 'text-accent-success' : 'text-accent-error'"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
          />
        </svg>
        <svg
          v-else
          class="h-4 w-4"
          :class="trend.value < 0 ? 'text-accent-error' : 'text-accent-success'"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6"
          />
        </svg>
        <span
          class="text-sm font-medium"
          :class="trend.value > 0 ? 'text-accent-success' : 'text-accent-error'"
        >
          {{ Math.abs(trend.value) }}%
        </span>
      </div>
    </div>

    <!-- Decorative corner accent -->
    <div
      class="absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-10 blur-2xl transition-opacity duration-500 group-hover:opacity-20"
      :class="{
        'bg-accent-success': variant === 'success',
        'bg-accent-warning': variant === 'warning',
        'bg-accent-primary': variant === 'primary',
        'bg-text-muted': variant === 'default',
      }"
    />
  </component>
</template>

