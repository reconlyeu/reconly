<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { analyticsApi } from '@/services/api';
import { Loader2 } from 'lucide-vue-next';
import { strings } from '@/i18n/en';

interface Props {
  period: string;
}

const props = defineProps<Props>();
const hoveredIndex = ref<number | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);

const { data, isLoading, isError } = useQuery({
  queryKey: ['analytics-over-time', props.period],
  queryFn: () => analyticsApi.getUsageOverTime(props.period),
  staleTime: 60000,
});

// Calculate cumulative data for rising trend
const cumulativeData = computed(() => {
  if (!data.value || data.value.length === 0) return [];

  let cumulativeIn = 0;
  let cumulativeOut = 0;

  return data.value.map((point) => {
    const dailyIn = point.tokens_in || 0;
    const dailyOut = point.tokens_out || 0;
    cumulativeIn += dailyIn;
    cumulativeOut += dailyOut;

    return {
      ...point,
      daily_tokens_in: dailyIn,
      daily_tokens_out: dailyOut,
      daily_total: dailyIn + dailyOut,
      cumulative_tokens_in: cumulativeIn,
      cumulative_tokens_out: cumulativeOut,
      cumulative_total: cumulativeIn + cumulativeOut,
    };
  });
});

const maxTokens = computed(() => {
  if (cumulativeData.value.length === 0) return 0;
  // Max is the final cumulative total (always the last point)
  const max = cumulativeData.value[cumulativeData.value.length - 1]?.cumulative_total || 0;

  // Add 20% headroom then round up for nice axis labels
  const withHeadroom = max * 1.2;
  if (withHeadroom <= 50000) return Math.ceil(withHeadroom / 10000) * 10000 || 10000;
  if (withHeadroom <= 100000) return Math.ceil(withHeadroom / 25000) * 25000;
  if (withHeadroom <= 500000) return Math.ceil(withHeadroom / 50000) * 50000;
  return Math.ceil(withHeadroom / 100000) * 100000;
});

const chartData = computed(() => {
  if (cumulativeData.value.length === 0) return [];
  return cumulativeData.value.map((point, index) => {
    return {
      ...point,
      percentage: maxTokens.value > 0 ? (point.cumulative_total / maxTokens.value) * 100 : 0,
      index,
      date: new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    };
  });
});

// SVG path calculations
const chartWidth = 600;
const chartHeight = 200;
const padding = { top: 20, right: 30, bottom: 10, left: 10 };

const areaPath = computed(() => {
  if (chartData.value.length === 0) return '';

  const points = chartData.value.map((point, i) => {
    const x = padding.left + (i / Math.max(chartData.value.length - 1, 1)) * (chartWidth - padding.left - padding.right);
    const y = chartHeight - padding.bottom - (point.percentage / 100) * (chartHeight - padding.top - padding.bottom);
    return { x, y };
  });

  // Create smooth curve using cardinal spline
  const linePath = points.map((p, i) => (i === 0 ? `M ${p.x},${p.y}` : `L ${p.x},${p.y}`)).join(' ');

  // Close the area path
  const lastX = points[points.length - 1]?.x || chartWidth - padding.right;
  const firstX = points[0]?.x || padding.left;
  const bottomY = chartHeight - padding.bottom;

  return `${linePath} L ${lastX},${bottomY} L ${firstX},${bottomY} Z`;
});

const linePath = computed(() => {
  if (chartData.value.length === 0) return '';

  const points = chartData.value.map((point, i) => {
    const x = padding.left + (i / Math.max(chartData.value.length - 1, 1)) * (chartWidth - padding.left - padding.right);
    const y = chartHeight - padding.bottom - (point.percentage / 100) * (chartHeight - padding.top - padding.bottom);
    return { x, y };
  });

  return points.map((p, i) => (i === 0 ? `M ${p.x},${p.y}` : `L ${p.x},${p.y}`)).join(' ');
});

const dataPoints = computed(() => {
  return chartData.value.map((point, i) => {
    const x = padding.left + (i / Math.max(chartData.value.length - 1, 1)) * (chartWidth - padding.left - padding.right);
    const y = chartHeight - padding.bottom - (point.percentage / 100) * (chartHeight - padding.top - padding.bottom);
    return { ...point, x, y };
  });
});

const handleMouseEnter = (index: number) => {
  hoveredIndex.value = index;
};

const handleMouseLeave = () => {
  hoveredIndex.value = null;
};

const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(0) + 'k';
  return num.toLocaleString();
};
</script>

