/**
 * Pinia store for Analytics
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  AnalyticsSummary,
  TokensByProvider,
  TokensByFeed,
  UsageOverTime,
} from '@/types/entities';
import type { AnalyticsPeriod } from '@/services/api';

export const useAnalyticsStore = defineStore('analytics', () => {
  // State
  const summary = ref<AnalyticsSummary | null>(null);
  const tokensByProvider = ref<TokensByProvider[]>([]);
  const tokensByFeed = ref<TokensByFeed[]>([]);
  const usageOverTime = ref<UsageOverTime[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const period = ref<AnalyticsPeriod>('7d');

  // Getters
  const totalTokens = computed(() => {
    if (!summary.value) return 0;
    return summary.value.total_tokens_in + summary.value.total_tokens_out;
  });

  const successRate = computed(() => {
    return summary.value?.success_rate ?? 0;
  });

  const topProvider = computed(() => {
    if (tokensByProvider.value.length === 0) return null;
    return tokensByProvider.value.reduce((max, p) =>
      p.tokens_in + p.tokens_out > max.tokens_in + max.tokens_out ? p : max
    );
  });

  const topFeed = computed(() => {
    if (tokensByFeed.value.length === 0) return null;
    return tokensByFeed.value.reduce((max, f) =>
      f.tokens_in + f.tokens_out > max.tokens_in + max.tokens_out ? f : max
    );
  });

  // Actions
  const setSummary = (data: AnalyticsSummary) => {
    summary.value = data;
  };

  const setTokensByProvider = (data: TokensByProvider[]) => {
    tokensByProvider.value = data;
  };

  const setTokensByFeed = (data: TokensByFeed[]) => {
    tokensByFeed.value = data;
  };

  const setUsageOverTime = (data: UsageOverTime[]) => {
    usageOverTime.value = data;
  };

  const setPeriod = (value: AnalyticsPeriod) => {
    period.value = value;
  };

  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  const setError = (value: string | null) => {
    error.value = value;
  };

  const reset = () => {
    summary.value = null;
    tokensByProvider.value = [];
    tokensByFeed.value = [];
    usageOverTime.value = [];
  };

  return {
    // State
    summary,
    tokensByProvider,
    tokensByFeed,
    usageOverTime,
    loading,
    error,
    period,
    // Getters
    totalTokens,
    successRate,
    topProvider,
    topFeed,
    // Actions
    setSummary,
    setTokensByProvider,
    setTokensByFeed,
    setUsageOverTime,
    setPeriod,
    setLoading,
    setError,
    reset,
  };
});
