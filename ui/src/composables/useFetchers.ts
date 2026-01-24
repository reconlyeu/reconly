/**
 * Composable for managing fetchers via Vue Query
 *
 * Provides reactive queries for:
 * - Listing available fetchers with their config schemas
 */

import { useQuery } from '@tanstack/vue-query';
import { fetchersApi } from '@/services/api';
import { computed } from 'vue';

/**
 * Query key for fetchers list
 */
export const FETCHERS_QUERY_KEY = ['fetchers'] as const;

/**
 * Hook to fetch all available fetchers with their config schemas
 */
export function useFetchersList() {
  return useQuery({
    queryKey: FETCHERS_QUERY_KEY,
    queryFn: () => fetchersApi.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes - fetchers rarely change
  });
}

/**
 * Hook to get a specific fetcher by name
 */
export function useFetcher(name: string) {
  const { data: fetchers, isLoading, isError, error } = useFetchersList();

  const fetcher = computed(() => {
    if (!fetchers.value) return null;
    return fetchers.value.find((f) => f.name === name) || null;
  });

  return {
    fetcher,
    isLoading,
    isError,
    error,
  };
}

/**
 * Helper to get the config settings key prefix for a fetcher
 */
export function getFetcherSettingsPrefix(fetcherName: string): string {
  return `fetch.${fetcherName}`;
}

/**
 * Helper to build the full setting key for a fetcher config field
 */
export function getFetcherSettingKey(fetcherName: string, fieldKey: string): string {
  return `${getFetcherSettingsPrefix(fetcherName)}.${fieldKey}`;
}
