/**
 * Composable for managing source type options from dynamic fetchers.
 *
 * Provides reactive access to available source types fetched from the
 * /api/v1/fetchers endpoint, with caching, loading states, and helper
 * functions for type lookups.
 */

import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { fetchersApi } from '@/services/api';
import type { Fetcher } from '@/types/entities';
import { FETCHERS_QUERY_KEY } from '@/composables/useFetchers';

/**
 * Represents a source type option for use in dropdowns and forms.
 */
export interface SourceTypeOption {
  /** Internal type name (e.g., 'rss', 'youtube') */
  name: string;
  /** Human-readable display name */
  displayName: string;
  /** Description of the source type */
  description: string;
  /** Icon identifier (e.g., 'mdi:rss') */
  icon: string | null;
  /** Whether this type requires OAuth authentication */
  supportsOAuth: boolean;
  /** List of OAuth providers if OAuth is supported */
  oauthProviders: string[];
  /** Whether this is an extension-provided type */
  isExtension: boolean;
}

/** Re-export for consumers that only use this composable */
export { FETCHERS_QUERY_KEY as FETCHER_TYPES_QUERY_KEY };

/**
 * Types that have custom form components and should not use the generic URL form.
 * These types have specialized UIs that handle their own field rendering.
 */
export const CUSTOM_FORM_TYPES = ['agent', 'imap'] as const;
export type CustomFormType = typeof CUSTOM_FORM_TYPES[number];

/**
 * Check if a source type has a custom form component.
 */
export function hasCustomForm(typeName: string): typeName is CustomFormType {
  return CUSTOM_FORM_TYPES.includes(typeName as CustomFormType);
}

/**
 * Hook to fetch and manage source type options from the API.
 *
 * @returns Reactive source type options with loading/error states
 */
export function useFetcherTypes() {
  const {
    data: fetchers,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: FETCHERS_QUERY_KEY,
    queryFn: () => fetchersApi.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes - fetchers rarely change
  });

  /**
   * Transform fetcher data into source type options.
   * Only includes configured/enabled fetchers.
   */
  const sourceTypeOptions = computed<SourceTypeOption[]>(() => {
    if (!fetchers.value) return [];

    return fetchers.value
      .filter((f) => f.is_configured) // Only show configured fetchers
      .map((fetcher): SourceTypeOption => ({
        name: fetcher.name,
        displayName: fetcher.metadata?.display_name || fetcher.name,
        description: fetcher.description,
        icon: fetcher.metadata?.icon || null,
        supportsOAuth: fetcher.metadata?.supports_oauth || false,
        oauthProviders: fetcher.oauth_providers || [],
        isExtension: fetcher.is_extension,
      }));
  });

  /**
   * Get valid source type names for validation.
   */
  const validSourceTypes = computed<string[]>(() => {
    return sourceTypeOptions.value.map((opt) => opt.name);
  });

  /**
   * Get a specific fetcher by name.
   */
  const getFetcherByName = (name: string): Fetcher | null => {
    if (!fetchers.value) return null;
    return fetchers.value.find((f) => f.name === name) || null;
  };

  /**
   * Get source type option by name.
   */
  const getTypeOption = (name: string): SourceTypeOption | null => {
    return sourceTypeOptions.value.find((opt) => opt.name === name) || null;
  };

  /**
   * Get URL placeholder for a source type.
   * Falls back to a generic placeholder if type not found.
   */
  const getUrlPlaceholder = (typeName: string): string => {
    const placeholders: Record<string, string> = {
      rss: 'https://example.com/feed.xml',
      youtube: 'https://youtube.com/@channel or /watch?v=...',
      website: 'https://example.com/article',
      blog: 'https://blog.example.com',
    };
    return placeholders[typeName] || 'https://example.com';
  };

  return {
    // Data
    fetchers,
    sourceTypeOptions,
    validSourceTypes,

    // State
    isLoading,
    isError,
    error,

    // Methods
    refetch,
    getFetcherByName,
    getTypeOption,
    getUrlPlaceholder,
  };
}
