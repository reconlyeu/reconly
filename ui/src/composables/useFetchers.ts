/**
 * Composable for managing fetchers via Vue Query
 *
 * Provides reactive queries and mutations for:
 * - Listing available fetchers with their config schemas
 * - Toggling fetcher enabled state
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { fetchersApi } from '@/services/api';
import type { Fetcher } from '@/types/entities';
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
 * Hook to get only enabled fetchers
 */
export function useEnabledFetchers() {
  const { data: fetchers, isLoading, isError, error } = useFetchersList();

  const enabledFetchers = computed(() => {
    if (!fetchers.value) return [];
    return fetchers.value.filter((f) => f.enabled);
  });

  return {
    fetchers: enabledFetchers,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook for toggling fetcher enabled state
 */
export function useToggleFetcher(options?: {
  onSuccess?: (data: Fetcher) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      fetchersApi.setEnabled(name, enabled),
    onSuccess: (data) => {
      // Invalidate fetchers list to refresh activation states
      queryClient.invalidateQueries({ queryKey: FETCHERS_QUERY_KEY });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
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
