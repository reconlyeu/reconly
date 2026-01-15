/**
 * Composable for managing extensions via Vue Query
 *
 * Provides reactive queries and mutations for:
 * - Listing installed extensions
 * - Enabling/disabling extensions
 * - Installing/uninstalling from catalog
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { extensionsApi } from '@/services/api';
import type { Extension, ExtensionType, ExtensionInstallResponse } from '@/types/entities';
import { computed, type Ref } from 'vue';

/**
 * Query key for extensions list
 */
export const EXTENSIONS_QUERY_KEY = ['extensions'] as const;

/**
 * Hook to fetch all installed extensions
 */
export function useExtensionsList(type?: Ref<ExtensionType | undefined>) {
  return useQuery({
    queryKey: [...EXTENSIONS_QUERY_KEY, type?.value],
    queryFn: () => extensionsApi.list(type?.value),
    staleTime: 5 * 60 * 1000, // 5 minutes - extensions rarely change
  });
}

/**
 * Hook to get extensions of a specific type
 */
export function useExtensionsByType(type: ExtensionType) {
  return useQuery({
    queryKey: [...EXTENSIONS_QUERY_KEY, type],
    queryFn: () => extensionsApi.listByType(type),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook to get a specific extension by type and name
 */
export function useExtension(type: ExtensionType, name: string) {
  const { data: extensions, isLoading, isError, error } = useExtensionsList();

  const extension = computed(() => {
    if (!extensions.value) return null;
    return extensions.value.find((e) => e.type === type && e.name === name) || null;
  });

  return {
    extension,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook to get only enabled extensions
 */
export function useEnabledExtensions() {
  const { data: extensions, isLoading, isError, error } = useExtensionsList();

  const enabledExtensions = computed(() => {
    if (!extensions.value) return [];
    return extensions.value.filter((e) => e.enabled);
  });

  return {
    extensions: enabledExtensions,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook for toggling extension enabled state
 */
export function useToggleExtension(options?: {
  onSuccess?: (data: Extension) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, name, enabled }: { type: ExtensionType; name: string; enabled: boolean }) =>
      extensionsApi.setEnabled(type, name, enabled),
    onSuccess: (data) => {
      // Invalidate extensions list to refresh activation states
      queryClient.invalidateQueries({ queryKey: EXTENSIONS_QUERY_KEY });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// CATALOG (Phase 2)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Query key for extension catalog
 */
export const CATALOG_QUERY_KEY = ['extensions', 'catalog'] as const;

/**
 * Hook to fetch the extension catalog
 */
export function useCatalog(options?: { forceRefresh?: boolean }) {
  return useQuery({
    queryKey: [...CATALOG_QUERY_KEY, options?.forceRefresh],
    queryFn: () => extensionsApi.getCatalog(options?.forceRefresh),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to search the extension catalog
 */
export function useCatalogSearch(
  query: Ref<string | undefined>,
  type: Ref<ExtensionType | undefined>,
  verifiedOnly: Ref<boolean>
) {
  return useQuery({
    queryKey: [...CATALOG_QUERY_KEY, 'search', query, type, verifiedOnly],
    queryFn: () => extensionsApi.searchCatalog(query.value, type.value, verifiedOnly.value),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for installing an extension
 * Supports both PyPI package names and GitHub URLs
 */
export function useInstallExtension(options?: {
  onSuccess?: (data: ExtensionInstallResponse) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ packageName, githubUrl, upgrade }: { packageName?: string; githubUrl?: string; upgrade?: boolean }) =>
      extensionsApi.install(packageName, githubUrl, upgrade),
    onSuccess: (data) => {
      // Invalidate catalog to refresh installed status
      queryClient.invalidateQueries({ queryKey: CATALOG_QUERY_KEY });
      // Also invalidate extensions list since a new one might be available after restart
      queryClient.invalidateQueries({ queryKey: EXTENSIONS_QUERY_KEY });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
}

/**
 * Hook for uninstalling an extension
 */
export function useUninstallExtension(options?: {
  onSuccess?: (data: ExtensionInstallResponse) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ type, name }: { type: ExtensionType; name: string }) =>
      extensionsApi.uninstall(type, name),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: CATALOG_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: EXTENSIONS_QUERY_KEY });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
}
