<script setup lang="ts">
/**
 * QuickInsights component - displays actionable insight cards
 *
 * Shows:
 * - "New Today" - count with sparkline and change indicator
 * - "This Week" - count with sparkline and change indicator
 * - "Feed Health" - healthy vs failing feeds status
 *
 * Cards are clickable and link to filtered views.
 */
import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { Sparkles, Calendar, HeartPulse, AlertCircle, TrendingUp, TrendingDown } from 'lucide-vue-next';
import { dashboardApi } from '@/services/api';
import { strings } from '@/i18n/en';

type Variant = 'default' | 'success' | 'warning' | 'primary';

interface InsightCard {
  id: string;
  label: string;
  value: string | number;
  subtitle?: string;
  change?: number;
  sparklineData?: number[];
  icon: typeof Sparkles;
  variant: Variant;
  href: string;
}

// Consolidated variant styling - background, icon color, orb color
const variantStyles: Record<Variant, { bg: string; icon: string; orb: string; sparkline: string }> = {
  default: {
    bg: 'from-bg-elevated/50 to-bg-elevated/30',
    icon: 'text-text-muted',
    orb: 'bg-text-muted',
    sparkline: 'stroke-text-muted',
  },
  success: {
    bg: 'from-accent-success/10 to-accent-success/5',
    icon: 'text-accent-success',
    orb: 'bg-accent-success',
    sparkline: 'stroke-accent-success',
  },
  warning: {
    bg: 'from-accent-warning/10 to-accent-warning/5',
    icon: 'text-accent-warning',
    orb: 'bg-accent-warning',
    sparkline: 'stroke-accent-warning',
  },
  primary: {
    bg: 'from-accent-primary/10 to-accent-primary/5',
    icon: 'text-accent-primary',
    orb: 'bg-accent-primary',
    sparkline: 'stroke-accent-primary',
  },
};

const { data: insights, isLoading } = useQuery({
  queryKey: ['dashboard-insights'],
  queryFn: dashboardApi.getInsights,
  refetchInterval: 30000,
});

const feedHealthVariant = computed<Variant>(() => {
  if (!insights.value) return 'default';
  if (insights.value.feeds_failing === 0) return 'success';
  if (insights.value.feeds_failing > insights.value.feeds_healthy) return 'warning';
  return 'default';
});

const feedHealthDisplay = computed(() => {
  if (!insights.value) return '-';
  const { feeds_healthy, feeds_failing } = insights.value;
  if (feeds_failing === 0) {
    return `${feeds_healthy} ${strings.quickInsights.allHealthy}`;
  }
  return `${feeds_healthy}/${feeds_healthy + feeds_failing}`;
});

const feedHealthSubtitle = computed(() => {
  if (!insights.value?.feeds_failing) return '';
  return `${insights.value.feeds_failing} ${strings.quickInsights.needsAttention}`;
});

const insightsConfig = computed<InsightCard[]>(() => [
  {
    id: 'new-today',
    label: strings.quickInsights.newToday,
    value: insights.value?.new_today ?? '-',
    change: insights.value?.change_today,
    sparklineData: insights.value?.daily_counts,
    icon: Sparkles,
    variant: 'primary',
    href: '/digests?period=today',
  },
  {
    id: 'this-week',
    label: strings.quickInsights.thisWeek,
    value: insights.value?.new_this_week ?? '-',
    change: insights.value?.change_week,
    sparklineData: insights.value?.daily_counts,
    icon: Calendar,
    variant: 'default',
    href: '/digests?period=week',
  },
  {
    id: 'feed-health',
    label: strings.quickInsights.feedHealth,
    value: feedHealthDisplay.value,
    subtitle: feedHealthSubtitle.value,
    icon: insights.value?.feeds_failing ? AlertCircle : HeartPulse,
    variant: feedHealthVariant.value,
    href: '/feeds',
  },
]);

// Generate SVG path for sparkline (line path)
function generateSparklinePath(data: number[]): string {
  if (!data || data.length === 0) return '';

  const width = 160;
  const height = 48;
  const padding = 4;

  const maxVal = Math.max(...data, 1);
  const minVal = Math.min(...data, 0);
  const range = maxVal - minVal || 1;

  const points = data.map((val, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
    return `${x},${y}`;
  });

  return `M${points.join(' L')}`;
}

