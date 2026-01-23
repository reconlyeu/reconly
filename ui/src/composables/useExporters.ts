/**
 * Composable for managing exporters via Vue Query
 *
 * Provides reactive queries and mutations for:
 * - Listing available exporters with their config schemas
 * - Exporting digests directly to filesystem paths
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { exportersApi, digestsApi } from '@/services/api';
import type { Exporter, ExportToPathRequest, ExportToPathResponse } from '@/types/entities';
import { computed } from 'vue';

/**
 * Query key for exporters list
 */
export const EXPORTERS_QUERY_KEY = ['exporters'] as const;

/**
 * Hook to fetch all available exporters with their config schemas
 */
export function useExportersList() {
  return useQuery({
    queryKey: EXPORTERS_QUERY_KEY,
    queryFn: () => exportersApi.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes - exporters rarely change
  });
}

/**
 * Hook to get a specific exporter by name
 */
export function useExporter(name: string) {
  const { data: exporters, isLoading, isError, error } = useExportersList();

  const exporter = computed(() => {
    if (!exporters.value) return null;
    return exporters.value.find((e) => e.name === name) || null;
  });

  return {
    exporter,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook to get exporters that support direct file export
 */
export function useDirectExportCapableExporters() {
  const { data: exporters, isLoading, isError, error } = useExportersList();

  const directExportExporters = computed(() => {
    if (!exporters.value) return [];
    return exporters.value.filter((e) => e.supports_direct_export);
  });

  return {
    exporters: directExportExporters,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook to get only enabled exporters
 */
export function useEnabledExporters() {
  const { data: exporters, isLoading, isError, error } = useExportersList();

  const enabledExporters = computed(() => {
    if (!exporters.value) return [];
    return exporters.value.filter((e) => e.enabled);
  });

  return {
    exporters: enabledExporters,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook to get enabled exporters that support direct file export
 * Used in feed config modal for auto-export options
 */
export function useEnabledDirectExportExporters() {
  const { data: exporters, isLoading, isError, error } = useExportersList();

  const enabledDirectExportExporters = computed(() => {
    if (!exporters.value) return [];
    return exporters.value.filter((e) => e.enabled && e.supports_direct_export);
  });

  return {
    exporters: enabledDirectExportExporters,
    isLoading,
    isError,
    error,
  };
}

/**
 * Hook for toggling exporter enabled state
 */
export function useToggleExporter(options?: {
  onSuccess?: (data: Exporter) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      exportersApi.setEnabled(name, enabled),
    onSuccess: (data) => {
      // Invalidate exporters list to refresh activation states
      queryClient.invalidateQueries({ queryKey: EXPORTERS_QUERY_KEY });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
}

/**
 * Hook for exporting digests to a filesystem path
 *
 * Returns a mutation that can be called with export parameters.
 * Handles loading state, success, and error states.
 */
export function useExportToPath(options?: {
  onSuccess?: (data: ExportToPathResponse) => void;
  onError?: (error: Error) => void;
}) {
  return useMutation({
    mutationFn: (request: ExportToPathRequest) => digestsApi.exportToPath(request),
    onSuccess: (data) => {
      // Optionally invalidate digests cache if needed
      // queryClient.invalidateQueries({ queryKey: ['digests'] });
      options?.onSuccess?.(data);
    },
    onError: (error: Error) => {
      options?.onError?.(error);
    },
  });
}

/**
 * Helper to get the config settings key prefix for an exporter
 */
export function getExporterSettingsPrefix(exporterName: string): string {
  return `export.${exporterName}`;
}

/**
 * Helper to build the full setting key for an exporter config field
 */
export function getExporterSettingKey(exporterName: string, fieldKey: string): string {
  return `${getExporterSettingsPrefix(exporterName)}.${fieldKey}`;
}
