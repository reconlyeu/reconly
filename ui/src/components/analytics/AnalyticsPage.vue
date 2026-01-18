<script setup lang="ts">
import { ref } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { analyticsApi } from '@/services/api';
import { strings } from '@/i18n/en';
import StatsWidget from '@/components/dashboard/StatsWidget.vue';
import ProviderUsageChart from './ProviderUsageChart.vue';
import UsageOverTimeChart from './UsageOverTimeChart.vue';
import { TrendingUp, TrendingDown, Activity } from 'lucide-vue-next';

const selectedPeriod = ref('7d');

const { data: summary } = useQuery({
  queryKey: ['analytics-summary', selectedPeriod],
  queryFn: () => analyticsApi.getSummary(selectedPeriod.value),
  staleTime: 60000,
  refetchInterval: 60000,
});

const periods = [
  { value: '7d', label: strings.analytics.periods.week },
  { value: '30d', label: strings.analytics.periods.month },
  { value: '90d', label: strings.analytics.periods.quarter },
];
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-text-primary">{{ strings.analytics.title }}</h1>
        <p class="mt-1 text-sm text-text-secondary">
          Monitor LLM token usage and success metrics
        </p>
      </div>

      <!-- Period Selector -->
      <select
        v-model="selectedPeriod"
        class="rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
      >
        <option v-for="period in periods" :key="period.value" :value="period.value">
          {{ period.label }}
        </option>
      </select>
    </div>

    <!-- Summary Stats -->
    <div class="mb-8 grid gap-4 md:grid-cols-3">
      <StatsWidget
        :label="strings.analytics.summary.tokensIn"
        :value="summary?.total_tokens_in?.toLocaleString() || '-'"
        variant="default"
        :icon="TrendingUp"
      />
      <StatsWidget
        :label="strings.analytics.summary.tokensOut"
        :value="summary?.total_tokens_out?.toLocaleString() || '-'"
        variant="primary"
        :icon="TrendingDown"
      />
      <StatsWidget
        :label="strings.analytics.summary.successRate"
        :value="summary?.success_rate ? `${summary.success_rate.toFixed(1)}%` : '-'"
        variant="success"
        :icon="Activity"
      />
    </div>

    <!-- Charts -->
    <div class="space-y-6">
      <!-- Provider Usage -->
      <div>
        <ProviderUsageChart :period="selectedPeriod" />
      </div>

      <!-- Usage Over Time -->
      <div>
        <UsageOverTimeChart :period="selectedPeriod" />
      </div>
    </div>
  </div>
</template>