// Generate SVG path for sparkline area fill (closed path)
function generateSparklineAreaPath(data: number[]): string {
  if (!data || data.length === 0) return '';

  const width = 160;
  const height = 48;
  const padding = 4;

  const maxVal = Math.max(...data, 1);
  const minVal = Math.min(...data, 0);
  const range = maxVal - minVal || 1;

  const points = data.map((val, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
    return `${x},${y}`;
  });

  // Close the path: go to bottom-right, bottom-left, then back to start
  const lastX = padding + ((data.length - 1) / (data.length - 1)) * (width - 2 * padding);
  const firstX = padding;

  return `M${points.join(' L')} L${lastX},${height} L${firstX},${height} Z`;
}

// Format change indicator
function formatChange(change: number | undefined): string {
  if (change === undefined || change === 0) return '';
  return change > 0 ? `+${change}` : `${change}`;
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <a
      v-for="(insight, index) in insightsConfig"
      :key="insight.id"
      :href="insight.href"
      class="group relative block overflow-hidden rounded-2xl border border-border-subtle bg-gradient-to-br p-6 transition-all duration-300 hover:border-border-default hover:shadow-xl hover:shadow-black/20 cursor-pointer animate-fade-in"
      :class="variantStyles[insight.variant].bg"
      :style="{ animationDelay: `${index * 100}ms` }"
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
            {{ insight.label }}
          </span>
          <component
            :is="insight.icon"
            class="h-5 w-5 transition-transform duration-300 group-hover:scale-110"
            :class="variantStyles[insight.variant].icon"
          />
        </div>

        <!-- Value row with sparkline -->
        <div class="mb-2 flex items-end justify-between gap-4">
          <div class="flex items-baseline gap-2">
            <!-- Value with loading state -->
            <div
              v-if="isLoading"
              class="h-10 w-20 animate-pulse rounded-lg bg-bg-hover"
            />
            <div
              v-else
              class="text-4xl font-bold tracking-tight text-text-primary transition-transform duration-300 group-hover:scale-105"
            >
              {{ insight.value }}
            </div>

            <!-- Change indicator -->
            <div
              v-if="!isLoading && insight.change !== undefined && insight.change !== 0"
              class="flex items-center gap-0.5 text-sm font-medium"
              :class="insight.change > 0 ? 'text-accent-success' : 'text-accent-warning'"
            >
              <TrendingUp v-if="insight.change > 0" class="h-3.5 w-3.5" />
              <TrendingDown v-else class="h-3.5 w-3.5" />
              <span>{{ formatChange(insight.change) }}</span>
            </div>
          </div>

          <!-- Sparkline Chart -->
          <div
            v-if="!isLoading && insight.sparklineData && insight.sparklineData.length > 1"
            class="relative"
          >
            <svg
              class="h-12 w-40"
              viewBox="0 0 160 48"
              preserveAspectRatio="none"
            >
              <!-- Gradient definition for area fill -->
              <defs>
                <linearGradient :id="`gradient-${insight.id}`" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop
                    offset="0%"
                    :class="insight.variant === 'primary' ? 'text-accent-primary' : insight.variant === 'success' ? 'text-accent-success' : 'text-text-muted'"
                    style="stop-color: currentColor; stop-opacity: 0.3"
                  />
                  <stop
                    offset="100%"
                    :class="insight.variant === 'primary' ? 'text-accent-primary' : insight.variant === 'success' ? 'text-accent-success' : 'text-text-muted'"
                    style="stop-color: currentColor; stop-opacity: 0"
                  />
                </linearGradient>
              </defs>
              <!-- Area fill -->
              <path
                :d="generateSparklineAreaPath(insight.sparklineData)"
                :fill="`url(#gradient-${insight.id})`"
              />
              <!-- Line -->
              <path
                :d="generateSparklinePath(insight.sparklineData)"
                fill="none"
                :class="variantStyles[insight.variant].sparkline"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
        </div>

        <!-- Subtitle (e.g., "2 need attention" for feed health) -->
        <div v-if="insight.subtitle && !isLoading" class="flex items-center gap-1.5">
          <span class="text-sm font-medium text-accent-warning">
            {{ insight.subtitle }}
          </span>
        </div>
      </div>

      <!-- Decorative corner accent -->
      <div
        class="absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-10 blur-2xl transition-opacity duration-500 group-hover:opacity-20"
        :class="variantStyles[insight.variant].orb"
      />
    </a>
  </div>
</template>

<style scoped>
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 0.5s ease-out both;
}
</style>