<template>
  <div class="rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated to-bg-surface p-6">
    <h2 class="mb-6 flex items-center gap-2 text-lg font-semibold text-text-primary">
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-primary/10">
        <svg class="h-4 w-4 text-accent-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="2 17 7 12 12 17 17 7 22 12" />
        </svg>
      </div>
      {{ strings.analytics.usageChart.title }}
    </h2>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex h-64 items-center justify-center">
      <Loader2 :size="32" class="animate-spin text-text-muted" :stroke-width="2" />
    </div>

    <!-- Error State -->
    <div v-else-if="isError" class="flex h-64 items-center justify-center">
      <p class="text-sm text-status-failed">{{ strings.analytics.usageChart.failedToLoad }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="!chartData || chartData.length === 0" class="flex h-64 items-center justify-center">
      <p class="text-sm text-text-muted">{{ strings.analytics.usageChart.noData }}</p>
    </div>

    <!-- Chart -->
    <div v-else class="relative flex gap-3">
      <!-- Y-axis labels -->
      <div class="flex flex-col justify-between text-xs text-text-muted py-1 w-12 text-right shrink-0">
        <span>{{ formatNumber(maxTokens) }}</span>
        <span>{{ formatNumber(maxTokens / 2) }}</span>
        <span>0</span>
      </div>

      <!-- Chart Area -->
      <div class="flex-1 min-w-0">
        <div ref="chartRef" class="relative rounded-lg bg-bg-surface/50" style="height: 220px;">
          <!-- SVG Chart -->
          <svg
            :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
            class="w-full h-full"
            preserveAspectRatio="none"
          >
            <!-- Gradient definition -->
            <defs>
              <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color: rgb(99, 102, 241); stop-opacity: 0.4" />
                <stop offset="100%" style="stop-color: rgb(99, 102, 241); stop-opacity: 0.05" />
              </linearGradient>
              <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color: rgb(129, 140, 248)" />
                <stop offset="100%" style="stop-color: rgb(99, 102, 241)" />
              </linearGradient>
            </defs>

            <!-- Grid lines -->
            <line
              v-for="i in 3"
              :key="i"
              :x1="padding.left"
              :y1="padding.top + ((i - 1) / 2) * (chartHeight - padding.top - padding.bottom)"
              :x2="chartWidth - padding.right"
              :y2="padding.top + ((i - 1) / 2) * (chartHeight - padding.top - padding.bottom)"
              stroke="currentColor"
              class="text-border-subtle"
              stroke-width="1"
              stroke-dasharray="4,4"
            />

            <!-- Area fill -->
            <path
              :d="areaPath"
              fill="url(#areaGradient)"
              class="transition-all duration-300"
            />

            <!-- Line -->
            <path
              :d="linePath"
              fill="none"
              stroke="url(#lineGradient)"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="transition-all duration-300"
            />

            <!-- Data points -->
            <g v-for="(point, index) in dataPoints" :key="point.date">
              <!-- Hover area (invisible, larger hit target) -->
              <circle
                :cx="point.x"
                :cy="point.y"
                r="20"
                fill="transparent"
                class="cursor-pointer"
                @mouseenter="handleMouseEnter(index)"
                @mouseleave="handleMouseLeave"
              />
              <!-- Visible point -->
              <circle
                :cx="point.x"
                :cy="point.y"
                :r="hoveredIndex === index ? 6 : 4"
                fill="rgb(99, 102, 241)"
                stroke="rgb(30, 30, 46)"
                stroke-width="2"
                class="pointer-events-none transition-all duration-200"
              />
              <!-- Glow on hover -->
              <circle
                v-if="hoveredIndex === index"
                :cx="point.x"
                :cy="point.y"
                r="12"
                fill="rgb(99, 102, 241)"
                opacity="0.2"
                class="pointer-events-none"
              />
            </g>
          </svg>

          <!-- Tooltips (positioned outside SVG for better rendering) -->
          <div
            v-for="(point, index) in dataPoints"
            :key="`tooltip-${point.date}`"
            class="absolute pointer-events-none transition-opacity duration-200"
            :class="hoveredIndex === index ? 'opacity-100' : 'opacity-0'"
            :style="{
              left: `${(point.x / chartWidth) * 100}%`,
              top: `${(point.y / chartHeight) * 100}%`,
              transform: 'translate(-50%, -100%) translateY(-12px)'
            }"
          >
            <div class="whitespace-nowrap rounded-lg border border-border-default bg-bg-elevated px-3 py-2 text-xs shadow-xl">
              <div class="font-semibold text-text-primary">{{ point.date }}</div>
              <div class="mt-1 space-y-0.5">
                <div class="text-text-muted text-[10px] uppercase tracking-wide mb-1">{{ strings.analytics.usageChart.cumulative }}</div>
                <div class="flex justify-between gap-4">
                  <span class="text-text-muted">{{ strings.analytics.usageChart.total }}</span>
                  <span class="font-mono text-accent-primary font-semibold">{{ point.cumulative_total.toLocaleString() }}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-text-muted">{{ strings.analytics.usageChart.in }}</span>
                  <span class="font-mono text-green-400">{{ point.cumulative_tokens_in.toLocaleString() }}</span>
                </div>
                <div class="flex justify-between gap-4">
                  <span class="text-text-muted">{{ strings.analytics.usageChart.out }}</span>
                  <span class="font-mono text-blue-400">{{ point.cumulative_tokens_out.toLocaleString() }}</span>
                </div>
                <div class="text-text-muted text-[10px] uppercase tracking-wide mt-2 mb-1">{{ strings.analytics.usageChart.thisDay }}</div>
                <div class="flex justify-between gap-4">
                  <span class="text-text-muted">{{ strings.analytics.usageChart.daily }}</span>
                  <span class="font-mono text-text-secondary">+{{ point.daily_total.toLocaleString() }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- X-axis labels -->
        <div class="mt-3 flex justify-between text-xs text-text-muted">
          <span>{{ chartData[0]?.date }}</span>
          <span v-if="chartData.length > 2">{{ chartData[Math.floor(chartData.length / 2)]?.date }}</span>
          <span>{{ chartData[chartData.length - 1]?.date }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
